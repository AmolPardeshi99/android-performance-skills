# Leak review checklist

## Contents
- Severity levels
- Lifecycle and views (LV)
- Context and statics (CS)
- Listeners and callbacks (LC)
- Async and scopes (AS)
- DI scopes (DI)
- Resources (RS)
- Compose (CP)
- Detection (DT)

## Severity levels

| Level | Meaning | Examples |
|---|---|---|
| **CRITICAL** | Retains an Activity or View tree for the life of the process, on a screen every user opens | Activity in a static field or singleton; Activity-bound component cached app-wide |
| **HIGH** | Retains an Activity, Fragment view, or ViewModel after the user leaves, repeated per visit | Binding not cleared; listener added to an app-wide manager with no removal; Rx subscription never disposed |
| **MEDIUM** | Temporary retention, or memory waste that grows with use | `postDelayed` with a long delay; replay cache holding a large page; unbounded pool threads |
| **LOW** | Hygiene, or retention bounded by a short time | `TypedArray` not recycled; missing `use {}` on a rarely-used stream |

Raise one level for screens on the main path (home, login, checkout). Lower one level when the
holder's lifetime turns out to be the same as the object it holds.

## Lifecycle and views (LV)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| LV1 | Fragment binding cleared in `onDestroyView` | `lateinit var binding` or `_binding` never set to null | HIGH | [lifecycle](../references/lifecycle-and-views.md) |
| LV2 | Observe with the view lifecycle | `observe(this)` in Fragments; bare `lifecycleScope.launch { collect }` | MEDIUM | [lifecycle](../references/lifecycle-and-views.md) |
| LV3 | ViewModels hold no UI | Activity, View, Binding, Activity Context, composable lambda fields | HIGH | [lifecycle](../references/lifecycle-and-views.md) |
| LV4 | Presenters detach | `attach(view)` without `detach()` in teardown | HIGH | [lifecycle](../references/lifecycle-and-views.md) |
| LV5 | Custom views unregister | Registration in constructor or `onAttachedToWindow` without removal in `onDetachedFromWindow` | HIGH | [lifecycle](../references/lifecycle-and-views.md) |
| LV6 | Result launchers registered once | `registerForActivityResult` in `onViewCreated` or click handlers | MEDIUM | [lifecycle](../references/lifecycle-and-views.md) |
| LV7 | `by lazy` does not leak `this` | `by lazy { X(this) }` where X is app-scoped | MEDIUM | [lifecycle](../references/lifecycle-and-views.md) |

## Context and statics (CS)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| CS1 | No UI in statics | `companion object` or `object` fields typed Activity, Fragment, View, Binding | CRITICAL | [context](../references/context-and-statics.md) |
| CS2 | Singletons store `applicationContext` | `init(context)` storing the argument as is | CRITICAL | [context](../references/context-and-statics.md) |
| CS3 | Anonymous listeners removed | `object :` or lambdas passed to app-wide objects | HIGH | [context](../references/context-and-statics.md) |

## Listeners and callbacks (LC)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| LC1 | Every register has a remove | `register*`, `add*Listener`, `subscribe`, `setCallback` without a pair | HIGH | [listeners](../references/listeners-and-callbacks.md) |
| LC2 | Delayed messages removed | `postDelayed` without `removeCallbacks` | MEDIUM | [listeners](../references/listeners-and-callbacks.md) |
| LC3 | Frame callbacks removed | Self-reposting `Choreographer` callbacks | HIGH | [listeners](../references/listeners-and-callbacks.md) |
| LC4 | Nav listeners removed | `addOnDestinationChangedListener` without removal | HIGH | [listeners](../references/listeners-and-callbacks.md) |
| LC5 | Process lifecycle observers are app-scoped | Activity or Fragment added to `ProcessLifecycleOwner` | CRITICAL | [listeners](../references/listeners-and-callbacks.md) |

## Async and scopes (AS)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| AS1 | No `GlobalScope` capturing UI | `GlobalScope.launch` touching `binding`, `this`, Views | HIGH | [async](../references/async-and-scopes.md) |
| AS2 | Hand-made scopes cancelled | `CoroutineScope(...)` fields without `cancel()` | HIGH | [async](../references/async-and-scopes.md) |
| AS3 | Rx disposed | `subscribe(...)` results ignored or never cleared | HIGH | [rxjava](../examples/rxjava.md) |
| AS4 | Replay caches small | `replay >= 1` on large payloads; `Eagerly` sharing in app scopes | MEDIUM | [async](../references/async-and-scopes.md) |
| AS5 | Background tasks capture data, not screens | `Runnable`/executor tasks referencing the Activity | MEDIUM | [async](../references/async-and-scopes.md) |
| AS6 | Bounded pools | `newCachedThreadPool` behind hot APIs | MEDIUM | [async](../references/async-and-scopes.md) |

## DI scopes (DI)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| DI1 | Singletons depend only on app-scoped types | `@Singleton` or `single {}` with Activity, Fragment, View, Activity Context dependencies | CRITICAL | [di](../references/di-scopes.md) |
| DI2 | Activity-bound components not cached | Components or subcomponents stored in `object`s or the Application | CRITICAL | [di](../references/di-scopes.md) |
| DI3 | Presenters scoped to the screen | Presenters in `@Singleton` or app-wide Koin `single` | HIGH | [di](../references/di-scopes.md) |

## Resources (RS)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| RS1 | Closeables closed | Streams, `Cursor`, DB handles without `use {}` | MEDIUM | [resources](../references/resources-and-native.md) |
| RS2 | `TypedArray` recycled | `obtainStyledAttributes` without `recycle`/`use` | LOW | [resources](../references/resources-and-native.md) |
| RS3 | Bitmap caches bounded | Static maps of Bitmaps; full-size decodes for small views | HIGH | [resources](../references/resources-and-native.md) |
| RS4 | Players and cameras released | `MediaPlayer`, `ExoPlayer`, camera without `release()` | HIGH | [resources](../references/resources-and-native.md) |
| RS5 | WebView destroyed | WebView never `destroy()`ed, or pooled with an Activity Context | HIGH | [resources](../references/resources-and-native.md) |
| RS6 | Services stop | `START_STICKY` for one-off work, no `stopSelf` | MEDIUM | [resources](../references/resources-and-native.md) |

## Compose (CP)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| CP1 | Registrations in `DisposableEffect` | `addListener` inside `LaunchedEffect` or composable body | HIGH | [compose](../examples/compose.md) |
| CP2 | `remember` keyed to its inputs, resources disposed | `remember { Resource(id) }` with no key or no `onDispose` | MEDIUM | [compose](../examples/compose.md) |
| CP3 | Long-lived remembered objects use `applicationContext` | `remember { Sdk(LocalContext.current) }` | HIGH | [compose](../examples/compose.md) |
| CP4 | No composable lambdas in ViewModels | `@Composable () -> Unit` fields in ViewModels | HIGH | [compose](../examples/compose.md) |
| CP5 | No bare scopes in composition | `CoroutineScope(...)` in a composable body | MEDIUM | [compose](../examples/compose.md) |
| CP6 | `RememberObserver` starts work in `onRemembered` | Work launched in `init` | MEDIUM | [compose](../examples/compose.md) |

## Detection (DT)

| ID | Rule | Look for | Default | Read |
|---|---|---|---|---|
| DT1 | LeakCanary in debug builds | No `leakcanary-android` dependency | LOW | [detection](../references/detection-and-tools.md) |
| DT2 | Leak checks on core flows in CI | No `DetectLeaksAfterTestSuccess` rule | LOW | [detection](../references/detection-and-tools.md) |
| DT3 | OOM and low-memory exits tracked | No `ApplicationExitInfo` handling | LOW | [detection](../references/detection-and-tools.md) |
