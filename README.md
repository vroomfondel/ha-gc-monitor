# GC Monitor for Home Assistant

A small custom integration that measures the garbage collector pauses of the Home Assistant core process
and shortens them by freezing the objects that exist after startup.

## Why

A full collection (generation 2) of CPython's garbage collector stops every thread of the process until it
is done. Its duration grows with the number of tracked objects. A large Home Assistant instance holds
millions of them, almost all created during startup and alive until the next restart.

On the instance this was written for (Raspberry Pi 4, Home Assistant 2026.11, Python 3.14, about two
million tracked objects) a full collection took 1.8–2.3 s and ran every 2.5–4 minutes. During such a pause
nothing in Home Assistant runs: no automations, no timers, and no acknowledgements from integrations that
talk to devices with tight timeouts.

## What it does

- **Measure:** registers a callback in `gc.callbacks` and logs every full collection with its duration.
- **Freeze:** five minutes after Home Assistant has started, it runs one `gc.collect()` followed by
  `gc.freeze()`. All objects alive at that moment move to the permanent generation and are skipped by
  later collections.
- **Undo:** removing or disabling the integration calls `gc.unfreeze()`.

Result on the instance above, first hours after the freeze: full collections take 0.1–0.4 s (median
0.13–0.24 s). They run more often, about every 35 seconds, because the trigger depends on the number of
objects that are not frozen. The total pause time per hour is lower than before.

This is a measurement from one installation over a few hours, not a benchmark.

## Trade-offs

- **Frozen objects are never freed.** Whatever was alive at the freeze and becomes garbage later (for
  example after reloading an integration) stays in memory until Home Assistant restarts. Watch the memory
  of the core process if you reload integrations often.
- **The freeze itself is one full collection**, so there is a single pause of the old length five minutes
  after startup.
- **It does not fix slow integrations.** Pauses caused by code that blocks the event loop are a different
  problem; enable asyncio debug mode with the `profiler` integration to find those.

## Installation

HACS: add this repository as a custom repository of type *Integration*, install *GC Monitor*, restart
Home Assistant, then add the integration under *Settings → Devices & services*. There is nothing to
configure.

Manual: copy `custom_components/gc_monitor` into the `custom_components` directory of your configuration
and continue as above.

## Log output

| Message                                                          | Level   | When                                       |
|------------------------------------------------------------------|---------|--------------------------------------------|
| `gc monitor active, threshold=(2000, 10, 10)`                    | INFO    | Integration loaded                         |
| `gc freeze done, frozen=1702464 collected=66166 duration=1.839s` | INFO    | Five minutes after startup                 |
| `gc generation=2 duration=0.132s collected=… frozen=…`           | DEBUG   | Every full collection shorter than 0.5 s   |
| `gc generation=… duration=1.881s collected=… frozen=…`           | WARNING | Any collection that takes 0.5 s or longer  |

To see every full collection:

```yaml
logger:
  logs:
    custom_components.gc_monitor: debug
```

## Related

[`bakerkj/ha-gc-manager`](https://github.com/bakerkj/ha-gc-manager) tunes the collector of Home Assistant
as well. This integration is deliberately smaller: it measures, freezes once, and has no options.

## License

MIT
