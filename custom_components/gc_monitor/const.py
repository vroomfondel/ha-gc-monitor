"""Constants of the GC monitor integration."""

from typing import Final

DOMAIN: Final = "gc_monitor"
WARN_SECONDS: Final = 0.5
FULL_GENERATION: Final = 2
FREEZE_DELAY_SECONDS: Final = 300
CONF_REFREEZE_HOURS: Final = "refreeze_hours"
DEFAULT_REFREEZE_HOURS: Final = 0
MAX_REFREEZE_HOURS: Final = 720
SERVICE_REFREEZE: Final = "refreeze"
