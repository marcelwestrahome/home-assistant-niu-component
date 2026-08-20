"""Unit tests for NIU config-entry lifecycle handling."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from tests.unit.ha_stubs import clear_niu_modules, install_homeassistant_stubs


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeApi:
    """API object created once for a config entry."""

    sn = "TEST-SN"
    sensor_prefix = "MQi"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def initialize(self) -> None:
        self.calls.append("initialize")

    def updateBat(self) -> None:
        self.calls.append("battery")

    def updateMoto(self) -> None:
        self.calls.append("motor")

    def updateMotoInfo(self) -> None:
        self.calls.append("overall")

    def updateTrackInfo(self) -> None:
        self.calls.append("track")


class FakeConfigEntries:
    """Record forwarded and unloaded platforms."""

    def __init__(self) -> None:
        self.forwarded: list[tuple[str, ...]] = []
        self.unloaded: list[tuple[str, ...]] = []
        self.updated: list[dict[str, str]] = []

    def async_update_entry(self, entry, **changes) -> None:
        self.updated.append(changes)
        for key, value in changes.items():
            setattr(entry, key, value)

    async def async_forward_entry_setups(self, entry, platforms) -> None:
        self.forwarded.append(tuple(platforms))

    async def async_unload_platforms(self, entry, platforms) -> bool:
        self.unloaded.append(tuple(platforms))
        return True


class FakeHass:
    """Home Assistant subset used during config-entry setup."""

    def __init__(self) -> None:
        self.data = {}
        self.config_entries = FakeConfigEntries()
        self.config = types.SimpleNamespace(
            language="de",
            country="AT",
            time_zone="Europe/Vienna",
        )

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class ComponentTest(unittest.IsolatedAsyncioTestCase):
    """Verify setup and reload use entry-local immutable state."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    def setUp(self) -> None:
        install_homeassistant_stubs()
        clear_niu_modules()
        self.component = importlib.import_module("custom_components.niu")
        self.const = importlib.import_module("custom_components.niu.const")

    async def test_setup_and_reload_share_one_api_and_stable_platforms(self) -> None:
        """Reloading must not retain or duplicate a mutable platform list."""
        auth = {
            self.const.CONF_USERNAME: "user@example.com",
            self.const.CONF_PASSWORD: "secret",
            self.const.CONF_SCOOTER_ID: 0,
            self.const.CONF_SENSORS: ["BatteryChargeA", "LastTrackThumb"],
        }
        entry = types.SimpleNamespace(
            entry_id="entry-1",
            data={self.const.CONF_AUTH: auth},
            unique_id=None,
            title="Niu EScooter Integration",
        )
        hass = FakeHass()
        first_api = FakeApi()
        second_api = FakeApi()

        with patch.object(
            self.component.NiuApi,
            "from_hass",
            side_effect=[first_api, second_api],
        ) as from_hass:
            self.assertTrue(await self.component.async_setup_entry(hass, entry))
            first_coordinator = hass.data[self.const.DOMAIN][entry.entry_id]
            self.assertIs(first_coordinator.data, first_api)
            self.assertTrue(await self.component.async_unload_entry(hass, entry))
            self.assertTrue(await self.component.async_setup_entry(hass, entry))

        self.assertEqual(from_hass.call_count, 2)
        self.assertEqual(first_api.calls, ["initialize", "battery", "track"])
        self.assertEqual(second_api.calls, ["initialize", "battery", "track"])
        self.assertEqual(
            hass.config_entries.forwarded,
            [("sensor", "camera"), ("sensor", "camera")],
        )
        self.assertEqual(hass.config_entries.unloaded, [("sensor", "camera")])
        self.assertEqual(
            hass.config_entries.updated,
            [{"unique_id": "TEST-SN", "title": "NIU – MQi"}],
        )

    async def test_setup_preserves_existing_metadata(self) -> None:
        """Setup must not overwrite an existing unique ID or a custom title."""
        auth = {
            self.const.CONF_USERNAME: "user@example.com",
            self.const.CONF_PASSWORD: "secret",
            self.const.CONF_SCOOTER_ID: 0,
            self.const.CONF_SENSORS: ["BatteryChargeA"],
        }
        entry = types.SimpleNamespace(
            entry_id="entry-1",
            data={self.const.CONF_AUTH: auth},
            unique_id="EXISTING-SN",
            title="My Scooter",
        )
        hass = FakeHass()

        with patch.object(
            self.component.NiuApi, "from_hass", return_value=FakeApi()
        ):
            self.assertTrue(await self.component.async_setup_entry(hass, entry))

        self.assertEqual(hass.config_entries.updated, [])


if __name__ == "__main__":
    unittest.main()
