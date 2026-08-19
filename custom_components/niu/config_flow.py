"""Config flow for the NIU integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .api import (
    NiuApi,
    NiuAuthenticationError,
    NiuConnectionError,
    NiuHttpError,
    NiuNoVehiclesError,
    NiuRateLimitError,
    NiuResponseError,
    NiuServerError,
    NiuVehicleNotFoundError,
)
from .const import (
    AVAILABLE_SENSORS,
    CONF_AUTH,
    CONF_PASSWORD,
    CONF_SCOOTER_ID,
    CONF_SENSORS,
    CONF_USERNAME,
    CONF_VEHICLE,
    DEFAULT_SCOOTER_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the NIU integration."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._api: NiuApi | None = None
        self._vehicles: list[dict[str, Any]] = []
        self._credentials: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate credentials and load vehicles from the configured NIU account."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api = NiuApi.from_hass(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    DEFAULT_SCOOTER_ID,
                )
                vehicles = await self.hass.async_add_executor_job(api.get_vehicles)
            except NiuAuthenticationError:
                errors["base"] = "invalid_auth"
            except NiuNoVehiclesError:
                errors["base"] = "no_vehicles"
            except (NiuConnectionError, NiuServerError, NiuRateLimitError):
                errors["base"] = "cannot_connect"
            except NiuVehicleNotFoundError:
                errors["base"] = "invalid_scooter"
            except (NiuHttpError, NiuResponseError):
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected error while validating NIU account")
                errors["base"] = "unknown"
            else:
                self._api = api
                self._vehicles = vehicles
                self._credentials = user_input
                return await self.async_step_vehicle()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a vehicle returned for the configured NIU account."""
        if self._api is None or not self._vehicles:
            return await self.async_step_user()

        errors: dict[str, str] = {}
        if user_input is not None:
            vehicle_sn = user_input[CONF_VEHICLE]
            try:
                self._api.select_vehicle(self._vehicles, vehicle_sn)
            except NiuVehicleNotFoundError:
                errors["base"] = "invalid_scooter"
            else:
                await self.async_set_unique_id(str(self._api.sn))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NIU – {self._api.sensor_prefix}",
                    data={
                        CONF_AUTH: {
                            **self._credentials,
                            CONF_SCOOTER_ID: self._api.scooter_id,
                            CONF_SENSORS: user_input[CONF_SENSORS],
                        }
                    },
                )

        options = [
            {
                "value": str(vehicle.get("sn_id")),
                "label": f"{vehicle.get('scooter_name')} ({vehicle.get('sn_id')})",
            }
            for vehicle in self._vehicles
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_VEHICLE): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options)
                ),
                vol.Required(
                    CONF_SENSORS, default=AVAILABLE_SENSORS
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=AVAILABLE_SENSORS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
            }
        )
        return self.async_show_form(
            step_id="vehicle", data_schema=schema, errors=errors
        )
