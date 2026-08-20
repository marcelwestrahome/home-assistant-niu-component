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
        vol.Required(CONF_SCOOTER_ID, default=DEFAULT_SCOOTER_ID): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
        vol.Required(CONF_SENSORS, default=AVAILABLE_SENSORS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AVAILABLE_SENSORS,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            ),
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the NIU integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate credentials and the selected vehicle before creating an entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api = NiuApi.from_hass(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_SCOOTER_ID],
                )
                await self.hass.async_add_executor_job(api.initialize)
            except NiuAuthenticationError:
                errors["base"] = "invalid_auth"
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
                await self.async_set_unique_id(str(api.sn))
                self._abort_if_unique_id_configured()
                title = (
                    f"NIU – {api.sensor_prefix}"
                    if api.sensor_prefix
                    else "NIU vehicle"
                )
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_AUTH: {
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_SCOOTER_ID: user_input[CONF_SCOOTER_ID],
                            CONF_SENSORS: user_input[CONF_SENSORS],
                        }
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
