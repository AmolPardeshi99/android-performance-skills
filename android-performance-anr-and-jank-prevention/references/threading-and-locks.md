# Threading, locks, and Binder

## Contents
- Dispatcher choice
- Blocking the main thread on purpose (runBlocking, get, latches)
- Locks
- lazy modes
- Unbounded thread pools
- Binder calls on main
- Cancellation in tight loops
- Bounded waits

Framework code: [../examples/coroutines-flow.md](../examples/coroutines-flow.md),
[../examples/rxjava.md](../examples/rxjava.md).

## Dispatcher choice

| Work | Coroutines | RxJava |
|---|---|---|
| Blocking I/O: network, disk, DB, prefs | `Dispatchers.IO` | `Schedulers.io()` |
| CPU: parsing, mapping large lists, crypto, image decode | `Dispatchers.Default` | `Schedulers.computation()` |
| View or Compose state | `Dispatchers.Main` | `AndroidSchedulers.mainThread()` |
| Serial access to shared state | `Dispatchers.IO.limitedParallelism(1)` | `Schedulers.single()` or a single-thread executor |

`Dispatchers.Default` has as many threads as cores (at least two). Blocking I/O there starves
CPU work. Room and Retrofit suspend functions already switch threads for the call itself, but
anything you do with the result runs on the caller's dispatcher.

## Blocking the main thread on purpose

These all make main wait, whatever thread does the work:

- `runBlocking { }` on main. It also deadlocks if the inner code needs main.
- `Future.get()`, `Deferred` awaited from `runBlocking`, `CountDownLatch.await()`,
  `Thread.join()`, RxJava `blockingGet()` / `blockingFirst()` on a cold source.
- `Lazy.get()` or `Provider.get()` on main when the provider does heavy work.

`runBlocking` belongs in tests and `main()` functions, not in Android callbacks. Exception: a
`blockingFirst()` on a seeded `BehaviorSubject` or `StateFlow.value` returns immediately and is
not a finding.

## Locks

- **`synchronized` around a suspend call.** The thread is released at the suspension point but
  the monitor is not. Use `Mutex.withLock` and keep suspension outside it where possible.
- **Lock order inversion.** Thread A takes L1 then L2, thread B takes L2 then L1. Enforce one
  order, or replace both locks with a single serial dispatcher.
- **`ReentrantLock` without `finally`.** Use `lock.withLock { }`.
- **`Mutex` is not reentrant.** Locking it twice in the same coroutine hangs forever.
- **Main taking a lock that a worker holds during I/O.** Logging, analytics, and caches are the
  usual culprits. Do not hold a lock while calling into another component, an SDK, or I/O.

Third-party SDKs with internal lock contention show up the same way. See
[third-party-sdks-low-end.md](third-party-sdks-low-end.md).

## lazy modes

| Mode | Behavior | Use |
|---|---|---|
| `SYNCHRONIZED` (default) | First access takes a lock; later reads are a volatile read | Shared across threads, init must run once |
| `PUBLICATION` | No lock; several threads may run init, first result wins | Shared, init is cheap and idempotent |
| `NONE` | No synchronization | Only ever touched from one thread, such as main |

The real risk is not the lock overhead after init. It is a heavy initializer behind `by lazy`
that main touches first, or that main waits for while a worker is initializing it.

## Unbounded thread pools

`Executors.newCachedThreadPool()` and custom pools with no maximum create a thread for every
task when existing threads are busy. Under startup load this can mean dozens of threads, each
with its own stack (around 1 MB), more scheduler pressure, and more lock contention.

- Prefer shared dispatchers or a fixed pool sized to the work.
- When you find a cached pool behind a hot API, replacing it with a fixed pool is usually safe,
  because callers do not depend on the pool type.
- Count threads in a Perfetto trace or with `adb shell ps -T -p <pid> | wc -l`.

## Binder calls on main

`PackageManager`, `ActivityManager`, `AccountManager`, `ContentResolver`, `Settings`,
`TelephonyManager`, and calls to services in other processes all go over Binder. Each is
synchronous. Under system load, or when system_server's Binder threads are all busy, a call
that normally takes a millisecond can take seconds.

- Keep them off startup, resume, and input paths. Fetch once on IO and cache.
- In a trace, main in `Native` with `BinderProxy.transact` on top is waiting on another
  process. Perfetto shows the server side of the transaction; see [perfetto.md](perfetto.md).
- If system_server CPU is very high at the same time, it is likely `EXTERNAL`.

## Cancellation in tight loops

A CPU loop with no suspension point ignores cancellation and keeps running after the screen is
gone. Call `ensureActive()` per item, or `yield()` every few hundred items.

## Bounded waits

When main or a Binder thread genuinely has to wait for something (binding to a service, a
cross-process handoff), put an upper bound on the wait and decide what happens on timeout. One
push pipeline that bound to a service in another process used a 4 s bound on the connection,
well under the broadcast timeout, and dropped to a fallback path if it expired. An unbounded
wait turns a slow dependency into an ANR.
