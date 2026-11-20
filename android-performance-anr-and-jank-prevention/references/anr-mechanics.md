# ANR mechanics

## Contents
- Timeouts
- Three kinds of ANR
- What happens after the timeout
- Version changes worth knowing
- Vitals thresholds

## Timeouts

AOSP defaults. OEMs can change them, so treat them as typical values.

| Trigger | Typical timeout |
|---|---|
| Input event (touch, key) not consumed | 5 s |
| `BroadcastReceiver.onReceive` | 10 s foreground broadcast, 60 s background broadcast |
| Service `onCreate` / `onStartCommand` / `onBind` | 20 s foreground service, about 200 s background |
| `startForegroundService()` without `startForeground()` | A few seconds. Check the current docs for your target SDK |
| `JobService.onStartJob` / `onStopJob` slow to return (Android 14+) | A few seconds, reported as "No response to onStartJob" |
| `ContentProvider` publish during process start | About 10 s |

Two consequences people miss:

- **A cold start counts against the timeout.** If a broadcast or service start launches your
  process, `Application.onCreate`, every `ContentProvider.onCreate`, and the DI graph all run
  inside that window. A receiver that does nothing can still ANR because of startup.
- **Background work does not stop the clock.** `goAsync()` only lets `onReceive` return. The
  timeout keeps running until `PendingResult.finish()` is called.

## Three kinds of ANR

| Kind | Detected by | Cause |
|---|---|---|
| Component | ActivityManagerService | A service, broadcast, provider, or job callback did not finish in time |
| Input | InputDispatcher | An event sent to a window was not acknowledged within 5 s |
| No focused window | InputDispatcher with WindowManager | Input arrived but no window could take focus |

**Component ANR.** When the system asks your process to run a callback over Binder, it also
posts a delayed timeout message. Your app must report completion before that message fires. If
the main looper is busy with other messages, the callback starts late and the clock keeps
running.

**Input ANR.** The clock starts when the event is queued on your window's input channel. The
main thread only has to start handling it, so many short tasks back to back can cause an input
ANR as surely as one long task. This is the "no gap for input" pattern in
[startup-input-gaps.md](startup-input-gaps.md).

**No focused window.** Usually happens during activity transitions when `onResume` or the first
frame is late. Check system_server load and window logs as well as your own main thread.

## What happens after the timeout

1. The system dumps stacks for your process and some others to `/data/anr/` (`anr_*` files on
   newer releases, `traces.txt` on older ones) and logs `am_anr` to the event log.
2. It logs an `ANR in <process>` block with load averages and per-process CPU use.
3. It shows the dialog, or kills the process silently if it is in the background.

The stack is taken **after** the timeout. The frame on top may be whatever happened to run
next, not the work that used up the time. That is why a second signal is required in triage.

## Version changes worth knowing

| Release | Change |
|---|---|
| Android 11 (API 30) | `ApplicationExitInfo` gives the ANR reason and trace on next launch |
| Android 14 (API 34) | Slow `JobService` callbacks raise an ANR the app can see |
| Android 14+ | Cached apps cannot receive most context-registered broadcasts until they leave the cached state |
| Android 15 (API 35) | Some foreground service types get run-time limits; check the docs for the types you use |

## Vitals thresholds

Google Play's bad-behavior threshold for user-perceived ANR rate is 0.47% of daily active users
overall, and 8% on any single device model. Play counts only `Input dispatching timed out` ANRs
as user-perceived, so a broadcast, service, or job ANR counts toward the total ANR rate but not
the user-perceived one.
