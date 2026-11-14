"""Config flow of the GC monitor integration."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigFlow
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.config_entries import OptionsFlow
from homeassistant.core import callback

from .const import CONF_REFREEZE_HOURS
from .const import DEFAULT_REFREEZE_HOURS
from .const import DOMAIN
from .const import MAX_REFREEZE_HOURS


class GcMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single config entry without asking for input."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the entry.

        Args:
            user_input: Unused form data.

        Returns:
            The created entry.
        """
        return self.async_create_entry(title="GC Monitor", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow.

        Args:
            config_entry: Config entry of this integration.

        Returns:
            The options flow handler.
        """
        return GcMonitorOptionsFlow()


class GcMonitorOptionsFlow(OptionsFlow):
    """Edit the refreeze interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show and store the options.

        Args:
            user_input: Submitted form data, ``None`` on first display.

        Returns:
            The form or the created options entry.
        """
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_REFREEZE_HOURS, DEFAULT_REFREEZE_HOURS)
        schema = vol.Schema(
            {
                vol.Required(CONF_REFREEZE_HOURS, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=MAX_REFREEZE_HOURS)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
