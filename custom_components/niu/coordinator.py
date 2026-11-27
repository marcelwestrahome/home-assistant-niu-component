"""Coordinate NIU API polling for all entities in a config entry."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NiuApi,
    NiuApiError,
    NiuHttpError,
    NiuRateLimitError,
    NiuResponseError,
    NiuServerError,
)
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
        self._failed_groups: set[str] = set()

    def _sync_update_data(self) -> NiuApi:
        """Initialize once, then update each required endpoint exactly once."""
        if not self._initialized:
            _LOGGER.debug("Initializing shared NIU API client")
            self.api.initialize()
            self._initialized = True

        _LOGGER.debug(
            "Updating NIU data groups: %s", ", ".join(sorted(self.sensor_groups))
        )
        attempted: dict[str, bool] = {}
        first_error: NiuApiError | None = None

        updates = (
            ("battery", {SENSOR_TYPE_BAT, SENSOR_TYPE_BAT2}, self.api.updateBat),
            (
                "scooter",
                {SENSOR_TYPE_MOTO, SENSOR_TYPE_POS, SENSOR_TYPE_DIST},
                self.api.updateMoto,
            ),
            ("totals", {SENSOR_TYPE_OVERALL}, self.api.updateMotoInfo),
            ("track", {SENSOR_TYPE_TRACK}, self.api.updateTrackInfo),
        )
        for name, groups, update in updates:
            if not self.sensor_groups & groups:
                continue
            try:
                update()
            except (NiuResponseError, NiuHttpError, NiuServerError) as err:
                # NIU sometimes rejects a single endpoint (e.g. status 1131) while
                # the others keep working. Keep that endpoint's last data and carry
                # on, so one bad endpoint doesn't take every entity down.
                attempted[name] = False
                first_error = first_error or err
                if name not in self._failed_groups:
                    _LOGGER.warning("NIU %s data update failed: %s", name, err)
                self._failed_groups.add(name)
            else:
                attempted[name] = True
                if name in self._failed_groups:
                    _LOGGER.info("NIU %s data update recovered", name)
                    self._failed_groups.discard(name)

        if attempted and not any(attempted.values()) and first_error is not None:
            raise first_error
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
