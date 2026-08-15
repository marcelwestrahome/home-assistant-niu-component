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
        device_name = "Niu E-scooter"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_name)},
            name=device_name,
            manufacturer="NIU",
            model="E-scooter",
        )
