"""Log garbage collector pauses of the Home Assistant core process."""

import gc
import logging
import time
from datetime import datetime
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import CONF_REFREEZE_HOURS
from .const import DEFAULT_REFREEZE_HOURS
from .const import DOMAIN
from .const import FREEZE_DELAY_SECONDS
from .const import FULL_GENERATION
from .const import SERVICE_REFREEZE
from .const import WARN_SECONDS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class GcPauseLogger:
    """Callback for ``gc.callbacks`` that logs full collections and long pauses."""

    def __init__(self) -> None:
        """Initialise the start timestamp."""
        self._started = 0.0

    def __call__(self, phase: str, info: dict[str, int]) -> None:
        """Record the start of a collection and log its duration at the end.

        Args:
            phase: ``start`` or ``stop`` as passed by the interpreter.
            info: Collection details with ``generation``, ``collected`` and ``uncollectable``.
        """
        if phase == "start":
            self._started = time.perf_counter()
            return
        duration = time.perf_counter() - self._started
        if info["generation"] < FULL_GENERATION and duration < WARN_SECONDS:
            return
        _LOGGER.log(
            logging.WARNING if duration >= WARN_SECONDS else logging.DEBUG,
            "gc generation=%s duration=%.3fs collected=%s uncollectable=%s frozen=%s",
            info["generation"],
            duration,
            info["collected"],
            info["uncollectable"],
            gc.get_freeze_count(),
        )


def collect_and_freeze(reason: str) -> None:
    """Thaw frozen objects, collect everything once and freeze the survivors.

    Args:
        reason: Trigger written to the log.
    """
    started = time.perf_counter()
    thawed = gc.get_freeze_count()
    gc.unfreeze()
    collected = gc.collect()
    gc.freeze()
    _LOGGER.info(
        "gc freeze done, reason=%s thawed=%s frozen=%s collected=%s duration=%.3fs",
        reason,
        thawed,
        gc.get_freeze_count(),
        collected,
        time.perf_counter() - started,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the refreeze service.

    Args:
        hass: Home Assistant instance.
        config: YAML configuration, unused.

    Returns:
        Always ``True``.
    """

    @callback
    def _handle_refreeze(call: ServiceCall) -> None:
        if DOMAIN not in hass.data:
            raise ServiceValidationError("GC Monitor is not loaded")
        collect_and_freeze("service")

    hass.services.async_register(DOMAIN, SERVICE_REFREEZE, _handle_refreeze)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register the pause logger and schedule the freeze after startup.

    Args:
        hass: Home Assistant instance.
        entry: Config entry of this integration.

    Returns:
        Always ``True``.
    """
    pause_logger = GcPauseLogger()
    hass.data[DOMAIN] = pause_logger
    gc.callbacks.append(pause_logger)
    hours = int(entry.options.get(CONF_REFREEZE_HOURS, DEFAULT_REFREEZE_HOURS))
    _LOGGER.info("gc monitor active, threshold=%s refreeze_hours=%s", gc.get_threshold(), hours)

    @callback
    def _startup_freeze(now: datetime) -> None:
        collect_and_freeze("startup")

    @callback
    def _interval_freeze(now: datetime) -> None:
        collect_and_freeze("interval")

    @callback
    def _schedule(hass: HomeAssistant) -> None:
        entry.async_on_unload(async_call_later(hass, FREEZE_DELAY_SECONDS, _startup_freeze))
        if hours > 0:
            entry.async_on_unload(async_track_time_interval(hass, _interval_freeze, timedelta(hours=hours)))

    entry.async_on_unload(async_at_started(hass, _schedule))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after an options change.

    Args:
        hass: Home Assistant instance.
        entry: Config entry of this integration.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the pause logger and thaw frozen objects.

    Args:
        hass: Home Assistant instance.
        entry: Config entry of this integration.

    Returns:
        Always ``True``.
    """
    pause_logger = hass.data.pop(DOMAIN, None)
    if pause_logger in gc.callbacks:
        gc.callbacks.remove(pause_logger)
    gc.unfreeze()
    return True
