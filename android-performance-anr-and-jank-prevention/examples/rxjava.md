# Samples: RxJava

## Contents
- observeOn placement
- Providers that switch to main too early
- blocking operators
- subscribeOn only once
- Bounded schedulers
- Interop with coroutines

## observeOn placement

```kotlin
// ❌ Parsing runs on main because it comes after observeOn
api.fetchOrderJson()
    .subscribeOn(Schedulers.io())
    .observeOn(AndroidSchedulers.mainThread())
    .map { json -> gson.fromJson(json, Order::class.java) }
    .subscribe(::render)

// ✅ All transformation before the switch; only rendering after it
api.fetchOrderJson()
    .subscribeOn(Schedulers.io())
    .map { json -> gson.fromJson(json, Order::class.java) }
    .observeOn(AndroidSchedulers.mainThread())
    .subscribe(::render)
```

Rule: `observeOn(mainThread())` is the last operator before `subscribe`.

## Providers that switch to main too early

```kotlin
// ❌ A data provider forces main on every consumer, so their parsing runs on main
fun unreadCount(): Observable<UnreadCount> =
    inboxApi.unread().observeOn(AndroidSchedulers.mainThread()).map(::parse)

// ✅ Providers stay on background schedulers; the UI layer observes on main
fun unreadCount(): Observable<UnreadCount> =
    inboxApi.unread().subscribeOn(Schedulers.io()).map(::parse)
```

## blocking operators

```kotlin
// ❌ Waits on main for a network-backed source
val user = userRepo.user().blockingGet()

// OK: seeded BehaviorSubject returns its current value immediately
val current = userSubject.blockingFirst()
```

## subscribeOn only once

Only the `subscribeOn` closest to the source takes effect. Put it in the data layer, and do not
rely on a later `subscribeOn` to move work off main.

## Bounded schedulers

`Schedulers.io()` grows its pool without limit. For bursts of small blocking tasks at startup,
use a bounded scheduler:

```kotlin
val prefsScheduler: Scheduler = Schedulers.from(Executors.newFixedThreadPool(4))
```

## Interop with coroutines

```kotlin
// kotlinx-coroutines-rx3
suspend fun loadConfig(): Config = configApi.getConfig().await()          // Single -> suspend
fun configRx(): Single<Config> = rxSingle(Dispatchers.IO) { repo.load() } // suspend -> Single
```
