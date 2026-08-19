"""Shared NIU entity definitions."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NiuDataUpdateCoordinator


class NiuCoordinatorEntity(CoordinatorEntity[NiuDataUpdateCoordinator]):
    """Base entity attached to a scooter and its shared coordinator."""

    def __init__(self, coordinator: NiuDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        api = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(api.sn))},
            name=api.sensor_prefix,
            manufacturer="NIU",
            model="Vehicle",
        )
