"""Log garbage collector pauses of the Home Assistant core process."""

import gc
import logging
import time
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .const import FREEZE_DELAY_SECONDS
from .const import FULL_GENERATION
from .const import WARN_SECONDS

_LOGGER = logging.getLogger(__name__)


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


@callback
def _freeze(now: datetime) -> None:
    """Collect once and move all surviving objects to the permanent generation.

    Args:
        now: Fire time passed by the scheduler.
    """
    if gc.get_freeze_count():
        return
    started = time.perf_counter()
    collected = gc.collect()
    gc.freeze()
    _LOGGER.info(
        "gc freeze done, frozen=%s collected=%s duration=%.3fs",
        gc.get_freeze_count(),
        collected,
        time.perf_counter() - started,
    )


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
    _LOGGER.info("gc monitor active, threshold=%s", gc.get_threshold())

    @callback
    def _schedule(hass: HomeAssistant) -> None:
        entry.async_on_unload(async_call_later(hass, FREEZE_DELAY_SECONDS, _freeze))

    entry.async_on_unload(async_at_started(hass, _schedule))
    return True


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
