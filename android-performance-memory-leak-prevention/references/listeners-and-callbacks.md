# Listeners, callbacks, and Handlers

## Contents
- Pairing table
- System listeners and receivers
- SDK and app-wide managers
- Handler and postDelayed
- Choreographer frame callbacks
- NavController listeners
- ProcessLifecycleOwner

## Pairing table

| Register in | Remove in |
|---|---|
| `onCreate` | `onDestroy` |
| `onStart` | `onStop` |
| `onResume` | `onPause` |
| `onViewCreated` (Fragment) | `onDestroyView` |
| `onAttachedToWindow` (View) | `onDetachedFromWindow` |
| `DisposableEffect` body (Compose) | its `onDispose` |
| ViewModel `init` | `onCleared` |

## System listeners and receivers

`SensorManager`, `LocationManager`, `ConnectivityManager.registerNetworkCallback`,
`registerReceiver`, `ContentResolver.registerContentObserver`, and `ClipboardManager`
listeners all hold your listener until you remove it. Pair each one per the table.

For connectivity, use `registerDefaultNetworkCallback` instead of the deprecated
`CONNECTIVITY_ACTION` broadcast.

## SDK and app-wide managers

Session managers, config managers, analytics, location and map SDKs, and event buses are
app-scoped. Every `addListener`/`subscribe` from a screen needs a `removeListener`. When an SDK
only offers `setCallback`, clear it (`setCallback(null)`) on teardown.

## Handler and postDelayed

`MessageQueue → Message → Runnable → Activity` keeps the Activity alive until the message runs.

- Keep the `Runnable` in a field and `removeCallbacks` in teardown, or
  `handler.removeCallbacksAndMessages(null)`.
- Better: `lifecycleScope.launch { delay(ms); ... }`, which is cancelled automatically.

## Choreographer frame callbacks

A frame callback that re-posts itself runs forever unless removed. Remove it in `onPause` or
`onDetachedFromWindow`, and stop re-posting when the owner is no longer active.

## NavController listeners

`NavController` outlives Fragment views. Add `OnDestinationChangedListener` in `onViewCreated`
and remove it in `onDestroyView`, or collect `currentBackStackEntryFlow` with the view
lifecycle.

## ProcessLifecycleOwner

Its lifecycle never reaches `DESTROYED`, so observers are never removed automatically. Add only
app-scoped observers to it, from `Application`. React to foreground and background in an
Activity through the Activity's own lifecycle.
