"""Unit tests for coordinator-backed NIU entities."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests.unit.ha_stubs import clear_niu_modules, install_homeassistant_stubs

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PNG_IMAGE = b"\x89PNG\r\n\x1a\nimage-bytes"
NIU_IMAGE_FAILURE = b'{"data":null,"desc":"img fail","status":200}'


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

    def __init__(
        self,
        content: bytes = PNG_IMAGE,
        content_type: str | None = "image/jpeg",
    ) -> None:
        self.content = content
        self.headers = {}
        if content_type is not None:
            self.headers["content-type"] = content_type

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

    async def test_camera_uses_plain_camera_and_caches_unchanged_url(self) -> None:
        """The NIU camera should download a thumbnail only when its URL changes."""
        self.api.getDataTrack = Mock(return_value="https://example.test/track.jpg")
        hass = types.SimpleNamespace()
        client = FakeClient()
        camera = self.camera_module.LastTrackCamera(hass, self.coordinator)

        with patch.object(self.camera_module, "get_async_client", return_value=client):
            first = await camera.async_camera_image()
            second = await camera.async_camera_image()

        self.assertEqual(first, PNG_IMAGE)
        self.assertEqual(second, PNG_IMAGE)
        self.assertEqual(client.get.call_count, 1)
        self.assertEqual(camera._attr_unique_id, "MQi Last Track Camera")
        self.assertEqual(
            camera._attr_device_info["identifiers"],
            {("niu", "Niu E-scooter")},
        )
        self.assertIsInstance(camera._attr_device_info["model"], str)

    async def test_camera_is_on_before_first_thumbnail_download(self) -> None:
        """The camera proxy must be usable before its first image request."""
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        self.assertTrue(camera.is_on)

    async def test_camera_reports_missing_track_thumbnail(self) -> None:
        """Missing NIU track data should be visible in debug logs."""
        client = FakeClient()
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module._LOGGER, "debug") as debug,
        ):
            image = await camera.async_camera_image()

        self.assertIsNone(image)
        client.get.assert_not_called()
        debug.assert_called_once_with("No NIU last-track thumbnail URL available")

    async def test_camera_rejects_non_image_response(self) -> None:
        """An HTML error document must not be exposed as a camera image."""
        self.api.getDataTrack = Mock(return_value="https://example.test/track.jpg")
        client = FakeClient()
        client.get.return_value = FakeResponse(b"<html>error</html>", "text/html")
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            image = await camera.async_camera_image()

        self.assertIsNone(image)
        warning.assert_called_once_with(
            "NIU last-track thumbnail returned invalid content type: %s",
            "text/html",
        )

    async def test_camera_uses_thumbnail_response_content_type(self) -> None:
        """Home Assistant should serve the thumbnail with its detected media type."""
        self.api.getDataTrack = Mock(return_value="https://example.test/track.png")
        client = FakeClient()
        client.get.return_value = FakeResponse(PNG_IMAGE, "image/jpeg; charset=binary")
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with patch.object(self.camera_module, "get_async_client", return_value=client):
            image = await camera.async_camera_image()

        self.assertEqual(image, PNG_IMAGE)
        self.assertEqual(camera.content_type, "image/png")

    async def test_camera_falls_back_after_niu_img_fail_response(self) -> None:
        """The domestic CDN URL should be tried after NIU's overseas URL fails."""
        overseas_url = (
            "https://app-api-fk.niu.com/track/overseas/thumb/ride.png?token=test"
        )
        domestic_url = "https://app-api.niucache.com/track/thumb/ride.png?token=test"
        self.api.getDataTrack = Mock(return_value=overseas_url)
        client = FakeClient()
        client.get.side_effect = [
            FakeResponse(NIU_IMAGE_FAILURE, "image/png"),
            FakeResponse(PNG_IMAGE, "image/png"),
        ]
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            image = await camera.async_camera_image()

        self.assertEqual(image, PNG_IMAGE)
        self.assertEqual(
            [call.args[0] for call in client.get.await_args_list],
            [overseas_url, domestic_url],
        )
        warning.assert_called_once_with(
            "NIU last-track thumbnail returned invalid image data: %s",
            "NIU status 200: img fail",
        )

    def test_camera_builds_fallbacks_for_unknown_niu_cdn_host(self) -> None:
        """A new NIU CDN hostname should still use the known track path fallbacks."""
        source_url = "https://cdn-new.niu.test/track/thumb/ride.png?token=test"

        candidates = self.camera_module._thumbnail_url_candidates(source_url)

        self.assertEqual(candidates[0], source_url)
        self.assertIn(
            "https://app-api.niucache.com/track/thumb/ride.png?token=test",
            candidates,
        )
        self.assertIn(
            "https://app-api-fk.niu.com/track/overseas/thumb/ride.png?token=test",
            candidates,
        )

    def test_camera_prefers_verified_domestic_paths_for_niu_gateway(self) -> None:
        """The working domestic thumbnail path must precede overseas fallbacks."""
        source_url = (
            "https://s.niucache.com/app-api-fk/v5/track/overseas/thumb/"
            "TEST-SN/test-ride/image.png?token=test"
        )

        candidates = self.camera_module._thumbnail_url_candidates(source_url)

        self.assertEqual(
            candidates,
            [
                "https://s.niucache.com/app-api-fk/v5/track/thumb/"
                "TEST-SN/test-ride/image.png?token=test",
                source_url,
                "https://app-api-fk.niu.com/v5/track/thumb/"
                "TEST-SN/test-ride/image.png?token=test",
                "https://app-api-fk.niu.com/v5/track/overseas/thumb/"
                "TEST-SN/test-ride/image.png?token=test",
            ],
        )

    async def test_camera_throttles_retries_after_invalid_image(self) -> None:
        """Repeated proxy requests must not repeatedly hit a failing NIU URL."""
        self.api.getDataTrack = Mock(return_value="https://example.test/track.png")
        client = FakeClient()
        client.get.return_value = FakeResponse(NIU_IMAGE_FAILURE, "image/png")
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module, "monotonic", side_effect=[100, 100, 110]),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            first = await camera.async_camera_image()
            second = await camera.async_camera_image()

        self.assertIsNone(first)
        self.assertIsNone(second)
        client.get.assert_awaited_once()
        warning.assert_called_once_with(
            "NIU last-track thumbnail returned invalid image data: %s",
            "NIU status 200: img fail",
        )

    async def test_camera_rejects_empty_image_response(self) -> None:
        """An empty CDN response must not replace a usable camera image."""
        self.api.getDataTrack = Mock(return_value="https://example.test/track.jpg")
        client = FakeClient()
        client.get.return_value = FakeResponse(b"")
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            image = await camera.async_camera_image()

        self.assertIsNone(image)
        warning.assert_called_once_with(
            "NIU last-track thumbnail returned an empty response"
        )

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

        self.assertEqual(first, PNG_IMAGE)
        self.assertEqual(after_timeout, PNG_IMAGE)
        self.assertEqual(client.get.call_count, 2)
        warning.assert_called_once()

    async def test_camera_limits_total_fallback_time_and_throttles_retry(
        self,
    ) -> None:
        """A hanging CDN must finish before HA's proxy timeout and start backoff."""
        self.api.getDataTrack = Mock(
            return_value="https://example.test/track/overseas/thumb/ride.png"
        )
        client = FakeClient()

        async def never_finishes(*args, **kwargs):
            await asyncio.sleep(1)

        client.get.side_effect = never_finishes
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module, "GET_IMAGE_TOTAL_TIMEOUT", 0.01),
            patch.object(self.camera_module, "monotonic", side_effect=[100, 100, 110]),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            first = await camera.async_camera_image()
            second = await camera.async_camera_image()

        self.assertIsNone(first)
        self.assertIsNone(second)
        client.get.assert_awaited_once()
        warning.assert_called_once_with(
            "Timed out while fetching NIU last-track thumbnail candidates"
        )

    async def test_camera_does_not_log_private_thumbnail_url_on_http_error(
        self,
    ) -> None:
        """HTTP failures must not expose scooter or ride identifiers in logs."""
        private_url = (
            "https://s.niucache.com/app-api-fk/v5/track/overseas/thumb/"
            "PRIVATE-SERIAL/PRIVATE-RIDE/image.png"
        )
        self.api.getDataTrack = Mock(return_value=private_url)
        client = FakeClient()
        error = self.camera_module.httpx.HTTPStatusError(
            f"not found for URL {private_url}"
        )
        error.response = types.SimpleNamespace(status_code=404)
        client.get.side_effect = error
        camera = self.camera_module.LastTrackCamera(
            types.SimpleNamespace(), self.coordinator
        )

        with (
            patch.object(self.camera_module, "get_async_client", return_value=client),
            patch.object(self.camera_module._LOGGER, "warning") as warning,
        ):
            image = await camera.async_camera_image()

        self.assertIsNone(image)
        log_output = " ".join(str(call) for call in warning.call_args_list)
        self.assertNotIn("PRIVATE-SERIAL", log_output)
        self.assertNotIn("PRIVATE-RIDE", log_output)
        self.assertTrue(
            any(
                "HTTP %s" in call.args[0] and call.args[-1] == 404
                for call in warning.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
