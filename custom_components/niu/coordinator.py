"""Coordinate NIU API polling for all entities in a config entry."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NiuApi, NiuApiError, NiuRateLimitError
from .const import (
    DOMAIN,
    SENSOR_TYPE_BAT,
    SENSOR_TYPE_BAT2,
    SENSOR_TYPE_DIST,
    SENSOR_TYPE_MOTO,
    SENSOR_TYPE_OVERALL,
    SENSOR_TYPE_POS,
    SENSOR_TYPE_TRACK,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=150)
DEFAULT_RATE_LIMIT_BACKOFF = 300
MIN_RATE_LIMIT_BACKOFF = 30
MAX_RATE_LIMIT_BACKOFF = 3600


def required_sensor_groups(sensors_selected: list[str]) -> set[str]:
    """Return the API data groups needed by the selected entities."""
    return {
        SENSOR_TYPES[sensor][3]
        for sensor in sensors_selected
        if sensor in SENSOR_TYPES
    }


class NiuDataUpdateCoordinator(DataUpdateCoordinator[NiuApi]):
    """Fetch each required NIU endpoint once per polling cycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: NiuApi,
        sensor_groups: set[str],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
        )
        self.api = api
        self.sensor_groups = frozenset(sensor_groups)
        self._initialized = False

    def _sync_update_data(self) -> NiuApi:
        """Initialize once, then update each required endpoint exactly once."""
        if not self._initialized:
            _LOGGER.debug("Initializing shared NIU API client")
            self.api.initialize()
            self._initialized = True

        _LOGGER.debug(
            "Updating NIU data groups: %s", ", ".join(sorted(self.sensor_groups))
        )
        if self.sensor_groups & {SENSOR_TYPE_BAT, SENSOR_TYPE_BAT2}:
            self.api.updateBat()
        if self.sensor_groups & {
            SENSOR_TYPE_MOTO,
            SENSOR_TYPE_POS,
            SENSOR_TYPE_DIST,
        }:
            self.api.updateMoto()
        if SENSOR_TYPE_OVERALL in self.sensor_groups:
            self.api.updateMotoInfo()
        if SENSOR_TYPE_TRACK in self.sensor_groups:
            self.api.updateTrackInfo()
        return self.api

    async def _async_update_data(self) -> NiuApi:
        """Fetch NIU data without blocking Home Assistant's event loop."""
        try:
            return await self.hass.async_add_executor_job(self._sync_update_data)
        except NiuRateLimitError as err:
            retry_after = err.retry_after or DEFAULT_RATE_LIMIT_BACKOFF
            retry_after = max(
                MIN_RATE_LIMIT_BACKOFF,
                min(retry_after, MAX_RATE_LIMIT_BACKOFF),
            )
            raise UpdateFailed(
                "NIU API rate limit exceeded", retry_after=retry_after
            ) from err
        except NiuApiError as err:
            raise UpdateFailed(f"NIU API update failed: {err}") from err
        except Exception as err:
            raise UpdateFailed("Unexpected error while updating NIU data") from err
