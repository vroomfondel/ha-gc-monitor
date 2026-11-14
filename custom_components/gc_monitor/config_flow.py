"""Config flow of the GC monitor integration."""

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN


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
