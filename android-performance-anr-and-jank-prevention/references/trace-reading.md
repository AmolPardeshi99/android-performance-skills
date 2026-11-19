# Reading an ANR trace

## Contents
- Workflow
- Main thread states
- Lock chains
- The "ANR in" CPU block
- App defect, overload, or external
- Reading a cluster, not one trace

## Workflow

1. Find the exact time: search the event log for `am_anr`.
2. Find `ANR in <process>`: reason, load averages, CPU use per process before and during.
3. Open the trace file for that time and find `"main"`.
4. Read the main stack top-down. Note the state and the first frame in app or SDK code.
5. Follow any `waiting to lock <0x...> held by thread N` to thread N and read its stack.
6. Look at the 5 to 10 seconds before `am_anr` in logcat: `Slow operation`, `Slow dispatch`,
   `Slow delivery`, `dvm_lock_sample`, app launches, screen on/off, OEM freeze or unfreeze lines.
7. If still unclear, go to [perfetto.md](perfetto.md).

## Main thread states

| State in trace | Meaning | Next step |
|---|---|---|
| `Native`, top frame `nativePollOnce` | Looper idle. The slow work already finished, or the event never arrived | Look for overload or external causes; the stack itself is not the culprit |
| `Native`, top frame `BinderProxy.transact` | Waiting on another process | Find which service; check system_server load; see [threading-and-locks.md](threading-and-locks.md) |
| `Runnable` | Running Java or Kotlin code | The frames are the suspect; confirm with a cluster |
| `Blocked` | Waiting for a monitor | Follow the lock owner |
| `Waiting` / `TimedWaiting` | `Object.wait`, `park`, `sleep`, latch, future `get` | Find who should signal; usually main waiting for a worker |
| `WaitingForGcToComplete` or similar | GC pause | Allocation pressure or a memory leak |

Frames worth recognizing at the top of main:

- `ClassLinker`, `<clinit>`, `Class.forName`: first-touch class init. See
  [class-init-first-touch.md](class-init-first-touch.md).
- `LayoutInflater.createView` then `Constructor.newInstance`: reflective view creation on first
  inflate of each custom view class.
- `QueuedWork.waitToFinish` under `handleStopActivity` or `handleServiceArgs`: pending
  `SharedPreferences.apply()` writes. See [main-thread-io.md](main-thread-io.md).
- `Dagger*Component`, `*_Factory.get`, `DoubleCheck.get`: graph construction. See
  [di-graph-cost.md](di-graph-cost.md).

## Lock chains

```
"main" prio=5 tid=1 Blocked
  at com.example.EventLogger.log(EventLogger.kt:98)
  - waiting to lock <0x0d3fbd00> (a com.example.EventLogger) held by thread 34

"logger-worker" prio=5 tid=34 TimedWaiting
  at java.lang.Object.wait(Native method)
  - waiting on <0x00fc7065> (a java.util.concurrent.atomic.AtomicInteger)
  - locked <0x0d3fbd00> (a com.example.EventLogger)
```

Main wants a lock held by a worker that is itself waiting. Fix the worker, or stop main from
taking that lock. Never fix it by adding a timeout on main.

## The "ANR in" CPU block

```
Load: 15.29 / 5.19 / 1.87
CPU usage from 0ms to 13135ms later:
  191% 1948/system_server: 72% user + 119% kernel / faults: 78816 minor 9 major
   30% 5991/com.example.app: 23% user + 6.4% kernel / faults: 118172 minor 2 major
```

- Load is the 1, 5, and 15 minute averages. Compare it with the core count. A 1-minute load
  well above the number of cores means the device was overloaded.
- `major` faults mean pages were read from storage. Many on your process means heavy I/O or
  code loading. Many on system_server or `kswapd` means memory pressure.
- High `kernel` time on system_server often means Binder or I/O pressure.

## App defect, overload, or external

| Signal | Points to |
|---|---|
| Main `Blocked` on a lock your code or an SDK owns | `APP_DEFECT` |
| Main `Runnable` in the same app frame across many reports | `APP_DEFECT` |
| Main waiting on a worker's result (`get`, latch, `runBlocking`) | `APP_DEFECT` |
| Main idle, many different short tops across the cluster, ANRs at startup | `APP_OVERLOAD` (no gap for input) |
| Your process has high CPU right before the ANR | `APP_DEFECT` or `APP_OVERLOAD` |
| OEM freeze or unfreeze lines around the ANR time | `EXTERNAL` |
| system_server or surfaceflinger very busy, load far above core count | `EXTERNAL` (fix nothing; keep resume light) |
| Several unrelated apps ANR in the same minute | `EXTERNAL` |
| `kswapd` busy, low-memory kills nearby | `EXTERNAL`, sometimes caused by your memory use |

Only propose code fixes for `APP_DEFECT` and `APP_OVERLOAD`. For `EXTERNAL`, say so, suggest
tagging these in the dashboard so they stop hiding real regressions, and keep resume paths
short so the app recovers quickly.

## Reading a cluster, not one trace

A Vitals or Crashlytics cluster groups ANRs by top frame. Before you trust a cluster:

- Open several samples. If the top frames differ but all sit under the same `onCreate` or
  `onResume`, the real problem is total main-thread work in that callback.
- Check the device mix. A cluster dominated by low-RAM devices or one OEM points to
  [third-party-sdks-low-end.md](third-party-sdks-low-end.md).
- Check the app version mix. A cluster that starts in one release is a regression; see
  [release-watch.md](release-watch.md).
