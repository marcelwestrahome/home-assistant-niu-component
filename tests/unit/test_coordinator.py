"""Unit tests for coordinated NIU polling."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

from tests.unit.ha_stubs import clear_niu_modules, install_homeassistant_stubs


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeHass:
    """Home Assistant subset used by the coordinator."""

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class FakeApi:
    """Record all synchronous API operations."""

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


class CoordinatorTest(unittest.IsolatedAsyncioTestCase):
    """Verify one shared and selective polling cycle."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    def setUp(self) -> None:
        install_homeassistant_stubs()
        clear_niu_modules()
        self.coordinator_module = importlib.import_module(
            "custom_components.niu.coordinator"
        )
        self.const = importlib.import_module("custom_components.niu.const")

    async def test_first_refresh_initializes_once_and_deduplicates_endpoints(
        self,
    ) -> None:
        """Several entity groups sharing an endpoint must produce one request."""
        api = FakeApi()
        coordinator = self.coordinator_module.NiuDataUpdateCoordinator(
            FakeHass(),
            None,
            api,
            {
                self.const.SENSOR_TYPE_BAT,
                self.const.SENSOR_TYPE_BAT2,
                self.const.SENSOR_TYPE_MOTO,
                self.const.SENSOR_TYPE_POS,
                self.const.SENSOR_TYPE_DIST,
                self.const.SENSOR_TYPE_TRACK,
            },
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator._async_update_data()

        self.assertEqual(
            api.calls,
            [
                "initialize",
                "battery",
                "motor",
                "track",
                "battery",
                "motor",
                "track",
            ],
        )
        self.assertIs(coordinator.data, api)

    async def test_rate_limit_is_forwarded_as_coordinator_backoff(self) -> None:
        """A Retry-After header should control the next coordinator attempt."""
        api_module = importlib.import_module("custom_components.niu.api")

        class RateLimitedApi(FakeApi):
            def updateBat(self) -> None:
                raise api_module.NiuRateLimitError(420)

        coordinator = self.coordinator_module.NiuDataUpdateCoordinator(
            FakeHass(), None, RateLimitedApi(), {self.const.SENSOR_TYPE_BAT}
        )
        coordinator._initialized = True

        with self.assertRaises(self.coordinator_module.UpdateFailed) as raised:
            await coordinator._async_update_data()

        self.assertEqual(raised.exception.retry_after, 420)

    def test_legacy_battery_sensors_still_require_battery_endpoint(self) -> None:
        """Existing entries with pre-dual-battery names must keep polling."""
        groups = self.coordinator_module.required_sensor_groups(
            ["BatteryCharge", "BatteryGrade"]
        )

        self.assertEqual(groups, {self.const.SENSOR_TYPE_BAT})


if __name__ == "__main__":
    unittest.main()
