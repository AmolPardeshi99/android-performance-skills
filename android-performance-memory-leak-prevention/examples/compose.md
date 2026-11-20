# Samples: Jetpack Compose

## Contents
- Choosing the effect API
- Registrations need DisposableEffect
- remember keys for resources
- Context in remembered objects
- Latest values in long-lived callbacks
- No composable lambdas in ViewModels
- Coroutine scopes in composables
- RememberObserver
- App-wide state

## Choosing the effect API

| API | Runs | Cleanup | Use for |
|---|---|---|---|
| `SideEffect` | After every successful recomposition | None | Pushing Compose state into non-Compose objects |
| `LaunchedEffect(key)` | Coroutine on enter and key change | Cancelled on exit or key change | Suspending work |
| `DisposableEffect(key)` | On enter and key change | `onDispose` | Registrations, listeners, resources |

## Registrations need DisposableEffect

```kotlin
// ❌ No cleanup; the SDK keeps the listener after the screen leaves
LaunchedEffect(Unit) { LocationSdk.addListener { onLocation(it) } }

// ✅
DisposableEffect(Unit) {
    val listener = LocationListener { onLocation(it) }
    LocationSdk.addListener(listener)
    onDispose { LocationSdk.removeListener(listener) }
}

// Lifecycle observer
val lifecycle = LocalLifecycleOwner.current.lifecycle
DisposableEffect(lifecycle) {
    val observer = LifecycleEventObserver { _, event -> viewModel.onLifecycle(event) }
    lifecycle.addObserver(observer)
    onDispose { lifecycle.removeObserver(observer) }
}
```

## remember keys for resources

```kotlin
@Composable
fun ItemDetail(itemId: String) {
    val resource = remember(itemId) { ExpensiveResource(itemId) }
    DisposableEffect(resource) { onDispose { resource.close() } }
}
```

## Context in remembered objects

`LocalContext.current` is usually the Activity. Remembering an object built from it is fine
while it stays inside the composition: when the Activity is recreated, the composition and its
remembered values go with it. It leaks when that object is handed to something that outlives
the Activity, such as a singleton, an app-scoped cache, or a ViewModel.

```kotlin
// ❌ The app-wide cache keeps the first Activity alive after it is destroyed
val context = LocalContext.current
val player = remember { PlayerCache.getOrCreate { VideoPlayer(context) } }

// ✅ Anything that can outlive the screen gets the application Context
val appContext = LocalContext.current.applicationContext
val player = remember { PlayerCache.getOrCreate { VideoPlayer(appContext) } }
```

## Latest values in long-lived callbacks

```kotlin
@Composable
fun Tracking(onLocation: (Location) -> Unit) {
    val latest by rememberUpdatedState(onLocation)
    DisposableEffect(Unit) {
        val cb = LocationCallback { latest(it) }
        LocationSdk.setCallback(cb)
        onDispose { LocationSdk.setCallback(null) }
    }
}
```

## No composable lambdas in ViewModels

```kotlin
// ❌ Keeps whatever the lambda captured alive with the ViewModel
class ProfileViewModel : ViewModel() { var content: (@Composable () -> Unit)? = null }

// ✅ Expose state; the UI decides what to show
class ProfileViewModel(repo: ProfileRepo) : ViewModel() {
    val profile: StateFlow<Profile?> = repo.profile.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
}
```

## Coroutine scopes in composables

```kotlin
// ❌ New scope every recomposition; old jobs orphaned
val scope = CoroutineScope(Dispatchers.IO)

// ✅
val scope = rememberCoroutineScope()
```

## RememberObserver

```kotlin
class Poller : RememberObserver {
    private var job: Job? = null
    override fun onRemembered() { job = CoroutineScope(Dispatchers.Main).launch { poll() } }  // not in init
    override fun onForgotten() { job?.cancel() }
    override fun onAbandoned() { job?.cancel() }
}
```

## App-wide state

Snapshot state in an app-wide `object` is not a leak by itself, but it keeps whatever it holds
for the life of the process and is shared by every screen. Keep screen state in ViewModels, and
keep app-wide state small and free of Context, Views, and large payloads.
