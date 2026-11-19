# Performance review checklist

## Contents
- Severity levels
- Threading and blocking (T)
- Main-thread I/O and parsing (IO)
- DI graph (DI)
- First-touch costs (FT)
- Receivers, services, processes (RX)
- Startup and input gaps (ST)
- SDKs and devices (SDK)
- Rendering (R)
- Observability and rollout (OBS)

## Severity levels

Grade each finding by where it runs and how long it can block, not by how bad the code looks.

| Level | Meaning | Examples |
|---|---|---|
| **CRITICAL** | Can block main for seconds or deadlock on a path every user hits | `runBlocking` on main in launch path; lock taken on main that a worker holds during I/O; unbounded wait on main; `goAsync` without `finish` |
| **HIGH** | Main-thread blocking on a primary path (startup, resume, input, receivers) likely above 100 ms on low-end devices | Prefs or JSON on main in `onCreate`; heavy `@Inject` fields on the launch activity; giant enum first touched on main at startup |
| **MEDIUM** | Blocking on a secondary path, or repeated cost that causes jank | Formatter created in `onBindViewHolder`; parsing after `observeOn(main)` on a detail screen; decorative animation on low-end |
| **LOW** | Latent hazard or hygiene; no measurable cost today | `lazy` without mode on main-only fields; unbounded pool not yet hot; missing trace sections |

Raise one level when the code is on the cold-start path of a receiver or the first screen.
Lower one level when you cannot show it runs on main.

## Threading and blocking (T)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| T1 | Never block main waiting for other work | `runBlocking`, `.get()`, `await()` in `runBlocking`, `CountDownLatch.await`, `join`, `blockingGet` on cold sources | CRITICAL | [threading](../references/threading-and-locks.md) |
| T2 | No lock on main that background I/O also holds | `synchronized` or `ReentrantLock` shared by main and IO code, loggers, caches | CRITICAL | [threading](../references/threading-and-locks.md) |
| T3 | No `synchronized` around suspension | `synchronized { suspendCall() }` | HIGH | [threading](../references/threading-and-locks.md) |
| T4 | Consistent lock order | Nested locks taken in different orders | HIGH | [threading](../references/threading-and-locks.md) |
| T5 | Right dispatcher | Blocking I/O on `Default`, CPU on `Main` | MEDIUM | [coroutines](../examples/coroutines-flow.md) |
| T6 | No `GlobalScope` | `GlobalScope.launch` | LOW | [coroutines](../examples/coroutines-flow.md) |
| T7 | Bounded pools | `newCachedThreadPool`, pools with no max, `Schedulers.io()` for bursty blocking tasks | MEDIUM | [threading](../references/threading-and-locks.md) |
| T8 | Binder calls off hot paths | `PackageManager`, `ContentResolver.query`, `AccountManager`, `Settings` in lifecycle callbacks | HIGH | [threading](../references/threading-and-locks.md) |
| T9 | Bounded waits | Service connection or IPC handoff with no timeout | HIGH | [threading](../references/threading-and-locks.md) |
| T10 | Cancellable loops | Long CPU loop in a coroutine with no `ensureActive`/`yield` | LOW | [coroutines](../examples/coroutines-flow.md) |

## Main-thread I/O and parsing (IO)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| IO1 | No prefs reads on main at startup | `getSharedPreferences(...).getX` in `onCreate`, getters called from UI | HIGH | [io](../references/main-thread-io.md) |
| IO2 | No `commit()` on main; few `apply()` before stop | `.commit()`, `apply()` in loops or per event | HIGH | [io](../references/main-thread-io.md) |
| IO3 | No parsing on main | `fromJson`, `JSONObject`, `parseFrom` after a suspend call or after `observeOn(main)` | HIGH | [io](../references/main-thread-io.md) |
| IO4 | No runtime parsing of static data | JSON string constants parsed at use | HIGH | [io](../references/main-thread-io.md) |
| IO5 | Read the field, not the blob | Decoding a large stored object to read one value | HIGH | [io](../references/main-thread-io.md) |
| IO6 | Fast path does not depend on an unfetched flag | Cached path guarded by a remote flag that defaults to off | MEDIUM | [io](../references/main-thread-io.md) |
| IO7 | Light providers and initializers | Work in `ContentProvider.onCreate`, `Initializer.create` | HIGH | [io](../references/main-thread-io.md) |
| IO8 | Files, DB, bitmaps off main | File reads, non-suspend DAO, `decodeFile`, `MediaPlayer.prepare` | HIGH | [io](../references/main-thread-io.md) |

## DI graph (DI)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| DI1 | No heavy eager fields on launch screens | `@Inject` fields with I/O or SDK init in their transitive graph | HIGH | [di](../references/di-graph-cost.md) |
| DI2 | Lazy is not a fix if `.get()` is on main | `Lazy.get()` / `Provider.get()` in `onCreate`/`onResume` | MEDIUM | [di](../references/di-graph-cost.md) |
| DI3 | Constructors without side effects | `init {}` that registers, reads prefs, starts SDKs | MEDIUM | [di](../references/di-graph-cost.md) |
| DI4 | Heavy `@Provides` off main | Retrofit, Gson, DB, SDK clients built when a screen opens | MEDIUM | [hilt](../examples/dagger-hilt.md) |
| DI5 | Koin startup is light | `createdAtStart = true` for heavy singletons, `get()` in fields | MEDIUM | [koin](../examples/koin.md) |

## First-touch costs (FT)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| FT1 | Giant enums not first touched on main at startup | Enums with hundreds of constants used in first-screen code | HIGH | [first-touch](../references/class-init-first-touch.md) |
| FT2 | Formatters created once, off hot paths | `SimpleDateFormat`, `DecimalFormat`, `String.format(Locale)` in binds, getters, composables | MEDIUM (HIGH at startup) | [first-touch](../references/class-init-first-touch.md) |
| FT3 | Reflection inflation of many custom views on first screen | Dozens of custom views in the first layout, no prewarm or factory | MEDIUM | [first-touch](../references/class-init-first-touch.md) |
| FT4 | Fonts cached | `createFromAsset` / `getFont` per view instance | MEDIUM | [views](../examples/views.md) |
| FT5 | First WebView not created on tap | `WebView(context)` in a click path with no prewarm | MEDIUM | [first-touch](../references/class-init-first-touch.md) |
| FT6 | Prewarming finishes before use | Prewarm started late, or on main | MEDIUM | [first-touch](../references/class-init-first-touch.md) |

## Receivers, services, processes (RX)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| RX1 | `onReceive` returns fast | I/O, SDK calls, heavy injection in `onReceive` | HIGH | [receivers](../references/receivers-and-processes.md) |
| RX2 | `goAsync` always finishes | `goAsync()` without `finish()` in `finally`, or unbounded work | CRITICAL | [receivers](../references/receivers-and-processes.md) |
| RX3 | Process-aware Application | Extra `android:process` with no process check in `Application.onCreate` | HIGH | [hilt](../examples/dagger-hilt.md) |
| RX4 | Service callbacks off main | Work in `onStartCommand`, `onBind` | HIGH | [receivers](../references/receivers-and-processes.md) |
| RX5 | `startForeground` first | Work before `startForeground()` after `startForegroundService()` | HIGH | [receivers](../references/receivers-and-processes.md) |
| RX6 | Jobs return quickly | Blocking work in `onStartJob` | HIGH | [receivers](../references/receivers-and-processes.md) |

## Startup and input gaps (ST)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| ST1 | Only on-screen UI built before first frame | Optional widgets, overlays, below-the-fold sections inflated in `onCreate` | HIGH | [startup](../references/startup-input-gaps.md) |
| ST2 | No double inflation | Layout inflated empty in `onCreate` and again with data | HIGH | [startup](../references/startup-input-gaps.md) |
| ST3 | Gaps between startup tasks | Many independent `post`/`runOnUiThread` calls fired together | MEDIUM | [startup](../references/startup-input-gaps.md) |
| ST4 | Non-UI startup work after first frame | Analytics, sync, prompts, reminders in `onCreate` | MEDIUM | [startup](../references/startup-input-gaps.md) |

## SDKs and devices (SDK)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| SDK1 | SDK init off main or deferred | SDK `init` in `Application.onCreate`, auto-init providers | HIGH | [sdks](../references/third-party-sdks-low-end.md) |
| SDK2 | SDK calls off main in lifecycle and bind paths | SDK APIs in `onResume`, bind methods | MEDIUM | [sdks](../references/third-party-sdks-low-end.md) |
| SDK3 | Low-end switch for decorative animation | Looping Lottie or animated vectors with no device-class check | MEDIUM | [sdks](../references/third-party-sdks-low-end.md) |
| SDK4 | No work for disabled telemetry | Events built before checking the sampling or enable flag | MEDIUM | [sdks](../references/third-party-sdks-low-end.md) |
| SDK5 | Device-class-aware sizing | Fixed cache and prefetch sizes on all devices | LOW | [sdks](../references/third-party-sdks-low-end.md) |

## Rendering (R)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| R1 | Bind only assigns | Filtering, parsing, formatting in `onBindViewHolder` | MEDIUM | [views](../examples/views.md) |
| R2 | Diff off main | `DiffUtil.calculateDiff` on main | MEDIUM | [views](../examples/views.md) |
| R3 | No allocations in `onDraw` | `Paint()`, `Path()`, `RectF()` inside `onDraw` | MEDIUM | [views](../examples/views.md) |
| R4 | Flat hierarchies | Nested layouts that one `ConstraintLayout` or `<merge>` would flatten | LOW | [rendering](../references/rendering-jank.md) |
| R5 | No dead views | Animation views that only show a static image | LOW | [rendering](../references/rendering-jank.md) |
| R6 | Compose: no heavy work in composition | Sorting, filtering, formatting in a composable body | MEDIUM | [compose](../examples/compose.md) |
| R7 | Compose: deferred reads | Scroll or animation state read at the top of a screen | MEDIUM | [compose](../examples/compose.md) |
| R8 | Compose: no backwards writes | State written after being read in the same composition | HIGH | [compose](../examples/compose.md) |
| R9 | Compose: lazy list keys | `items(list)` without `key` | LOW | [compose](../examples/compose.md) |

## Observability and rollout (OBS)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| OBS1 | Startup-order changes behind a flag with a safe default | Deferral or prewarm without a flag | LOW | [release-watch](../references/release-watch.md) |
| OBS2 | Hot paths have trace sections | Known hotspots with no `trace {}` or custom trace | LOW | [perfetto](../references/perfetto.md) |
| OBS3 | ANR traces collected | No `ApplicationExitInfo` handling | LOW | [release-watch](../references/release-watch.md) |
