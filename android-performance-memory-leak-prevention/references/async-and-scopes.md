# Async work, scopes, and threads

## Contents
- Coroutine scopes
- RxJava subscriptions
- Flows and replay caches
- Threads and executors
- Unbounded thread pools

Framework code: [../examples/coroutines-flow.md](../examples/coroutines-flow.md),
[../examples/rxjava.md](../examples/rxjava.md).

## Coroutine scopes

A coroutine holds everything its lambda captures until it finishes. If the scope outlives the
screen, so does the screen.

| Owner | Scope |
|---|---|
| Fragment view | `viewLifecycleOwner.lifecycleScope` |
| Activity | `lifecycleScope` |
| ViewModel | `viewModelScope` |
| Composable | `rememberCoroutineScope()` or `LaunchedEffect` |
| App-wide work | An injected app scope with `SupervisorJob`, not `GlobalScope` |

- A hand-made `CoroutineScope(...)` in a screen must be cancelled in the matching teardown.
- App-scoped work must not capture a View, Binding, or Activity. Pass plain data in and post
  results through a repository or `StateFlow`.

## RxJava subscriptions

`subscribe()` returns a `Disposable` that holds the observer, which usually captures the screen.

- Add each one to a `CompositeDisposable` and `clear()` it in the paired teardown
  (`onDestroyView` for Fragments, `onCleared` for ViewModels).
- Use `clear()` when the owner can subscribe again (Fragment views), `dispose()` when it is
  finished for good.
- AutoDispose or `takeUntil(lifecycleEvents)` are alternatives.

## Flows and replay caches

- `MutableSharedFlow(replay = N)` keeps the last N values with or without collectors. Large
  payloads (pages of results, Bitmaps) stay pinned. Use `replay = 0` for events and `StateFlow`
  with a clear-on-exit for state.
- `stateIn(scope, SharingStarted.Eagerly, ...)` in an app scope keeps the upstream running and
  its last value cached forever; prefer `WhileSubscribed(5_000)` for screen data.

## Threads and executors

A `Thread` or pool worker is a GC root while it runs. A `Runnable` submitted from an Activity
that captures `this` and blocks on I/O keeps the Activity alive for as long as the I/O takes.
Capture data, not the Activity, and post results back through a lifecycle-aware channel.

## Unbounded thread pools

Each platform thread reserves its own stack, around 1 MB by default. An unbounded
`newCachedThreadPool()` behind a hot API can create dozens of threads under startup load.

- Observed: a cached pool behind a preferences wrapper grew to 70 to 80 threads on some devices.
  Switching it to a fixed pool of 8 cut that overhead from roughly 80 MB to 8 MB at startup.
- Check thread counts with `adb shell ps -T -p <pid> | wc -l` or in a Perfetto trace.
- Prefer shared dispatchers or fixed pools sized to the work.
