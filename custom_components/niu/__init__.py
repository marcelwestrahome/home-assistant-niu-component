"""niu component."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_AUTH, CONF_SENSORS, DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Niu Smart Plug from a config entry."""

    niu_auth = entry.data.get(CONF_AUTH, None)
    if niu_auth == None:
        return False

    sensors_selected = niu_auth[CONF_SENSORS]
    if len(sensors_selected) < 1:
        _LOGGER.error("You did NOT selected any sensor... cant setup the integration..")
        return False

    if "LastTrackThumb" in sensors_selected:
        PLATFORMS.append("camera")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
