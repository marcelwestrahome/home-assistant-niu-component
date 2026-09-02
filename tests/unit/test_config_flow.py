"""Unit tests for the NIU config flow."""

from __future__ import annotations

import importlib
import types
import unittest
from unittest.mock import Mock, patch

from tests.unit.ha_stubs import AbortFlow, clear_niu_modules, install_homeassistant_stubs


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
    """Successfully authenticated NIU API object with two vehicles."""

    def __init__(self) -> None:
        self.vehicles = [
            {"sn_id": "FIRST-SN", "scooter_name": "Electric moped"},
            {"sn_id": "SECOND-SN", "scooter_name": "Commuter"},
        ]
        self.get_vehicles = Mock(return_value=self.vehicles)
        self.scooter_id = 0
        self.sn = None
        self.sensor_prefix = ""

    def select_vehicle(self, vehicles, vehicle_sn) -> None:
        for index, vehicle in enumerate(vehicles):
            if vehicle["sn_id"] == vehicle_sn:
                self.scooter_id = index
                self.sn = vehicle_sn
                self.sensor_prefix = vehicle["scooter_name"]
                return
        raise self.api_module.NiuVehicleNotFoundError(vehicle_sn)


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
        FakeApi.api_module = self.api_module
        self.credentials = {
            self.const.CONF_USERNAME: "user@example.com",
            self.const.CONF_PASSWORD: "secret",
        }
        self.vehicle_input = {
            self.const.CONF_VEHICLE: "SECOND-SN",
            self.const.CONF_SENSORS: ["BatteryChargeA", "CurrentSpeed"],
        }

    async def test_success_lists_vehicles_and_creates_selected_entry(self) -> None:
        """Setup should offer account vehicles and save the selected index."""
        api = FakeApi()

        with patch.object(
            self.flow_module.NiuApi, "from_hass", return_value=api
        ) as from_hass:
            vehicle_form = await self.flow.async_step_user(self.credentials)
            result = await self.flow.async_step_vehicle(self.vehicle_input)

        api.get_vehicles.assert_called_once_with()
        from_hass.assert_called_once_with(
            self.flow.hass, "user@example.com", "secret", 0
        )
        self.assertEqual(vehicle_form["type"], "form")
        self.assertEqual(vehicle_form["step_id"], "vehicle")
        options = vehicle_form["data_schema"][self.const.CONF_VEHICLE]["options"]
        self.assertEqual(
            options,
            [
                {
                    "value": "FIRST-SN",
                    "label": "Electric moped (FIRST-SN)",
                },
                {"value": "SECOND-SN", "label": "Commuter (SECOND-SN)"},
            ],
        )
        self.assertEqual(self.flow.unique_id, "SECOND-SN")
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "NIU – Commuter")
        self.assertEqual(
            result["data"],
            {
                self.const.CONF_AUTH: {
                    **self.credentials,
                    self.const.CONF_SCOOTER_ID: 1,
                    self.const.CONF_SENSORS: self.vehicle_input[
                        self.const.CONF_SENSORS
                    ],
                }
            },
        )

    async def test_same_vehicle_cannot_be_configured_twice(self) -> None:
        """A serial number already used by another entry must be rejected."""
        api = FakeApi()
        self.flow.hass.configured_unique_ids.add("SECOND-SN")

        with patch.object(self.flow_module.NiuApi, "from_hass", return_value=api):
            await self.flow.async_step_user(self.credentials)
            with self.assertRaises(AbortFlow):
                await self.flow.async_step_vehicle(self.vehicle_input)

    async def test_api_failures_are_reported_precisely(self) -> None:
        """Authentication, transport, and vehicle errors need different messages."""
        failures = (
            (self.api_module.NiuAuthenticationError("bad credentials"), "invalid_auth"),
            (self.api_module.NiuConnectionError("offline"), "cannot_connect"),
            (self.api_module.NiuServerError(503), "cannot_connect"),
            (self.api_module.NiuRateLimitError(60), "cannot_connect"),
            (self.api_module.NiuNoVehiclesError("empty account"), "no_vehicles"),
            (self.api_module.NiuVehicleNotFoundError(2), "invalid_scooter"),
            (self.api_module.NiuResponseError("bad response"), "unknown"),
        )

        for failure, expected_error in failures:
            with self.subTest(failure=type(failure).__name__):
                api = FakeApi()
                api.get_vehicles.side_effect = failure
                with patch.object(
                    self.flow_module.NiuApi, "from_hass", return_value=api
                ):
                    result = await self.flow.async_step_user(self.credentials)

                self.assertEqual(result["type"], "form")
                self.assertEqual(result["errors"], {"base": expected_error})

    async def test_unexpected_failure_is_logged_and_reported(self) -> None:
        """Unexpected defects must remain visible in logs without breaking the flow."""
        api = FakeApi()
        api.get_vehicles.side_effect = RuntimeError("boom")

        with (
            patch.object(self.flow_module.NiuApi, "from_hass", return_value=api),
            self.assertLogs(self.flow_module._LOGGER, level="ERROR"),
        ):
            result = await self.flow.async_step_user(self.credentials)

        self.assertEqual(result["errors"], {"base": "unknown"})


if __name__ == "__main__":
    unittest.main()
