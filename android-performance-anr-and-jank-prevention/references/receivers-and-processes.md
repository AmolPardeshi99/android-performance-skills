# Receivers, services, jobs, and process isolation

## Contents
- Why receiver ANRs are startup ANRs
- onReceive rules
- goAsync
- Moving push handling into its own process
- Services and foreground services
- JobService
- Review checks

## Why receiver ANRs are startup ANRs

When a broadcast or a push message arrives and your process is not running, the system starts
it to deliver the event. Before `onReceive` runs, the main thread executes
`Application.onCreate`, every `ContentProvider.onCreate`, and whatever DI graph and SDK setup
your application class does. All of that counts against the broadcast timeout.

So a receiver ANR with an innocent-looking `onReceive` usually means startup is too heavy for
this entry point. Look at `bindApplication` in a trace, or at `Application.onCreate` frames in
the ANR stack.

Observed in one large app: push messages were the single largest source of receiver ANRs, about
15,000 a day. The app built its DI graph and ran product and SDK initializers in the main
process before the push payload was even handed off.

## onReceive rules

- `onReceive` runs on main. Do nothing slow in it.
- Hand work to WorkManager (expedited if user-visible) or to an app-scoped coroutine with
  `goAsync()` for short work.
- Do not inject heavy graphs into receivers. Inject a small handler, or look it up lazily.
- For dynamically registered receivers, pass a `Handler` on a background looper to
  `registerReceiver` so `onReceive` does not run on main at all.

## goAsync

`goAsync()` lets `onReceive` return while work continues, but the broadcast timeout keeps
running until `PendingResult.finish()`. Use it only for work that reliably finishes in a few
seconds, and always call `finish()` in `finally`.

```kotlin
override fun onReceive(context: Context, intent: Intent) {
    val pending = goAsync()
    appScope.launch(Dispatchers.IO) {
        try {
            withTimeout(8_000) { handle(intent) }
        } finally {
            pending.finish()
        }
    }
}
```

## Moving push handling into its own process

If the main process's startup cannot be made light enough for every push, receive the push in a
small dedicated process and hand it to the main process over IPC. The small process starts
fast because it skips the main app's DI graph and SDK init.

Design that worked (three pieces):

1. **Client in the push process.** The push service runs with `android:process=":push"` (any
   name). On a message it serializes the payload into a `Bundle` and sends it with
   `Messenger.send()` to a service in the main process.
2. **Server in the main process.** A bound `Service` exposes a `Messenger` binder, rebuilds
   the message from the `Bundle`, and hands it to the handler.
3. **Handler in the main process.** All business logic moved out of the old receiver into one
   class. It runs notification work on an IO coroutine, not on the callback thread.

Details that matter:

- `Messenger` is lighter than AIDL and enough for small payloads at push volume.
- Route **every** push entry point through the boundary: message delivery and token refresh.
- **Bound the wait** for the service connection (4 s was used, well under the broadcast
  timeout) and decide what to do on timeout.
- Every process runs your `Application.onCreate`. Check the process name at the start and skip
  main-process initialization in the push process, or the new process is as slow as the old.
- Some push SDK versions do not deliver callbacks to a service in a non-default process. Test
  message delivery, data messages, notification messages, and token refresh on real devices
  before rollout, and ship behind a flag.

Result in that app: receiver ANRs fell from about 15,000 a day to about 5,000 (about 67%), and
the home screen's startup stopped competing with push handling, which unblocked other startup
fixes.

## Services and foreground services

- `onCreate`, `onStartCommand`, and `onBind` run on main. Launch work into a service-owned
  scope and `stopSelf(startId)` when done; cancel the scope in `onDestroy`.
- After `startForegroundService()`, call `startForeground()` first thing in `onStartCommand`,
  before any other work.
- Prefer WorkManager for deferrable work. It also avoids keeping a process alive.

## JobService

From Android 14, a slow `onStartJob` or `onStopJob` raises a visible ANR. Return quickly, do the
work in a coroutine, and call `jobFinished`. Prefer WorkManager, which handles this for you.

## Review checks

- Receivers or push services that inject large graphs or call SDKs synchronously.
- `goAsync()` without `finish()` in `finally`, or with unbounded work.
- `Application.onCreate` without a process-name check in apps that declare extra processes.
- Service callbacks doing I/O on main.
- `startForeground` not called first in `onStartCommand`.
