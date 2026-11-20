# Perfetto for ANRs and startup

## Contents
- Getting a useful trace
- Reading the main thread
- What each pattern looks like
- Queries
- Adding your own sections

## Getting a useful trace

- Release build, with Baseline Profiles, on a low-end device. Debug builds distort timing.
- Mark the build `profileable` so app sections and callstack sampling work:
  `<profileable android:shell="true" />` in the manifest.
- For startup: `adb shell am force-stop <pkg>`, start tracing, then launch.
- For ANRs in the field, `ProfilingManager` (Android 15+) can capture traces on device. Google's
  `android-profiler` skill has ready-made recording configs if the user has it.
- Include at least the `sched`, `freq`, `am`, `wm`, `gfx`, `view`, `binder_driver`, `dalvik`
  atrace categories, plus app tracing for the package.

## Reading the main thread

Open the trace at https://ui.perfetto.dev, find the app process, expand the main thread (its
thread id equals the process id).

1. Look at the thread state track: green Running, light green Runnable (waiting for a CPU),
   white or grey Sleeping, orange Uninterruptible (usually I/O).
2. For a long Sleeping stretch, click it to see what woke the thread. Binder replies and lock
   releases show up here.
3. For long Running stretches, look at the slices above: `bindApplication`, `activityStart`,
   `activityResume`, `inflate`, `Choreographer#doFrame`, `RV OnBindView`, and app sections.
4. Look at gaps. A main thread with no idle time for seconds during startup is the "no gap for
   input" pattern even if no slice is long.

## What each pattern looks like

| Pattern | In the trace |
|---|---|
| Main-thread I/O | Orange (D state) on main; `SharedPreferencesImpl` or file sections in sampled stacks |
| DI graph cost | Long app section around `inject`, or long `onCreate` with Dagger factory frames in sampled stacks |
| First-touch class init | Sampled stacks in `ClassLinker`, `<clinit>`; long first `inflate` that is short on later screens |
| ICU | Sampled stacks in `LocaleData` or `ICU` under a date or number format call |
| Receiver cold start | `bindApplication` and providers before the receiver's work, all inside the broadcast window |
| No gap for input | Main busy for seconds with many medium slices; input events delayed in `deliverInputEvent` |
| Lock contention | `Lock contention on ...` slices on main; see query 04 |
| Binder | Main Sleeping in a `binder transaction` slice; follow the arrow to the server thread |
| RenderThread back-pressure | Main in `syncAndDrawFrame` while RenderThread runs long `DrawFrame` |

## Queries

Run them, do not read them into context:

```bash
scripts/perfetto/run_queries.sh trace.perfetto-trace
scripts/perfetto/run_queries.sh trace.perfetto-trace scripts/perfetto/04_main_thread_lock_contention.sql
```

| File | Answers |
|---|---|
| `01_main_thread_long_slices.sql` | Which top-level main-thread slices are over 16 ms |
| `02_main_thread_state.sql` | How much main time was Running, Runnable, Sleeping, or in I/O |
| `03_startups.sql` | Startups found, their type and length, and the longest slices in each |
| `04_main_thread_lock_contention.sql` | Which locks blocked main, and who held them |
| `05_main_thread_binder.sql` | Which Binder calls from main were slow, and which process served them |
| `06_main_thread_slice_totals.sql` | Which slice names cost the most in total (repeated work) |

The queries use the Perfetto standard library (`android.startup.startups`,
`android.monitor_contention`, `android.binder`). Column names can change between Perfetto
releases; if a query fails, run `SELECT * FROM <table> LIMIT 1` and adjust.

## Adding your own sections

```kotlin
import androidx.tracing.trace

trace("home:inject") { component.inject(this) }
trace("home:inflate") { binding = ActivityHomeBinding.inflate(layoutInflater) }
```

Sections are cheap when tracing is off. Name them `area:step` so query 06 groups them.
