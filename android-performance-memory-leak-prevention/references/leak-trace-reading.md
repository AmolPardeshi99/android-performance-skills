# Reading leak traces and heap dumps

## Contents
- LeakCanary trace anatomy
- Finding the reference to break
- Common trace shapes
- Library and platform leaks
- Reading an HPROF without LeakCanary
- Ranking a backlog of leaks

## LeakCanary trace anatomy

```
┬───
│ GC Root: Global variable in native code
│
├─ com.example.sdk.LocationClient instance
│    Leaking: NO (LocationClient↓ is not leaking)
│    ↓ LocationClient.listeners
│                     ~~~~~~~~~
├─ java.util.ArrayList instance
│    Leaking: UNKNOWN
│    ↓ ArrayList[0]
│               ~~~
├─ com.example.map.MapFragment$onViewCreated$1 instance
│    Leaking: UNKNOWN
│    Anonymous class implementing com.example.sdk.LocationListener
│    ↓ MapFragment$onViewCreated$1.this$0
│                                  ~~~~~~
╰→ com.example.map.MapFragment instance
     Leaking: YES (Fragment#mFragmentManager is null)
     Retaining 2.1 MB in 18233 objects
```

- **GC Root** at the top: why the chain is alive.
- **Leaking: NO / YES / UNKNOWN** with a reason LeakCanary inferred.
- **`~~~` underline**: references LeakCanary suspects. The leak is somewhere between the last
  `NO` and the first `YES`.
- **Retaining N MB**: retained size, useful for ranking.

## Finding the reference to break

1. Find the last `Leaking: NO` node. That object is legitimately long-lived.
2. The underlined references below it are candidates. Read the code that creates each one.
3. Pick the reference that a lifecycle event should have cleared: a listener that should have
   been removed, a field that should have been nulled, a job that should have been cancelled.
4. In the example above: `LocationClient.listeners` should not still hold a listener created in
   `MapFragment.onViewCreated`. Fix: remove it in `onDestroyView`.

## Common trace shapes

| Shape | Usual cause |
|---|---|
| `Fragment.mView` or `Fragment.binding` with `Fragment#mView is null` reasons | Binding not cleared in `onDestroyView` |
| `MessageQueue.mMessages` → `Message.callback` | `postDelayed` not removed |
| `Thread` or `ThreadPoolExecutor$Worker` → `Runnable` → Activity | Background task captures the Activity |
| `StandaloneCoroutine` or `DispatchedContinuation` → lambda → Fragment | Scope outlives the screen |
| `LambdaObserver` or `ConsumerSingleObserver` → Activity | Rx subscription not disposed |
| `DaggerAppComponent` → subcomponent → Activity | Component built with the Activity and stored app-wide |
| `InputMethodManager.mCurRootView` or similar | Platform leak; often already ignored by LeakCanary |

## Library and platform leaks

LeakCanary ships a list of known platform and library leaks and marks them as "Library Leak".
Do not suppress a leak unless you can show it is in code you do not own, and record why.
Upgrading the library often fixes it.

## Reading an HPROF without LeakCanary

1. Capture: `scripts/capture_heap_dump.sh <package>` (or Android Studio's Memory Profiler).
2. Open in Android Studio (File > Open). Filter "Show activity/fragment leaks".
3. Sort by retained size. For each suspicious instance, open References and follow the path to
   a GC root.
4. Shark CLI (`shark-cli`) can run LeakCanary's analysis on any HPROF:
   `shark-cli --hprof heap.hprof analyze`.
5. For other tools (Eclipse MAT), convert first with `hprof-conv`.

## Ranking a backlog of leaks

When leak detection has been off for a while and many signatures appear at once:

1. Group by leak signature (LeakCanary groups them for you).
2. Rank by occurrences times retained size, and by whether the flow is core (login, home,
   checkout).
3. Fix one signature per change, so each fix is easy to verify and revert.
4. Keep detection running afterwards. In one large app, turning leak detection back on and
   fixing the top five signatures across login, home, booking, and account flows cleared the
   backlog; the pipeline then kept new ones from piling up.
