"""Minimal Home Assistant stubs for unit testing the custom integration."""

from __future__ import annotations

import sys
import types


class DeviceInfo(dict):
    """Small stand-in for Home Assistant's DeviceInfo mapping."""

    def __init__(self, **kwargs) -> None:
        super().__init__(kwargs)


class UpdateFailed(Exception):
    """Coordinator update failure carrying an optional retry delay."""

    def __init__(self, message: str = "", *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class DataUpdateCoordinator:
    """Small behavioral subset of Home Assistant's coordinator."""

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(
        self, hass, logger, *, config_entry=None, name, update_interval
    ) -> None:
        self.hass = hass
        self.logger = logger
        self.config_entry = config_entry
        self.name = name
        self.update_interval = update_interval
        self.data = None
        self.last_update_success = True

    async def async_config_entry_first_refresh(self) -> None:
        self.data = await self._async_update_data()


class CoordinatorEntity:
    """Small stand-in for CoordinatorEntity."""

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class SensorEntity:
    """SensorEntity stand-in."""


class Camera:
    """Camera stand-in."""

    def __init__(self) -> None:
        self.hass = None


class TimeoutException(Exception):
    """httpx timeout stand-in."""


class RequestError(Exception):
    """httpx request error stand-in."""


class HTTPStatusError(Exception):
    """httpx status error stand-in."""


def install_homeassistant_stubs() -> None:
    """Install only the modules imported by the integration under test."""
    for name in tuple(sys.modules):
        if name == "homeassistant" or name.startswith("homeassistant."):
            del sys.modules[name]

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    camera = types.ModuleType("homeassistant.components.camera")
    camera.Camera = Camera
    sensor = types.ModuleType("homeassistant.components.sensor")
    sensor.SensorEntity = SensorEntity

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = DeviceInfo
    httpx_client = types.ModuleType("homeassistant.helpers.httpx_client")
    httpx_client.get_async_client = lambda hass, verify_ssl=True: None
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.camera": camera,
        "homeassistant.components.sensor": sensor,
        "homeassistant.config_entries": config_entries,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.device_registry": device_registry,
        "homeassistant.helpers.httpx_client": httpx_client,
        "homeassistant.helpers.update_coordinator": update_coordinator,
    }
    sys.modules.update(modules)

    httpx = types.ModuleType("httpx")
    httpx.TimeoutException = TimeoutException
    httpx.RequestError = RequestError
    httpx.HTTPStatusError = HTTPStatusError
    sys.modules["httpx"] = httpx


def clear_niu_modules() -> None:
    """Remove cached integration modules so stubs are applied consistently."""
    for name in tuple(sys.modules):
        if name == "custom_components.niu" or name.startswith("custom_components.niu."):
            del sys.modules[name]
