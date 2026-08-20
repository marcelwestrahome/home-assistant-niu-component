"""Unit tests for the NIU config flow."""

from __future__ import annotations

import importlib
import types
import unittest
from unittest.mock import Mock, patch

from tests.unit.ha_stubs import clear_niu_modules, install_homeassistant_stubs


class FakeHass:
    """Home Assistant subset used by the config flow."""

    def __init__(self) -> None:
        self.config = types.SimpleNamespace(
            language="de", country="AT", time_zone="Europe/Vienna"
        )
        self.configured_unique_ids: set[str] = set()

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class FakeApi:
    """Successfully initialized NIU API object."""

    sn = "TEST-SN"
    sensor_prefix = "Flotti"

    def __init__(self) -> None:
        self.initialize = Mock()


class ConfigFlowTest(unittest.IsolatedAsyncioTestCase):
    """Verify validation and error reporting during initial setup."""

    def setUp(self) -> None:
        install_homeassistant_stubs()
        clear_niu_modules()
        self.flow_module = importlib.import_module("custom_components.niu.config_flow")
        self.api_module = importlib.import_module("custom_components.niu.api")
        self.const = importlib.import_module("custom_components.niu.const")
        self.flow = self.flow_module.ConfigFlow()
        self.flow.hass = FakeHass()
        self.user_input = {
            self.const.CONF_USERNAME: "user@example.com",
            self.const.CONF_PASSWORD: "secret",
            self.const.CONF_SCOOTER_ID: 0,
            self.const.CONF_SENSORS: ["BatteryChargeA", "CurrentSpeed"],
        }

    async def test_success_validates_vehicle_and_creates_unique_entry(self) -> None:
        """Setup should validate the selected vehicle before saving credentials."""
        api = FakeApi()

        with patch.object(
            self.flow_module.NiuApi, "from_hass", return_value=api
        ) as from_hass:
            result = await self.flow.async_step_user(self.user_input)

        api.initialize.assert_called_once_with()
        from_hass.assert_called_once_with(
            self.flow.hass, "user@example.com", "secret", 0
        )
        self.assertEqual(self.flow.unique_id, "TEST-SN")
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "NIU – Flotti")
        self.assertEqual(result["data"], {self.const.CONF_AUTH: self.user_input})

    async def test_api_failures_are_reported_precisely(self) -> None:
        """Authentication, transport, and vehicle errors need different messages."""
        failures = (
            (self.api_module.NiuAuthenticationError("bad credentials"), "invalid_auth"),
            (self.api_module.NiuConnectionError("offline"), "cannot_connect"),
            (self.api_module.NiuServerError(503), "cannot_connect"),
            (self.api_module.NiuRateLimitError(60), "cannot_connect"),
            (self.api_module.NiuVehicleNotFoundError(2), "invalid_scooter"),
            (self.api_module.NiuResponseError("bad response"), "unknown"),
        )

        for failure, expected_error in failures:
            with self.subTest(failure=type(failure).__name__):
                api = FakeApi()
                api.initialize.side_effect = failure
                with patch.object(
                    self.flow_module.NiuApi, "from_hass", return_value=api
                ):
                    result = await self.flow.async_step_user(self.user_input)

                self.assertEqual(result["type"], "form")
                self.assertEqual(result["errors"], {"base": expected_error})

    async def test_unexpected_failure_is_logged_and_reported(self) -> None:
        """Unexpected defects must remain visible in logs without breaking the flow."""
        api = FakeApi()
        api.initialize.side_effect = RuntimeError("boom")

        with (
            patch.object(self.flow_module.NiuApi, "from_hass", return_value=api),
            self.assertLogs(self.flow_module._LOGGER, level="ERROR"),
        ):
            result = await self.flow.async_step_user(self.user_input)

        self.assertEqual(result["errors"], {"base": "unknown"})


if __name__ == "__main__":
    unittest.main()
