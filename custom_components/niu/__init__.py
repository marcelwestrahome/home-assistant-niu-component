"""NIU scooter integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import NiuApi
from .const import (
    CONF_AUTH,
    CONF_PASSWORD,
    CONF_SCOOTER_ID,
    CONF_SENSORS,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import NiuDataUpdateCoordinator, required_sensor_groups

_LOGGER = logging.getLogger(__name__)
LEGACY_DEVICE_IDENTIFIER = (DOMAIN, "Niu E-scooter")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Niu component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NIU from a config entry."""
    niu_auth = entry.data.get(CONF_AUTH)
    if niu_auth is None:
        return False

    sensors_selected = niu_auth.get(CONF_SENSORS, [])
    if not sensors_selected:
        _LOGGER.error("No NIU sensors selected; integration cannot be set up")
        return False

    api = NiuApi.from_hass(
        hass,
        niu_auth[CONF_USERNAME],
        niu_auth[CONF_PASSWORD],
        niu_auth[CONF_SCOOTER_ID],
        entry.unique_id,
    )
    coordinator = NiuDataUpdateCoordinator(
        hass,
        entry,
        api,
        required_sensor_groups(sensors_selected),
    )
    await coordinator.async_config_entry_first_refresh()

    entry_updates = {}
    if entry.unique_id is None:
        entry_updates["unique_id"] = str(api.sn)
    if entry.title == "Niu EScooter Integration":
        entry_updates["title"] = f"NIU – {api.sensor_prefix}"
    if entry_updates:
        hass.config_entries.async_update_entry(entry, **entry_updates)

    _migrate_device_identifier(hass, entry, str(api.sn))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(
        entry, _get_platforms(sensors_selected)
    )

    return True


def _migrate_device_identifier(
    hass: HomeAssistant, entry: ConfigEntry, serial_number: str
) -> None:
    """Replace the old shared device identifier without orphaning its entities."""
    registry = dr.async_get(hass)
    if hasattr(registry, "async_get_device_by_identifier"):
        legacy_device = registry.async_get_device_by_identifier(
            LEGACY_DEVICE_IDENTIFIER, entry.entry_id
        )
    else:
        legacy_device = registry.async_get_device(
            identifiers={LEGACY_DEVICE_IDENTIFIER}
        )
        if legacy_device and entry.entry_id not in legacy_device.config_entries:
            return

    if legacy_device is not None:
        registry.async_update_device(
            legacy_device.id,
            new_identifiers={(DOMAIN, serial_number)},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading NIU config entry")
    niu_auth = entry.data.get(CONF_AUTH, {})
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, _get_platforms(niu_auth.get(CONF_SENSORS, []))
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


def _get_platforms(sensors_selected: list[str]) -> tuple[str, ...]:
    """Return an immutable, per-entry platform list."""
    if "LastTrackThumb" in sensors_selected:
        return ("sensor", "camera")
    return ("sensor",)
