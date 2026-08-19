"""Last-track camera for the NIU integration."""

from __future__ import annotations

import logging

import httpx

from homeassistant.components.camera import Camera
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN
from .coordinator import NiuDataUpdateCoordinator
from .entity import NiuCoordinatorEntity

_LOGGER = logging.getLogger(__name__)
GET_IMAGE_TIMEOUT = 10


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the last-track camera from a config entry."""
    coordinator: NiuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LastTrackCamera(hass, coordinator)])


class LastTrackCamera(NiuCoordinatorEntity, Camera):
    """Still-image camera showing the latest NIU track thumbnail."""

    def __init__(self, hass, coordinator: NiuDataUpdateCoordinator) -> None:
        NiuCoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self.hass = hass
        self._api = coordinator.data
        self._attr_name = f"{self._api.sensor_prefix} Last Track Camera"
        # Preserve GenericCamera's previous identifier to avoid a duplicate entity.
        self._attr_unique_id = self._attr_name
        self._attr_is_streaming = False
        self._last_url: str | None = None
        self._last_image: bytes | None = None

    @property
    def is_on(self) -> bool:
        """Return whether a track thumbnail has been downloaded."""
        return self._last_image is not None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the cached image or download it when the URL changed."""
        last_track_url = self._api.getDataTrack("track_thumb")
        if not last_track_url:
            return self._last_image
        if last_track_url == self._last_url and self._last_image is not None:
            return self._last_image

        try:
            client = get_async_client(self.hass, verify_ssl=True)
            response = await client.get(
                last_track_url,
                timeout=GET_IMAGE_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            _LOGGER.warning("Timeout while fetching NIU last-track image")
            return self._last_image
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.warning("Could not fetch NIU last-track image: %s", err)
            return self._last_image

        self._last_image = response.content
        self._last_url = last_track_url
        return self._last_image
