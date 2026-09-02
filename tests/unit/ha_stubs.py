"""Minimal Home Assistant stubs for unit testing the custom integration."""

from __future__ import annotations

import sys
import types


class ConfigFlow:
    """Small stand-in for Home Assistant's config-flow base class."""

    def __init_subclass__(cls, *, domain=None, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain

    async def async_set_unique_id(self, unique_id: str) -> None:
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        if self.unique_id in getattr(self.hass, "configured_unique_ids", set()):
            raise AbortFlow("already_configured")

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, *, step_id, data_schema, errors):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors,
        }


class AbortFlow(Exception):
    """Signal that a config flow should abort."""


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
        self._attr_is_on = True
        self.content_type = "image/jpeg"

    @property
    def is_on(self) -> bool:
        """Mirror Home Assistant's default camera power state."""
        return self._attr_is_on


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
    config_entries.ConfigFlow = ConfigFlow
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    config_entries.ConfigFlowResult = dict
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = DeviceInfo
    device_registry.async_get = lambda hass: hass.device_registry
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda hass: hass.entity_registry
    entity_registry.async_entries_for_config_entry = (
        lambda registry, entry_id: [
            entity
            for entity in registry.entries
            if entity.config_entry_id == entry_id
        ]
    )
    httpx_client = types.ModuleType("homeassistant.helpers.httpx_client")
    httpx_client.get_async_client = lambda hass, verify_ssl=True: None
    selector = types.ModuleType("homeassistant.helpers.selector")

    class SelectSelectorMode:
        LIST = "list"

    class TextSelectorType:
        PASSWORD = "password"

    selector.SelectSelector = lambda config: config
    selector.SelectSelectorConfig = lambda **kwargs: kwargs
    selector.SelectSelectorMode = SelectSelectorMode
    selector.TextSelector = lambda config: config
    selector.TextSelectorConfig = lambda **kwargs: kwargs
    selector.TextSelectorType = TextSelectorType
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
        "homeassistant.helpers.entity_registry": entity_registry,
        "homeassistant.helpers.httpx_client": httpx_client,
        "homeassistant.helpers.selector": selector,
        "homeassistant.helpers.update_coordinator": update_coordinator,
    }
    sys.modules.update(modules)

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda schema: schema
    voluptuous.Required = lambda key, **kwargs: key
    voluptuous.All = lambda *validators: validators
    voluptuous.Coerce = lambda target: target
    voluptuous.Range = lambda **kwargs: kwargs
    sys.modules["voluptuous"] = voluptuous

    requests = types.ModuleType("requests")
    requests.exceptions = types.SimpleNamespace(RequestException=Exception)
    sys.modules["requests"] = requests

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
