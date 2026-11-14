# GC Monitor for Home Assistant

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vroomfondel&repository=ha-gc-monitor&category=integration)
[![Validate](https://github.com/vroomfondel/ha-gc-monitor/actions/workflows/validate.yml/badge.svg)](https://github.com/vroomfondel/ha-gc-monitor/actions/workflows/validate.yml)

A small custom integration that measures the garbage collector pauses of the Home Assistant core process
and shortens them by freezing the objects that exist after startup.

Symptoms it addresses: Home Assistant freezes for one to several seconds at regular intervals, entities
briefly turn *unavailable*, KNX/IP tunnels get disconnected (`Received DisconnectRequest from tunnelling
server`), and updates of polling integrations run late.

## Why

A full collection (generation 2) of CPython's garbage collector stops every thread of the process until it
is done. Its duration grows with the number of tracked objects. A large Home Assistant instance holds
millions of them, almost all created during startup and alive until the next restart.

On the instance this was written for (Raspberry Pi 4, Home Assistant 2026.11, Python 3.14, about two
million tracked objects) a full collection took 1.8–2.3 s and ran every 2.5–4 minutes. During such a pause
nothing in Home Assistant runs: no automations, no timers, and no acknowledgements from integrations that
talk to devices with tight timeouts.

## How this was found: KNX tunnel disconnects

The starting point was a KNX installation whose entities flickered to *unavailable* a few times a day. The
log of the KNX integration showed, each time:

```
WARNING (KNX Interface) [xknx.log] Received DisconnectRequest from tunnelling server.
```

followed by a successful reconnect a few milliseconds later. Network, gateway and the host were all
ruled out. A debug capture of xknx showed the pattern:

- The gateway (a KNX IP interface in tunnelling mode) sends a `TUNNELLING_REQUEST` and expects the
  `TUNNELLING_ACK` within one second. Without it, it repeats the telegram once and waits another second.
  After that it closes the tunnel with a `DISCONNECT_REQUEST`. This is what the KNXnet/IP specification
  asks for.
- Home Assistant received the request, its repetition and the disconnect within about 20 ms of each
  other, after 2.4–4.2 s in which the whole process had written nothing to the log. The telegrams had
  been waiting in the socket buffer. Heartbeats before and after were answered normally.
- With this integration's pause logger and asyncio debug mode running side by side, the stalls of that
  length reported by asyncio matched generation-2 collections to within a few milliseconds.

So the gateway did nothing wrong: the process was stopped for longer than the two seconds the protocol
allows. A full collection of 1.8 s only breaks the tunnel when a telegram arrives early in the pause or
the pause runs long, which is why it happened only a few times a day and looked random.

If you see the same log line, check for the pattern above: several KNX frames logged within milliseconds
of each other right before the disconnect, and no log output at all in the seconds before. Other
integrations with protocol timeouts of one or two seconds are exposed in the same way.

## What it does

- **Measure:** registers a callback in `gc.callbacks` and logs every full collection with its duration.
- **Freeze:** five minutes after Home Assistant has started, it runs one `gc.collect()` followed by
  `gc.freeze()`. All objects alive at that moment move to the permanent generation and are skipped by
  later collections.
- **Refreeze:** on request or on an interval, it thaws the frozen objects, collects everything once and
  freezes the survivors again. See below.
- **Undo:** removing or disabling the integration calls `gc.unfreeze()`.

Result on the instance above, first hours after the freeze: full collections take 0.1–0.4 s (median
0.13–0.24 s). They run more often, about every 35 seconds, because the trigger depends on the number of
objects that are not frozen. The total pause time per hour is lower than before.

This is a measurement from one installation over a few hours, not a benchmark. Whether the KNX
disconnects are gone for good takes days to tell; this section will be updated.

## Refreeze

Frozen objects are never freed, and objects created after the freeze are collected again on every full
collection. Both can drift over time: memory that became garbage stays allocated, and the unfrozen set
may grow. A refreeze resets both, at the price of one pause of the original length (about two seconds
on the instance above). How much drift there is in practice has not been measured yet.

- **Service:** `gc_monitor.refreeze`, without parameters. Call it from an automation at a time when a
  pause does not hurt, for example at night.
- **Interval:** *Settings → Devices & services → GC Monitor → Configure*, "Refreeze interval in hours".
  `0` (the default) turns it off. The interval counts from the start of Home Assistant, not from a time
  of day; use the service in an automation if you need a fixed time.

```yaml
automation:
  - alias: "GC refreeze at night"
    triggers:
      - trigger: time
        at: "03:30:00"
    actions:
      - action: gc_monitor.refreeze
```

## Trade-offs

- **Frozen objects are never freed.** Whatever was alive at the freeze and becomes garbage later (for
  example after reloading an integration) stays in memory until the next refreeze or restart. Watch the
  memory of the core process if you reload integrations often.
- **Every freeze is one full collection**, so there is a pause of the old length five minutes after
  startup and at every refreeze.
- **It does not fix slow integrations.** Pauses caused by code that blocks the event loop are a different
  problem; enable asyncio debug mode with the `profiler` integration to find those.

## Installation

HACS: use the button at the top, or add this repository as a custom repository of type *Integration*,
install *GC Monitor*, restart
Home Assistant, then add the integration under *Settings → Devices & services*. It works without
configuration; the only option is the refreeze interval.

Manual: copy `custom_components/gc_monitor` into the `custom_components` directory of your configuration
and continue as above.

## Log output

| Message                                                                 | Level   | When                                      |
|-------------------------------------------------------------------------|---------|-------------------------------------------|
| `gc monitor active, threshold=(2000, 10, 10) refreeze_hours=0`          | INFO    | Integration loaded                        |
| `gc freeze done, reason=startup thawed=0 frozen=1702464 collected=…`    | INFO    | Five minutes after startup                |
| `gc freeze done, reason=service …` / `reason=interval …`                | INFO    | Refreeze by service call or interval      |
| `gc generation=2 duration=0.132s collected=… frozen=…`                  | DEBUG   | Every full collection shorter than 0.5 s  |
| `gc generation=… duration=1.881s collected=… frozen=…`                  | WARNING | Any collection that takes 0.5 s or longer |

To see every full collection:

```yaml
logger:
  logs:
    custom_components.gc_monitor: debug
```

## Related

[`bakerkj/ha-gc-manager`](https://github.com/bakerkj/ha-gc-manager) tunes the collector of Home Assistant
as well. This integration is deliberately smaller: it measures, freezes after startup, and can refreeze.

## License

MIT
