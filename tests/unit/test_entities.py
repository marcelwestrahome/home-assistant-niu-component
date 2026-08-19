"""Unit tests for coordinator-backed NIU entities."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests.unit.ha_stubs import clear_niu_modules, install_homeassistant_stubs


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeApi:
    """Cached API data exposed to entities."""

    sn = "TEST-SN"
    sensor_prefix = "MQi"

    def __init__(self) -> None:
        self.updateBat = Mock()
        self.updateMoto = Mock()

    def getDataBatA(self, field):
        return {"batteryCharging": 81}.get(field)

    def getDataBatB(self, field):
        return {"batteryCharging": 74}.get(field)

    def getDataMoto(self, field):
        return None

    def getDataPos(self, field):
        return None

    def getDataDist(self, field):
        return None

    def getDataOverall(self, field):
        return None

    def getDataTrack(self, field):
        return None

    def hasSecondBattery(self):
        return True


class FakeCoordinator:
    """Coordinator carrying one shared API object."""

    def __init__(self, api) -> None:
        self.data = api
        self.last_update_success = True


class FakeResponse:
    """Successful still-image response."""

    content = b"image-bytes"

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    """Record image downloads."""

    def __init__(self) -> None:
        self.get = AsyncMock(return_value=FakeResponse())


class EntityTest(unittest.IsolatedAsyncioTestCase):
    """Verify entities consume only coordinator-cached state."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    def setUp(self) -> None:
        install_homeassistant_stubs()
        clear_niu_modules()
        self.const = importlib.import_module("custom_components.niu.const")
        self.sensor_module = importlib.import_module("custom_components.niu.sensor")
        self.camera_module = importlib.import_module("custom_components.niu.camera")
        self.api = FakeApi()
        self.coordinator = FakeCoordinator(self.api)

    def test_sensor_reads_cache_without_triggering_api_update(self) -> None:
        """Reading multiple sensors must not cause duplicate network requests."""
        sensor_a = self.sensor_module.NiuSensor(
            self.coordinator,
            "BatteryChargeA",
            "battery_charge_a",
            "%",
            "batteryCharging",
            self.const.SENSOR_TYPE_BAT,
            "battery",
            "mdi:battery",
        )
        sensor_b = self.sensor_module.NiuSensor(
            self.coordinator,
            "BatteryChargeB",
            "battery_charge_b",
            "%",
            "batteryCharging",
            self.const.SENSOR_TYPE_BAT2,
            "battery",
            "mdi:battery",
        )

        self.assertEqual(sensor_a.native_value, 81)
        self.assertEqual(sensor_b.native_value, 74)
        self.api.updateBat.assert_not_called()
        self.assertEqual(
            sensor_a._attr_device_info["identifiers"],
            {("niu", "Niu E-scooter")},
        )
        self.assertIsInstance(sensor_a._attr_device_info["model"], str)
        self.assertEqual(sensor_a._attr_device_info, sensor_b._attr_device_info)

    async def test_legacy_battery_entities_keep_names_and_unique_ids(self) -> None:
        """Reloading an old config entry must restore its original entities."""
        entry = types.SimpleNamespace(
            entry_id="entry-1",
            data={
                self.const.CONF_AUTH: {
                    self.const.CONF_SENSORS: ["BatteryCharge", "BatteryGrade"]
                }
            },
        )
        hass = types.SimpleNamespace(
            data={self.const.DOMAIN: {entry.entry_id: self.coordinator}}
        )
        async_add_entities = Mock()

        await self.sensor_module.async_setup_entry(hass, entry, async_add_entities)

        entities = async_add_entities.call_args.args[0]
        self.assertEqual(
            [entity._attr_name for entity in entities],
            ["NIU Scooter MQi BatteryCharge", "NIU Scooter MQi BatteryGrade"],
        )
        self.assertEqual(
            [entity._attr_unique_id for entity in entities],
            [
                "sensor.niu_scooter_TEST-SN_battery_charge",
                "sensor.niu_scooter_TEST-SN_battery_grade",
            ],
        )
        self.assertEqual(entities[0].native_value, 81)

    def test_is_charging_keeps_identity_without_power_device_class(self) -> None:
        """A boolean charging state must not claim to be power measured in watts."""
        sensor_config = self.const.SENSOR_TYPES["IsCharging"]
        sensor = self.sensor_module.NiuSensor(
            self.coordinator,
            "IsCharging",
            sensor_config[0],
            sensor_config[1],
            sensor_config[2],
            sensor_config[3],
            sensor_config[4],
            sensor_config[5],
        )

        self.assertEqual(
            sensor._attr_unique_id, "sensor.niu_scooter_TEST-SN_is_charging"
        )
        self.assertIsNone(sensor._attr_device_class)
        self.assertIsNone(sensor._attr_native_unit_of_measurement)

    async def test_camera_uses_plain_camera_and_caches_unchanged_url(self) -> None:
        """The NIU camera should download a thumbnail only when its URL changes."""
        self.api.getDataTrack = Mock(return_value="https://example.test/track.jpg")
        hass = types.SimpleNamespace()
        client = FakeClient()
        camera = self.camera_module.LastTrackCamera(hass, self.coordinator)

        with patch.object(self.camera_module, "get_async_client", return_value=client):
            first = await camera.async_camera_image()
            second = await camera.async_camera_image()

        self.assertEqual(first, b"image-bytes")
        self.assertEqual(second, b"image-bytes")
        self.assertEqual(client.get.call_count, 1)
        self.assertEqual(camera._attr_unique_id, "MQi Last Track Camera")
        self.assertEqual(
            camera._attr_device_info["identifiers"],
            {("niu", "Niu E-scooter")},
        )
        self.assertIsInstance(camera._attr_device_info["model"], str)

    async def test_camera_preserves_cached_image_after_timeout(self) -> None:
        """A transient image failure must not discard the last valid thumbnail."""
        self.api.getDataTrack = Mock(
            side_effect=[
                "https://example.test/first.jpg",
                "https://example.test/second.jpg",
            ]
        )
        hass = types.SimpleNamespace()
        client = FakeClient()
        client.get.side_effect = [
            FakeResponse(),
            self.camera_module.httpx.TimeoutException("timed out"),
        ]
        camera = self.camera_module.LastTrackCamera(hass, self.coordinator)

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            first = await camera.async_camera_image()
            after_timeout = await camera.async_camera_image()

        self.assertEqual(first, b"image-bytes")
        self.assertEqual(after_timeout, b"image-bytes")
        self.assertEqual(client.get.call_count, 2)
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
