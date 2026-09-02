"""Unit tests for NIU API authentication and error handling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sys
from threading import Barrier
import types
import unittest
from unittest.mock import Mock, patch


class RequestException(Exception):
    """Base exception raised by the fake requests module."""


class Timeout(RequestException):
    """Request timed out."""


class FakeResponse:
    """Small requests.Response replacement used by the unit tests."""

    def __init__(
        self,
        status_code: int,
        payload: object | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self) -> object:
        """Return the configured response payload."""
        if self._payload is None:
            raise ValueError("response is not valid JSON")
        return self._payload


def _load_api_module():
    """Load the API module without requiring a Home Assistant installation."""
    repository_root = Path(__file__).resolve().parents[2]
    component_root = repository_root / "custom_components"
    niu_root = component_root / "niu"

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(component_root)]
    niu_package = types.ModuleType("custom_components.niu")
    niu_package.__path__ = [str(niu_root)]
    sys.modules["custom_components"] = custom_components
    sys.modules["custom_components.niu"] = niu_package

    requests_module = types.ModuleType("requests")
    requests_module.get = Mock(name="requests.get")
    requests_module.post = Mock(name="requests.post")
    requests_module.exceptions = types.SimpleNamespace(
        RequestException=RequestException,
    )
    sys.modules["requests"] = requests_module

    spec = importlib.util.spec_from_file_location(
        "custom_components.niu.api", niu_root / "api.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load custom_components.niu.api")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


api_module = _load_api_module()


def token_response(
    access_token: str,
    refresh_token: str = "refresh-token",
    expires_in: int = 86_400,
) -> FakeResponse:
    """Create a successful NIU OAuth token response."""
    return FakeResponse(
        200,
        {
            "status": 0,
            "data": {
                "token": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in,
                }
            },
        },
    )


def data_response(value: str = "ok") -> FakeResponse:
    """Create a successful NIU data response."""
    return FakeResponse(200, {"status": 0, "data": {"value": value}})


class NiuApiTest(unittest.TestCase):
    """Verify authentication recovery and robust HTTP handling."""

    def setUp(self) -> None:
        api_module.requests.get.reset_mock(return_value=True, side_effect=True)
        api_module.requests.post.reset_mock(return_value=True, side_effect=True)
        self.api = api_module.NiuApi("user@example.com", "secret", 0)
        self.api.sn = "TEST-SN"

    def assert_request_timeout(self, request_mock: Mock) -> None:
        """Assert that a requests call used the integration timeout."""
        self.assertEqual(
            request_mock.call_args.kwargs["timeout"], api_module.REQUEST_TIMEOUT
        )

    def set_authenticated(
        self,
        access_token: str = "access",
        *,
        refresh_token: str | None = None,
        refresh_at: float = 1_000,
    ) -> None:
        """Configure an access token that remains valid until refresh_at."""
        self.api.token = access_token
        self.api.refresh_token = refresh_token
        self.api._token_refresh_at = refresh_at

    def test_password_login_stores_full_token_and_uses_timeout(self) -> None:
        """A password login should retain refresh metadata for later renewal."""
        api_module.requests.post.return_value = token_response("access-1")

        token = self.api.get_token()

        self.assertEqual(token, "access-1")
        self.assertEqual(self.api.token, "access-1")
        self.assertEqual(self.api.refresh_token, "refresh-token")
        self.assert_request_timeout(api_module.requests.post)
        login_data = api_module.requests.post.call_args.kwargs["data"]
        self.assertEqual(login_data["grant_type"], "password")
        self.assertNotEqual(login_data["password"], "secret")

    def test_expiring_token_is_refreshed_before_api_request(self) -> None:
        """A token at its refresh deadline should be renewed proactively."""
        self.set_authenticated(
            "old-access", refresh_token="refresh-token", refresh_at=50
        )
        api_module.requests.post.return_value = token_response("new-access")
        api_module.requests.get.return_value = data_response()

        with patch.object(api_module, "monotonic", return_value=100):
            result = self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assertEqual(result["data"]["value"], "ok")
        self.assertEqual(api_module.requests.post.call_count, 1)
        self.assertEqual(
            api_module.requests.get.call_args.kwargs["headers"]["token"],
            "new-access",
        )

    def test_401_refreshes_token_and_retries_request_once(self) -> None:
        """An expired access token should be refreshed and the request retried."""
        self.set_authenticated("old-access", refresh_token="refresh-token")
        api_module.requests.get.side_effect = [
            FakeResponse(401, {"status": 401, "desc": "invalid token"}),
            data_response("recovered"),
        ]
        api_module.requests.post.return_value = token_response("new-access")

        with patch.object(api_module, "monotonic", return_value=0):
            result = self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assertEqual(result["data"]["value"], "recovered")
        self.assertEqual(api_module.requests.get.call_count, 2)
        self.assertEqual(api_module.requests.post.call_count, 1)
        retry_headers = api_module.requests.get.call_args_list[1].kwargs["headers"]
        self.assertEqual(retry_headers["token"], "new-access")
        refresh_data = api_module.requests.post.call_args.kwargs["data"]
        self.assertEqual(refresh_data["grant_type"], "refresh_token")
        self.assertEqual(refresh_data["refresh_token"], "refresh-token")

    def test_401_relogs_in_when_refresh_token_is_rejected(self) -> None:
        """A rejected refresh token should fall back to a password login."""
        self.set_authenticated("old-access", refresh_token="invalid-refresh")
        api_module.requests.get.side_effect = [
            FakeResponse(401, {"status": 401, "desc": "invalid token"}),
            data_response("relogged"),
        ]
        api_module.requests.post.side_effect = [
            FakeResponse(401, {"status": 401, "desc": "invalid refresh token"}),
            token_response("password-access", "password-refresh"),
        ]

        with (
            patch.object(api_module, "monotonic", return_value=0),
            patch.object(api_module._LOGGER, "warning") as warning,
        ):
            result = self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assertEqual(result["data"]["value"], "relogged")
        self.assertEqual(api_module.requests.post.call_count, 2)
        warning.assert_called_once()
        retry_headers = api_module.requests.get.call_args_list[1].kwargs["headers"]
        self.assertEqual(retry_headers["token"], "password-access")

    def test_second_401_raises_authentication_error_without_looping(self) -> None:
        """Authentication recovery should retry exactly once."""
        self.set_authenticated("old-access", refresh_token="refresh-token")
        api_module.requests.get.side_effect = [
            FakeResponse(401, {"status": 401}),
            FakeResponse(401, {"status": 401}),
        ]
        api_module.requests.post.return_value = token_response("new-access")
        with (
            patch.object(api_module, "monotonic", return_value=0),
            self.assertRaises(api_module.NiuAuthenticationError),
        ):
            self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assertEqual(api_module.requests.get.call_count, 2)
        self.assertEqual(api_module.requests.post.call_count, 1)

    def test_concurrent_401_responses_share_one_token_refresh(self) -> None:
        """Concurrent expired requests should not create a refresh-token storm."""
        self.set_authenticated("old-access", refresh_token="refresh-token")
        first_request_barrier = Barrier(2)

        def get_response(*args, **kwargs):
            if kwargs["headers"]["token"] == "old-access":
                first_request_barrier.wait(timeout=2)
                return FakeResponse(401, {"status": 401})
            return data_response("concurrent-recovery")

        api_module.requests.get.side_effect = get_response
        api_module.requests.post.return_value = token_response("new-access")

        with (
            patch.object(api_module, "monotonic", return_value=0),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            results = list(
                executor.map(
                    lambda _: self.api.get_info(api_module.MOTOR_BATTERY_API_URI),
                    range(2),
                )
            )

        self.assertEqual(
            [result["data"]["value"] for result in results],
            ["concurrent-recovery", "concurrent-recovery"],
        )
        self.assertEqual(api_module.requests.get.call_count, 4)
        self.assertEqual(api_module.requests.post.call_count, 1)

    def test_timeout_raises_connection_error(self) -> None:
        """Transport timeouts should become a stable integration exception."""
        self.set_authenticated()
        api_module.requests.get.side_effect = Timeout("read timed out")
        with (
            patch.object(api_module, "monotonic", return_value=0),
            self.assertRaises(api_module.NiuConnectionError),
        ):
            self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assert_request_timeout(api_module.requests.get)

    def test_429_exposes_retry_after(self) -> None:
        """Rate-limit responses should retain the server's backoff duration."""
        self.set_authenticated()
        api_module.requests.get.return_value = FakeResponse(
            429,
            {"status": 429, "desc": "too many requests"},
            headers={"Retry-After": "120"},
        )
        with (
            patch.object(api_module, "monotonic", return_value=0),
            self.assertRaises(api_module.NiuRateLimitError) as raised,
        ):
            self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assertEqual(raised.exception.retry_after, 120)

    def test_niu_status_error_raises_response_error(self) -> None:
        """HTTP 200 responses with a NIU error status should not look successful."""
        self.set_authenticated()
        api_module.requests.get.return_value = FakeResponse(
            200, {"status": 1234, "desc": "temporary NIU failure"}
        )
        with (
            patch.object(api_module, "monotonic", return_value=0),
            self.assertRaises(api_module.NiuResponseError) as raised,
        ):
            self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

        self.assertEqual(raised.exception.niu_status, 1234)

    def test_invalid_json_raises_response_error(self) -> None:
        """Malformed responses should be reported without leaking parser errors."""
        self.set_authenticated()
        api_module.requests.get.return_value = FakeResponse(200, None)

        with (
            patch.object(api_module, "monotonic", return_value=0),
            self.assertRaises(api_module.NiuResponseError),
        ):
            self.api.get_info(api_module.MOTOR_BATTERY_API_URI)

    def test_failed_update_preserves_last_good_data(self) -> None:
        """A failed refresh should not replace cached data with False."""
        previous_data = {"status": 0, "data": {"value": "previous"}}
        self.api.dataBat = previous_data
        self.set_authenticated()
        api_module.requests.get.return_value = FakeResponse(
            503, {"status": 503, "desc": "service unavailable"}
        )
        with (
            patch.object(api_module, "monotonic", return_value=0),
            self.assertRaises(api_module.NiuServerError),
        ):
            self.api.updateBat()

        self.assertIs(self.api.dataBat, previous_data)

    def test_getters_tolerate_missing_or_malformed_cached_data(self) -> None:
        """Partial NIU payloads should make entities unavailable, not crash them."""
        self.api.dataBat = {"data": {"batteries": None}}
        self.api.dataMoto = {"data": {"lastTrack": None, "postion": None}}
        self.api.dataMotoInfo = {"data": None}
        self.api.dataTrackInfo = {"data": []}

        self.assertIsNone(self.api.getDataBatA("batteryCharging"))
        self.assertIsNone(self.api.getDataBatB("batteryCharging"))
        self.assertIsNone(self.api.getDataMoto("estimatedMileage"))
        self.assertIsNone(self.api.getDataDist("distance"))
        self.assertIsNone(self.api.getDataPos("lat"))
        self.assertIsNone(self.api.getDataOverall("totalMileage"))
        self.assertIsNone(self.api.getDataTrack("track_thumb"))

    def test_initialize_rejects_invalid_vehicle_index(self) -> None:
        """Invalid indexes must not silently select another NIU vehicle."""
        api_module.requests.post.return_value = token_response("access")
        api_module.requests.get.return_value = FakeResponse(
            200,
            {
                "status": 0,
                "data": {
                    "items": [
                        {"sn_id": "FIRST", "scooter_name": "First"},
                        {"sn_id": "LAST", "scooter_name": "Last"},
                    ]
                },
            },
        )

        for scooter_id in (-1, 2):
            with self.subTest(scooter_id=scooter_id):
                self.api.scooter_id = scooter_id
                with self.assertRaises(api_module.NiuVehicleNotFoundError):
                    self.api.initialize()

    def test_get_vehicles_info_sends_overseas_locale_headers(self) -> None:
        """The vehicle list request must carry the caller's locale."""
        self.set_authenticated()
        api_module.requests.get.return_value = data_response()

        with patch.object(api_module, "monotonic", return_value=0):
            self.api.get_vehicles_info(api_module.MOTOINFO_LIST_API_URI)

        headers = api_module.requests.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Accept-Language"], "en-US")
        self.assertIn("clientIdentifier=Overseas", headers["user-agent"])
        self.assertIn("lang=en-US", headers["user-agent"])

    def test_get_vehicles_info_sends_domestic_identifier_for_chinese(self) -> None:
        """A Chinese locale must still be tagged as a domestic client."""
        self.api = api_module.NiuApi(
            "user@example.com", "secret", 0, language="zh-CN"
        )
        self.api.sn = "TEST-SN"
        self.set_authenticated()
        api_module.requests.get.return_value = data_response()

        with patch.object(api_module, "monotonic", return_value=0):
            self.api.get_vehicles_info(api_module.MOTOINFO_LIST_API_URI)

        headers = api_module.requests.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Accept-Language"], "zh-CN")
        self.assertIn("clientIdentifier=Domestic", headers["user-agent"])

    def test_initialize_prefers_serial_number_over_changed_list_order(self) -> None:
        """An existing entry must keep its vehicle when NIU reorders the list."""
        api_module.requests.post.return_value = token_response("access")
        api_module.requests.get.return_value = FakeResponse(
            200,
            {
                "status": 0,
                "data": {
                    "items": [
                        {"sn_id": "OTHER-SN", "scooter_name": "Other"},
                        {"sn_id": "TEST-SN", "scooter_name": "Electric moped"},
                    ]
                },
            },
        )
        self.api.scooter_id = 0
        self.api.vehicle_sn = "TEST-SN"

        self.api.initialize()

        self.assertEqual(self.api.scooter_id, 1)
        self.assertEqual(self.api.sn, "TEST-SN")
        self.assertEqual(self.api.sensor_prefix, "Electric moped")

    def test_get_vehicles_reports_empty_account(self) -> None:
        """An account without vehicles should have a specific setup error."""
        api_module.requests.post.return_value = token_response("access")
        api_module.requests.get.return_value = FakeResponse(
            200, {"status": 0, "data": {"items": []}}
        )

        with self.assertRaises(api_module.NiuNoVehiclesError):
            self.api.get_vehicles()


if __name__ == "__main__":
    unittest.main()
