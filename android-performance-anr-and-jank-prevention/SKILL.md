---
name: android-performance-anr-and-jank-prevention
description: >
  Exhaustive Android performance skill for writing ANR-free, frozen-frame-free, and janky-free
  code. Use this skill whenever writing, reviewing, or auditing Android code that involves:
  coroutines or threading (Dispatchers, withContext, runBlocking, GlobalScope, Mutex,
  synchronized), Android component lifecycles (Activity, Fragment, Service, BroadcastReceiver,
  JobService, ContentProvider), Jetpack Compose recomposition or state (remember, derivedStateOf,
  LazyColumn, Modifier, recomposition, stability), RecyclerView or Adapter code (onBindViewHolder,
  DiffUtil, ListAdapter), Binder IPC or system service calls (PackageManager, ContentResolver,
  AccountManager), SharedPreferences or DataStore, custom Views or onDraw, background work
  (WorkManager, coroutine scopes, JobScheduler), or any mention of ANR, frozen frames, jank,
  performance, StrictMode, Perfetto, or Android Vitals. Also use when the user asks how to
  analyze an ANR log, read a thread trace, interpret CPU usage in a bugreport, or distinguish
  app-side ANRs from system-induced ones. Trigger even for casual phrasings like "why is my app
  freezing", "how do I avoid ANR", "is this code safe to run on main thread", or "my app got an
  ANR in production". Covers View-based and Jetpack Compose UI systems, Android API levels 8
  through 35+.
---

# SKILL: ANR, Frozen Frames, and Main-Thread Safety (Exhaustive)

## Purpose and Scope

Use this skill when **writing, reviewing, or auditing** Android code to prevent Application Not
Responding (ANR) errors, frozen/janky frames, and any blocking or CPU-heavy work on the main
thread. Covers **View-based** and **Jetpack Compose** UI systems.

**ANR thresholds (AOSP/Pixel; OEMs may vary)**:
| Trigger | Timeout |
|---|---|
| Input dispatch (touch, key) blocked | 5 seconds |
| `BroadcastReceiver.onReceive` | 10 s (foreground) / 60 s (background) |
| Service `onCreate` / `onStartCommand` / `onBind` | ~20 seconds |
| `JobService.onStartJob` / `onStopJob` (Android 14+, explicit ANR) | few seconds |
| `startForegroundService` without calling `startForeground` | 5 s (Android 8–14) / **3 s (Android 15+)** |

**Frozen frame thresholds**: Any frame taking >16 ms (60 fps) causes jank. Frames >700 ms are
classified as "frozen frames" and tracked in Android Vitals.

**Android Vitals ANR rate**: Google Play surfaces user-perceived ANR rate (Input ANRs only). Your
bad behavior threshold is ≥ 0.47 % of daily active users.

---

## PART 0 — ANR SYSTEM DESIGN PHILOSOPHY

Understanding how Android's ANR mechanism works at the system level is essential for writing
proactively resilient code and for diagnosing failures when they occur.

### 0.1 ANR vs SNR — What Android Actually Monitors

Android draws a hard architectural line between two categories of unresponsiveness:

- **ANR (Application Not Responding)**: The application process failed to service a system-
  dispatched event within a timeout. This is always treated as an **application-layer** fault.
  Monitored via the message-scheduling mechanism inside `system_server` (AMS / InputDispatcher).
- **SNR (System Not Responding)**: The `system_server` process itself is unresponsive. Monitored
  by the `Watchdog` mechanism that polls key system threads.

Because these are separate monitoring systems, an app can be blamed for an ANR that was
genuinely caused by system resource exhaustion (high CPU load, Binder thread-pool saturation,
OEM freeze policies). Part 5 of this skill covers distinguishing the two during analysis.

### 0.2 Three Architectural ANR Types

| ANR Class | Who Detects | Root Trigger |
|---|---|---|
| **Component-class** | `ActivityManagerService` (AMS) | Service / Broadcast lifecycle callback not completed within timeout |
| **Input-class** | `InputDispatcher` | Touch or key event not consumed within 5 s |
| **No-Focused-Window** | `InputDispatcher` + WMS | System cannot find a legal focus window to route events to |

**Component-class ANR** — "bomb planting" model:
When AMS dispatches a cross-process task to your app via Binder (e.g. `scheduleCreateService`),
it simultaneously posts a delayed timeout message to its `MainHandler`. Your app must call back
via `serviceDoneExecuting()` / `finishReceiver()` before the bomb detonates. Even if you do the
real work on a background thread, any delay in the Binder callback (e.g., the main thread queue
is jammed by `runOnUiThread` calls) will still trigger ANR.

**Input-class ANR** — event pipeline: `EventHub` → `InputReader` → `InputDispatcher`
`InputDispatcher` maintains a `waitQueue` of events dispatched but not yet acknowledged. The 5 s
clock starts when the event is pushed into the window's `InputChannel`. Timeout detection is
event-driven (triggered on new events or periodic heartbeats), not a polling loop.

**No-Focused-Window ANR** — almost always a system issue:
Caused by abnormal window lifecycle during Activity transitions or when `handleResumeActivity`
is delayed. App code rarely causes this directly. When diagnosing, look at `system_server` CPU
load, Binder call delays between system services, and WMS logs — not just your app's stack.

### 0.3 ANR Circuit-Breaker Sequence (What Happens After Timeout)

1. **Scene collection**: AMS/InputDispatcher captures main thread stack, CPU usage, memory
   snapshot, and writes to ANR trace files.
   - Older devices/docs: `/data/anr/traces.txt`
   - Newer devices and bugreports: per-event `/data/anr/anr_*` files
2. **Resource isolation**: `ProcessRecord` scheduling priority is adjusted to ensure the ANR
   processing flow executes even under heavy system load.
3. **User decision**: The ANR dialog is shown (some OEM ROMs crash to the home screen instead).
   The system hands control to the user rather than making an automated kill decision.

This "fault isolation → scene protection → user decision" sequence is intentional: it prevents
cascade failures across the Binder thread pool while preserving forensic data.

### 0.4 Android Version ANR Changes

| Version | Change |
|---|---|
| Android 11 (API 30) | `ApplicationExitInfo` API: query historical ANR reasons in-process |
| Android 14 (API 34) | `ProcessStateRecord`: finer process state tracking; `JobService` ANRs are now **explicit** (reported to app) instead of silent |
| Android 15 (API 35) | Foreground service `startForeground()` timeout reduced from **5 s to 3 s** |

---

## PART 1 — COROUTINE DISPATCHER MISUSE

---

### 1.1 I/O Work on `Dispatchers.Default` — Thread Pool Starvation

**Root cause**: `Dispatchers.Default` has a fixed thread pool sized to CPU core count (minimum
2). Blocking those threads with I/O (network, disk, DB) starves CPU-bound work and can cause
thread starvation deadlocks.

```kotlin
// ❌ BAD: blocking file I/O on Default — exhausts CPU thread pool
suspend fun loadConfig(): Config = withContext(Dispatchers.Default) {
    File("/data/config.json").readText().let { gson.fromJson(it, Config::class.java) }
}

// ✅ CORRECT: I/O on Dispatchers.IO — elastic pool designed for blocking calls
suspend fun loadConfig(): Config = withContext(Dispatchers.IO) {
    File("/data/config.json").readText().let { gson.fromJson(it, Config::class.java) }
}

// ✅ CPU transform on Dispatchers.Default — correct use
suspend fun transformItems(raw: List<RawItem>): List<DomainItem> =
    withContext(Dispatchers.Default) { raw.map { it.toDomain() } }
```

**Dispatcher selection guide**:
| Work type | Dispatcher |
|---|---|
| Network (blocking HTTP), file read/write, SQLite, SharedPreferences | `Dispatchers.IO` |
| CPU-intensive: sorting, mapping large collections, crypto, image decoding | `Dispatchers.Default` |
| UI update, View access, Compose state mutation | `Dispatchers.Main` (or `Dispatchers.Main.immediate`) |
| Single-threaded sequential write of shared mutable state | `Dispatchers.IO.limitedParallelism(1)` |
| Room (suspend functions) | Room automatically uses `Dispatchers.IO` internally |
| Retrofit (suspend functions) | Retrofit automatically dispatches on `Dispatchers.IO` |

---

### 1.2 JSON / Protobuf Parsing on the Main Thread

**Root cause**: API response post-processing — `gson.fromJson`, `moshi.adapter().fromJson`,
`proto.parseFrom` — is CPU-bound work. It is invisible as blocking but can take 10–500 ms on
large payloads. When it happens on the Main thread (inside a `viewModelScope.launch {}` without
a `withContext` switch, or after `observeOn(mainThread())`), it contributes directly to ANRs.

```kotlin
// ❌ BAD: Retrofit suspend function delivers on Main thread;
//         post-processing (mapping) therefore runs on Main
class UserViewModel(private val api: UserApi) : ViewModel() {
    fun loadUser(id: String) {
        viewModelScope.launch {  // defaults to Dispatchers.Main in viewModelScope
            val dto = api.fetchUser(id)   // Retrofit does I/O on IO dispatcher correctly
            // The following map() runs back on Main because we're in Dispatchers.Main context
            val user = dto.toUser()       // ← Main thread CPU work; risky for large DTOs
            _uiState.value = UiState.Success(user)
        }
    }
}

// ✅ CORRECT: explicit withContext for any transformation after suspension
class UserViewModel(private val api: UserApi) : ViewModel() {
    fun loadUser(id: String) {
        viewModelScope.launch {
            val user = withContext(Dispatchers.IO) {
                val dto = api.fetchUser(id)   // network on IO
                dto.toUser()                  // mapping stays on IO
            }
            _uiState.value = UiState.Success(user)  // back on Main
        }
    }
}

// ✅ BEST: push all I/O + transformation to the Repository layer
class UserRepository(private val api: UserApi) {
    // This function is main-safe; callers don't need to add withContext
    suspend fun getUser(id: String): User = withContext(Dispatchers.IO) {
        api.fetchUser(id).toUser()
    }
}
```

### RxJava `observeOn` Placement — Operations After Switch Run on Main

```kotlin
// ❌ BAD: map{} is placed after observeOn(mainThread()) → JSON parsing on Main
api.fetchOrderRx()
    .subscribeOn(Schedulers.io())
    .observeOn(AndroidSchedulers.mainThread())   // ← switch to Main happens here
    .map { json -> gson.fromJson(json, Order::class.java) }  // ← runs ON MAIN
    .subscribe { render(it) }

// ✅ CORRECT: all transformations before observeOn; only terminal UI work after
api.fetchOrderRx()
    .subscribeOn(Schedulers.io())
    .map { json -> gson.fromJson(json, Order::class.java) }   // still on IO thread
    .observeOn(AndroidSchedulers.mainThread())
    .subscribe { render(it) }                                  // UI update on Main
```

**Rule**: `observeOn(mainThread())` is the last operator before `subscribe`. Every `map`,
`flatMap`, `filter` after it runs on the Main thread.

---

### 1.3 `runBlocking` on the Main Thread — ANR and Deadlock

**Root cause**: `runBlocking` blocks the calling thread until the coroutine finishes. Calling it
on Main blocks the entire UI pipeline. A classic deadlock occurs when the inner coroutine needs
to dispatch back to the Main thread — which is held by `runBlocking`.

```kotlin
// ❌ ANR: runBlocking in Activity lifecycle callback
class SplashActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Blocks Main thread — system cannot process input events — ANR in 5s
        val config = runBlocking { configRepository.fetch() }
    }
}

// ❌ DEADLOCK: inner coroutine needs Main; Main is blocked by runBlocking
fun getDataSync(): Data = runBlocking {
    withContext(Dispatchers.Main) {   // tries to post to Main — which is blocked by runBlocking → deadlock
        heavyWork()
    }
}

// ✅ CORRECT: always use lifecycle-scoped coroutines, never block Main
class SplashActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lifecycleScope.launch {
            val config = configRepository.fetch()
            applyConfig(config)
        }
    }
}
```

`runBlocking` is only valid in: unit test entry points, pure CLI `main()` functions.
Never in Android lifecycle callbacks, ViewModel methods, or Fragment/Activity code.

---

### 1.4 `GlobalScope` — Uncontrolled Lifetime, Hidden Leaks, Swallowed Errors

```kotlin
// ❌ BAD: GlobalScope escapes structured concurrency
fun syncData() {
    GlobalScope.launch(Dispatchers.IO) { repo.sync() }
    // Cannot cancel this from the caller; errors are silently dropped;
    // if repo.sync() hangs indefinitely, this coroutine lives forever
}

// ✅ CORRECT: inject a lifecycle-bound or application-scoped CoroutineScope
class SyncUseCase @Inject constructor(
    @ApplicationScope private val scope: CoroutineScope  // DI-provided, cancelled at app death
) {
    fun syncData(): Job = scope.launch(Dispatchers.IO) { repo.sync() }
}

// Application-scope definition (DI module)
@Provides @Singleton @ApplicationScope
fun provideApplicationScope(): CoroutineScope =
    CoroutineScope(SupervisorJob() + Dispatchers.Default)
```

---

### 1.5 Excessive `withContext` Switching — Context Switch Overhead

Each `withContext` call involves rescheduling the coroutine on a different thread pool. While
cheaper than thread context switches, they accumulate on hot paths.

```kotlin
// ❌ BAD: ping-pong between dispatchers — N context switches for N steps
suspend fun processOrder(id: String) {
    withContext(Dispatchers.Main) { showLoading() }
    withContext(Dispatchers.IO)   { val order = api.fetch(id) }
    withContext(Dispatchers.Main) { showOrder() }
    withContext(Dispatchers.IO)   { val history = api.fetchHistory(id) }
    withContext(Dispatchers.Main) { showHistory() }
}

// ✅ CORRECT: batch all I/O, single context switch back to Main
suspend fun processOrder(id: String) {
    showLoading()  // already on Main (viewModelScope default)
    val (order, history) = withContext(Dispatchers.IO) {
        val order   = api.fetch(id)
        val history = api.fetchHistory(id)
        Pair(order, history)
    }
    showOrder(order)    // back on Main — single switch
    showHistory(history)
}
```

---

### 1.6 `lazy` Thread Safety Mode Misuse

Kotlin's `lazy {}` defaults to `LazyThreadSafetyMode.SYNCHRONIZED` which acquires an intrinsic
monitor lock on every access until initialized. This is unnecessary — and adds CPU overhead — for
properties accessed only from a single thread (e.g., Main).

```kotlin
// ❌ BAD: SYNCHRONIZED mode on a Main-only UI property — lock overhead per access before init
class HomeFragment : Fragment() {
    private val adapter by lazy { HomeAdapter() }  // default = SYNCHRONIZED; unnecessary lock
    private val animation by lazy { LottieAnimation() }
}

// ✅ CORRECT: NONE mode for single-thread / Main-only properties
class HomeFragment : Fragment() {
    private val adapter    by lazy(LazyThreadSafetyMode.NONE) { HomeAdapter() }
    private val animation  by lazy(LazyThreadSafetyMode.NONE) { LottieAnimation() }
}

// ❌ BAD: SYNCHRONIZED lazy on a hot-path multi-thread object — lock contention
//         During initialization, all threads wait on the single lock
class IconManager {
    private val cache by lazy { buildHeavyIconCache() }  // 200ms init while others wait
}

// ✅ CORRECT: PUBLICATION mode if initialization is idempotent and can run in parallel
class IconManager {
    // Multiple threads may init but only the first result is stored — no lock wait
    private val cache by lazy(LazyThreadSafetyMode.PUBLICATION) { buildHeavyIconCache() }
}

// ✅ OR: initialize eagerly in DI / init block on a background thread
```

**`lazy` mode reference**:
| Mode | Lock behavior | Use case |
|---|---|---|
| `SYNCHRONIZED` | Acquires intrinsic lock; init runs exactly once | Multi-thread, expensive init, must run once |
| `PUBLICATION` | No lock; multiple threads may init, first stored | Multi-thread, idempotent init |
| `NONE` | No synchronization at all | Single-thread (Main-only UI properties) |

---

### 1.7 Lock and Mutex Misuse

#### `synchronized {}` with a Suspend Call — Deadlock

```kotlin
// ❌ DEADLOCK: thread is released at suspension point but the monitor lock is NOT released.
// Other threads waiting on the same lock are blocked indefinitely.
val lock = Any()
suspend fun updateCache() {
    synchronized(lock) {
        val data = fetchFromNetwork()  // suspend point — releases coroutine dispatcher, NOT the lock
        cache.put(data)
    }
}

// ✅ CORRECT: use Mutex (coroutine-aware lock — suspends, does not block the thread)
val mutex = Mutex()
suspend fun updateCache() {
    val data = fetchFromNetwork()  // suspend outside the lock
    mutex.withLock { cache.put(data) }
}
```

#### Nested Locks — Classic Deadlock

```kotlin
// ❌ DEADLOCK: Thread A acquires lockA then lockB; Thread B acquires lockB then lockA
fun threadA() { synchronized(lockA) { synchronized(lockB) { processA() } } }
fun threadB() { synchronized(lockB) { synchronized(lockA) { processB() } } }
// If A holds lockA and B holds lockB → each waits for the other → deadlock

// ✅ CORRECT option A: enforce consistent acquisition order across all code paths
// ✅ CORRECT option B: replace nested locks with a single-threaded dispatcher
val serialDispatcher = Dispatchers.IO.limitedParallelism(1)
suspend fun safeMutation() = withContext(serialDispatcher) {
    processA(); processB()  // only one coroutine at a time; no explicit lock needed
}
```

#### `ReentrantLock` Without `finally` — Lock Never Released

```kotlin
// ❌ BAD: exception between lock() and unlock() leaves lock permanently held
val lock = ReentrantLock()
fun doWork() {
    lock.lock()
    riskyOperation()   // throws → unlock() never called → all waiters blocked forever
    lock.unlock()
}

// ✅ CORRECT: always use withLock {} (Kotlin extension on Lock) or try/finally
fun doWork() {
    lock.withLock { riskyOperation() }  // releases even on exception
}
```

#### Mutex Re-entrance — Deadlock with Self

```kotlin
// ❌ DEADLOCK: Mutex is not reentrant — locking it twice on the same coroutine hangs
val mutex = Mutex()
suspend fun outer() {
    mutex.withLock {
        inner()  // calls mutex.withLock again → deadlock
    }
}
suspend fun inner() {
    mutex.withLock { /* ... */ }  // tries to acquire already-held mutex → suspends forever
}

// ✅ CORRECT: refactor to avoid re-entrance; use owner token for debugging
suspend fun inner() {
    // called only from within outer's locked section; does not re-acquire
    processInner()
}
```

---

### 1.8 Binder IPC on the Main Thread

Binder calls to system services or other processes are synchronous and can block for tens to
hundreds of milliseconds — more under system load. Every call to `PackageManager`,
`ActivityManager`, `ContentResolver.query`, system settings, or IPC to third-party processes
on the Main thread is an ANR risk.

```kotlin
// ❌ BAD: blocking Binder calls on Main
class StartupFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        // All of these are synchronous Binder calls to system services:
        val packages = requireContext().packageManager.getInstalledPackages(0)   // 200–500 ms
        val wifi     = Settings.Global.getInt(requireContext().contentResolver, Settings.Global.WIFI_ON, 0)
        val contacts = requireContext().contentResolver.query(ContactsContract.Contacts.CONTENT_URI, null, null, null, null)
    }
}

// ✅ CORRECT: move Binder calls to Dispatchers.IO
class StartupViewModel(private val pm: PackageManager) : ViewModel() {
    fun loadInstalledPackages() {
        viewModelScope.launch {
            val packages = withContext(Dispatchers.IO) { pm.getInstalledPackages(0) }
            _packageList.value = packages
        }
    }
}
```

**Enable StrictMode in debug builds to automatically surface Binder violations**:

```kotlin
if (BuildConfig.DEBUG) {
    StrictMode.setThreadPolicy(
        StrictMode.ThreadPolicy.Builder()
            .detectAll()
            .penaltyLog()        // Logcat in dev
            // .penaltyDeath()   // Use in CI to hard-fail on any violation
            .build()
    )
}
```

---

### 1.9 ContentProvider and AppInitializer on Main Thread

ContentProviders are initialized on the Main thread during process startup, before
`Application.onCreate()`. Any heavy work in `ContentProvider.onCreate()` directly blocks cold
start and can cause startup ANRs.

```kotlin
// ❌ BAD: synchronous SDK init in a ContentProvider (runs on Main at process start)
class MySdkInitProvider : ContentProvider() {
    override fun onCreate(): Boolean {
        HeavySdk.init(context!!)  // 300ms of reflection + I/O on Main at cold start
        return true
    }
}

// ✅ CORRECT option A: remove ContentProvider; init in Application.onCreate on background thread
class MyApp : Application() {
    @ApplicationScope @Inject lateinit var appScope: CoroutineScope

    override fun onCreate() {
        super.onCreate()
        appScope.launch(Dispatchers.IO) { HeavySdk.init(applicationContext) }
    }
}

// ✅ CORRECT option B: Jetpack App Startup with async initializer
class MySdkInitializer : Initializer<Unit> {
    override fun create(context: Context) {
        // Runs synchronously but you can chain dependencies explicitly
        // For async init: store a Deferred and await it lazily when first needed
    }
    override fun dependencies(): List<Class<out Initializer<*>>> = emptyList()
}
```

---

### 1.10 SharedPreferences on the Main Thread

`getSharedPreferences()` performs disk I/O on the **first call** and can block Main for
50–200 ms. `commit()` is always synchronous disk write; `apply()` is asynchronous but flushes
synchronously during Activity lifecycle teardown, which can cause ANRs.

```kotlin
// ❌ BAD: SharedPreferences disk I/O on Main
class SettingsFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val pref = requireContext()
            .getSharedPreferences("user_prefs", Context.MODE_PRIVATE)  // disk read on Main
            .getString("token", null)
        render(pref)
    }
}

// ❌ BAD: commit() is a synchronous disk write — blocks Main
prefs.edit().putString("key", value).commit()

// ✅ CORRECT: read on IO; cache in memory; write with apply()
class TokenRepository @Inject constructor(
    @ApplicationContext context: Context
) {
    private val prefs by lazy(LazyThreadSafetyMode.NONE) {
        context.getSharedPreferences("user_prefs", Context.MODE_PRIVATE)
    }

    suspend fun readToken(): String? = withContext(Dispatchers.IO) {
        prefs.getString("token", null)
    }

    fun writeToken(token: String) {
        prefs.edit().putString("token", token).apply()  // async; never use commit()
    }
}

// ✅ BETTER: migrate to DataStore (fully coroutine-based, no synchronous writes)
val Context.userPrefsStore by preferencesDataStore("user_prefs")
```

---

### 1.11 BroadcastReceiver — Heavy Work in `onReceive`

`onReceive` runs on the Main thread. The system ANRs the receiver at 10 seconds. Even before
10 seconds, any blocking work delays input handling.

**Critical `goAsync()` misconception**: `goAsync()` does **not** stop the
ANR timer. It converts the synchronous lifecycle callback into an asynchronous one, but the
10-second timeout still runs from the moment `onReceive` starts to when `PendingResult.finish()`
is called. If your background thread's work exceeds the timeout, ANR fires — even if your main
thread returned immediately.

```kotlin
// ❌ BAD: network call in onReceive — blocks Main for unknown duration
class PushReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val result = networkClient.syncNow()  // BLOCKS Main
        showNotification(context, result)
    }
}

// ❌ SUBTLE BUG: goAsync is used but PendingResult.finish() may be called after 10s timeout
// ANR still fires if the sub-thread work exceeds the broadcast timeout limit
class PushReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()               // timer is still running from this point
        Thread {
            Thread.sleep(12_000)              // 12s of work — ANR fires at 10s even in background thread
            pending.finish()
        }.start()
    }
}

// ✅ CORRECT option A: use goAsync() only for short work (<10s); always call finish()
class PushReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val result = networkClient.syncNow()
                showNotification(context, result)
            } finally {
                pending.finish()  // REQUIRED: call this before timeout, or system ANRs anyway
            }
        }
    }
}

// ✅ CORRECT option B: delegate to WorkManager (preferred for anything >few seconds)
class PushReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        WorkManager.getInstance(context).enqueue(
            OneTimeWorkRequestBuilder<SyncWorker>().build()
        )
        // onReceive returns immediately; no pending.finish() needed
    }
}
```

---

### 1.12 Service Lifecycle ANRs

```kotlin
// ❌ ANR: long-running blocking work in onStartCommand (Main thread)
class DownloadService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        downloadFile(intent?.getStringExtra("url"))  // blocks Main → ANR at ~20s
        return START_NOT_STICKY
    }
}

// ✅ CORRECT: dispatch to background; stop self when done
class DownloadService : Service() {
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val url = intent?.getStringExtra("url") ?: return START_NOT_STICKY
        serviceScope.launch {
            try { downloadFile(url) }
            finally { stopSelf(startId) }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() { serviceScope.cancel() }
}

// Android 8+: startForegroundService must call startForeground within 5 seconds (3s on Android 15+)
class ForegroundDownloadService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIF_ID, buildNotification())  // MUST be called immediately — 3s limit on API 35+
        // ... dispatch work
        return START_NOT_STICKY
    }
}
```

---

### 1.13 JobService ANR (Android 14+ Explicit)

```kotlin
// Android 14+: JobService.onStartJob / onStopJob must return quickly from the Main thread.
// Blocking work triggers explicit ANR with "No response to onStartJob".

// ❌ BAD: blocking work in onStartJob (Main thread)
class SyncJobService : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        syncData()  // blocking on Main → ANR on Android 14+
        return false
    }
}

// ✅ CORRECT: dispatch async; call jobFinished when done
class SyncJobService : JobService() {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onStartJob(params: JobParameters): Boolean {
        scope.launch {
            syncData()
            jobFinished(params, false)  // false = no reschedule
        }
        return true  // true = work is ongoing; system won't ANR
    }

    override fun onStopJob(params: JobParameters): Boolean {
        scope.cancel()
        return true  // true = reschedule
    }
}
```

---

### 1.14 Cooperative Cancellation — Tight Loops That Ignore Cancellation

A coroutine that never checks for cancellation continues running after its scope is cancelled,
consuming CPU and potentially updating a destroyed UI.

```kotlin
// ❌ BAD: infinite loop; scope cancellation has no effect
suspend fun processAll(items: List<Item>) {
    for (item in items) {
        heavyTransform(item)  // no suspension point — cancellation is never checked
    }
}

// ✅ CORRECT: ensureActive() checks cancellation at each iteration; throws CancellationException
suspend fun processAll(items: List<Item>) {
    for (item in items) {
        ensureActive()          // cooperative cancellation checkpoint
        heavyTransform(item)
    }
}

// ✅ For very tight loops: yield() provides a suspension + cancellation point
suspend fun crunch(data: LargeDataSet) = withContext(Dispatchers.Default) {
    data.forEachIndexed { index, value ->
        if (index % 500 == 0) yield()  // give scheduler and cancellation a chance
        compute(value)
    }
}
```

---

### 1.15 Binder Thread Pool Exhaustion — System-Induced ANR

The Binder driver limits each process to a maximum of 15 threads in its thread pool
(`BINDER_MAX_POOL_THREADS = 15`). When all Binder threads in `system_server` are busy (e.g.,
during a burst of app launches or heavy ContentProvider queries), your Binder calls to system
services block indefinitely on the calling side — regardless of how clean your main thread is.
This is a **system-induced ANR** that your code alone cannot prevent, but you can reduce
exposure to it.

```kotlin
// Patterns that place excessive load on the system Binder thread pool:

// ❌ BAD: querying multiple system services sequentially on startup
class StartupActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Each call below is a Binder round-trip to system_server.
        // Under load, any one of them can block for hundreds of ms or seconds.
        val pm   = packageManager.getInstalledPackages(0)          // Binder → PMS
        val accs = getSystemService(AccountManager::class.java)
                     .getAccountsByType("com.google")              // Binder → AMS
        val crs  = contentResolver.query(CONTACTS_URI, ...)        // Binder → ContentProvider
    }
}

// ✅ CORRECT: batch and defer all system service calls off the main thread
class StartupViewModel : ViewModel() {
    val startupData = viewModelScope.async(Dispatchers.IO) {
        val pm    = appContext.packageManager.getInstalledPackages(0)
        val accts = accountManager.getAccountsByType("com.google")
        StartupData(pm, accts)
    }
}
```

**Diagnosis signal in ANR log**: If main thread stack shows
`at com.android.internal.os.BinderProxy.transact` and CPU shows `system_server` at very high
usage (>100% across its threads), suspect Binder thread-pool pressure rather than app logic.

---

### 1.16 OEM App-Freezing ANR (Power-Optimization False Positive)

OEM Android distributions (especially Asian-market ROMs: OPPO, Vivo, Xiaomi, Huawei) implement
aggressive app-freezing policies (e.g., `HansManager`, `RefrigeratorManager`) to save battery.
When the screen turns off, they send a SIGSTOP-equivalent to background apps. If your app
receives an input event (e.g., back key, remote notification) while frozen, the system may time
out waiting for an acknowledgment and generate an ANR — even though your app code is correct.

**How to identify in the log**:
```
# App was frozen at screen-off:
OemPowerManager : freeze uid: 10182 package: com.example.myapp reason: LcdOff

# Back key dispatched to the frozen app — no response for 5s → ANR
WindowManager: Input event dispatching timed out sending to com.example.myapp

# System unfreezes app only *after* ANR is triggered:
OemPowerManager : unfreeze uid: 10182 package: com.example.myapp reason: Signal
```

**Resolution**: This is a **system-layer bug**, not an app code fix. When you see this pattern:
1. Do not spend time profiling your app code — it is correct.
2. Report to the OEM's developer relations channel with the freeze/unfreeze log evidence.
3. As a mitigation, minimize work done on app resume so your app can re-respond quickly after
   being unfrozen (keep `onResume` and `onStart` as lightweight as possible).
4. In your ANR monitoring dashboard, tag ANRs where `unfreeze … reason: Signal` appears
   within 1–2 seconds after `am_anr` — these are OEM-system false positives.

---

## PART 2 — VIEW-BASED SPECIFIC MAIN-THREAD ISSUES

---

### 2.1 Layout Inflation Cost

Layout inflation is synchronous on the Main thread. Each XML element involves `createViewFromTag`,
attribute resolution via `nativeApplyStyle`, and `setContentView`. Complex or deeply nested
layouts inflate slowly.

```kotlin
// ❌ BAD: inflating a large, always-present layout that contains optional sections
// All views in the layout are inflated even if they will never be shown
override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
    return inflater.inflate(R.layout.fragment_dashboard_with_everything, container, false)
}

// ✅ CORRECT: use ViewStub for optional UI — zero inflation cost until stub.inflate() is called
// In XML:
// <ViewStub
//     android:id="@+id/stub_error_state"
//     android:layout="@layout/layout_error_state"
//     android:inflatedId="@+id/error_root"
//     android:layout_width="match_parent"
//     android:layout_height="wrap_content" />

// Inflate on demand:
if (errorVisible) {
    val errorView = binding.stubErrorState.inflate()
}

// ✅ CORRECT: AsyncLayoutInflater for off-thread inflation (pre-Compose)
AsyncLayoutInflater(requireContext()).inflate(R.layout.heavy_list_item, container) { view, _, _ ->
    container?.addView(view)
}
```

---

### 2.2 RecyclerView `onBindViewHolder` — Heavy Work

`onBindViewHolder` runs on the Main thread for every visible item during scroll. Any filtering,
sorting, parsing, or network call here causes frames to be dropped.

```kotlin
// ❌ BAD: expensive work in bind
class PostAdapter(private val rawPosts: List<RawPost>) :
    RecyclerView.Adapter<PostViewHolder>() {

    override fun onBindViewHolder(holder: PostViewHolder, position: Int) {
        // Filtering on Main per bind — O(n) for every scroll frame
        val activePosts = rawPosts.filter { it.isActive }
        val post = activePosts[position]
        // String formatting / Gson parsing per bind
        val price = gson.fromJson(post.priceJson, Price::class.java)
        holder.bind(post, price)
    }
}

// ✅ CORRECT: pre-process in ViewModel; bind only assigns values
class PostAdapter : ListAdapter<Post, PostViewHolder>(PostDiffCallback()) {
    override fun onBindViewHolder(holder: PostViewHolder, position: Int) {
        holder.bind(getItem(position))  // Post is already processed domain model
    }
}

// ViewModel pre-processes before submitting to adapter:
viewModelScope.launch {
    val posts = withContext(Dispatchers.Default) {
        rawPosts.filter { it.isActive }.map { it.toDomainPost() }
    }
    adapter.submitList(posts)
}
```

### DiffUtil Must Run Off Main

```kotlin
// ❌ BAD: calculateDiff on Main thread — blocks UI during large list changes
val diff = DiffUtil.calculateDiff(MyDiffCallback(old, new))
adapter.dispatchUpdatesFrom(diff)

// ✅ CORRECT: ListAdapter uses AsyncListDiffer internally — DiffUtil runs on a background thread
adapter.submitList(newList)

// ✅ CORRECT for manual DiffUtil:
viewModelScope.launch {
    val diff = withContext(Dispatchers.Default) {
        DiffUtil.calculateDiff(MyDiffCallback(oldList, newList))
    }
    adapter.applyDiff(diff)
}
```

---

### 2.3 `onDraw` — Allocations and Heavy Computation

`onDraw` is called for every frame. Object allocation inside `onDraw` causes GC pressure that
interrupts frame rendering.

```kotlin
// ❌ BAD: Paint, Path, and RectF allocated on every frame
class GraphView(context: Context) : View(context) {
    override fun onDraw(canvas: Canvas) {
        val paint = Paint()           // GC pressure every frame
        val path = Path()
        val rect = RectF(0f, 0f, width.toFloat(), height.toFloat())
        paint.color = Color.RED
        canvas.drawRect(rect, paint)
    }
}

// ✅ CORRECT: allocate objects once in init or as class-level fields
class GraphView(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.RED }
    private val path  = Path()
    private val rect  = RectF()

    override fun onDraw(canvas: Canvas) {
        rect.set(0f, 0f, width.toFloat(), height.toFloat())
        canvas.drawRect(rect, paint)
    }
}
```

---

## PART 3 — JETPACK COMPOSE SPECIFIC ANR / FROZEN FRAMES

---

### 3.1 Heavy Work During Composition Phase

The Composition phase runs on the Main thread. Any slow computation called directly in a
composable body (not in `remember` or `LaunchedEffect`) blocks the Main thread on every
recomposition.

```kotlin
// ❌ BAD: expensive sort on every recomposition (including trivial state changes)
@Composable
fun ContactList(contacts: List<Contact>, comparator: Comparator<Contact>) {
    val sorted = contacts.sortedWith(comparator)  // O(n log n) on Main, every recompose
    LazyColumn { items(sorted) { ContactRow(it) } }
}

// ✅ CORRECT: wrap in remember(key) — recomputed only when inputs change
@Composable
fun ContactList(contacts: List<Contact>, comparator: Comparator<Contact>) {
    val sorted = remember(contacts, comparator) { contacts.sortedWith(comparator) }
    LazyColumn { items(sorted, key = { it.id }) { ContactRow(it) } }
}

// ✅ BEST: move computation to ViewModel — composable receives a ready-to-render list
class ContactViewModel : ViewModel() {
    val sortedContacts: StateFlow<List<Contact>> = combine(rawContacts, comparatorFlow) { list, cmp ->
        withContext(Dispatchers.Default) { list.sortedWith(cmp) }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
}
```

---

### 3.2 Backwards State Writes — Infinite Recomposition Loop

Writing to state after reading it in the same composition causes Compose to immediately schedule
another recomposition, creating an infinite loop that pegs the Main thread.

```kotlin
// ❌ BAD: writes state after reading it → infinite recomposition loop → frozen frame / ANR
@Composable
fun BadCounter() {
    var count by remember { mutableIntStateOf(0) }
    Text("$count")
    count++   // backwards write: state was read above, now written → endless recompose loop
}

// ✅ CORRECT: write state only inside event handlers or LaunchedEffect; never during composition
@Composable
fun GoodCounter() {
    var count by remember { mutableIntStateOf(0) }
    Text("Count: $count")
    Button(onClick = { count++ }) { Text("Increment") }
}
```

---

### 3.3 Reading High-Frequency State at the Wrong Composition Scope

Reading rapidly-changing state (e.g., scroll offset, animation value) at a parent composable
forces the entire subtree to recompose on every frame.

```kotlin
// ❌ BAD: reading scroll offset at the top-level composable forces full tree recompose on every scroll
@Composable
fun CollapsingToolbar() {
    val listState = rememberLazyListState()
    val offset = listState.firstVisibleItemScrollOffset  // read here → all children recompose on scroll
    Toolbar(offset = offset)
    LazyColumn(state = listState) { /* ... */ }
}

// ✅ CORRECT option A: derivedStateOf — recompose only when first visible item *index* changes
@Composable
fun CollapsingToolbar() {
    val listState = rememberLazyListState()
    val isCollapsed by remember { derivedStateOf { listState.firstVisibleItemIndex > 0 } }
    // Only recomposes when isCollapsed changes (crossing item boundary), not on every pixel scroll
    AnimatedVisibility(visible = isCollapsed) { CollapsedToolbar() }
    LazyColumn(state = listState) { /* ... */ }
}

// ✅ CORRECT option B: defer the read to the leaf composable via lambda (Jetsnack pattern)
@Composable
fun CollapsingToolbar(scrollProvider: () -> Int) {
    val offset = scrollProvider()   // read only during this composable's layout/draw, not its parent's
    // ...
}
// At call site:
CollapsingToolbar(scrollProvider = { listState.firstVisibleItemScrollOffset })
```

---

### 3.4 Unstable Parameters — Forced Recomposition

Compose marks a composable as **skippable** only when all its parameters are stable. Unstable
parameters (mutable collections, un-annotated complex classes) force recomposition even when the
data hasn't changed.

```kotlin
// ❌ BAD: List<T> is an interface — Compose cannot guarantee it's immutable → unstable
@Composable
fun OrderList(orders: List<Order>) {
    orders.forEach { OrderRow(it) }
}
// Every parent recomposition forces OrderList to recompose, even if orders hasn't changed

// ✅ CORRECT option A: use @Immutable on data classes
@Immutable
data class Order(val id: String, val total: Double)
// Now Compose can skip OrderList if 'orders' reference hasn't changed

// ✅ CORRECT option B: use Kotlinx Immutable Collections
@Composable
fun OrderList(orders: ImmutableList<Order>) {  // kotlinx.collections.immutable.ImmutableList
    orders.forEach { OrderRow(it) }
}

// ✅ CORRECT option C: if mutation is needed, isolate state in ViewModel; expose StateFlow<List<T>>
```

---

### 3.5 Missing `key` in `LazyColumn`/`LazyRow` — Unnecessary Full Rebind

Without stable keys, Compose uses positional identity for list items. When items are added,
removed, or reordered, every item below the changed position is considered new → full recompose +
rebind for the entire visible list.

```kotlin
// ❌ BAD: no key — item at position 0 changes → every other item recomposed
LazyColumn {
    items(notes) { note ->
        NoteRow(note)
    }
}

// ✅ CORRECT: stable key — Compose knows which item moved, recomposes only changed ones
LazyColumn {
    items(notes, key = { note -> note.id }) { note ->
        NoteRow(note)
    }
}

// ✅ For indexed lists:
LazyColumn {
    itemsIndexed(orders, key = { _, order -> order.orderId }) { index, order ->
        OrderRow(index, order)
    }
}
```

---

### 3.6 Side Effects Inside Composable Body — Work on Composition Phase

Running side effects (network calls, Toast, logging, analytics) directly in the composable body
runs them during the Composition phase on the Main thread, on every recomposition.

```kotlin
// ❌ BAD: network call directly in composition — blocks Main on every recompose
@Composable
fun ProductScreen(productId: String) {
    val product = runBlocking { productRepo.fetch(productId) }  // BLOCKS Main
    Text(product.name)
}

// ❌ BAD: Toast shown on every recomposition
@Composable
fun WelcomeScreen() {
    Toast.makeText(LocalContext.current, "Welcome!", Toast.LENGTH_SHORT).show()
}

// ✅ CORRECT: async work in LaunchedEffect; one-shot effects with key = Unit
@Composable
fun ProductScreen(productId: String, viewModel: ProductViewModel = hiltViewModel()) {
    LaunchedEffect(productId) {
        viewModel.loadProduct(productId)   // dispatched; does not block Main
    }
    val product by viewModel.product.collectAsState()
    product?.let { Text(it.name) }
}

@Composable
fun WelcomeScreen() {
    val context = LocalContext.current
    LaunchedEffect(Unit) { Toast.makeText(context, "Welcome!", Toast.LENGTH_SHORT).show() }
}
```

---

### 3.7 Modifier Chain Overhead — Lambda vs Value Modifiers

Some `Modifier` functions have lambda variants that defer state reads to the draw/layout phase,
avoiding full recomposition for frequently-changing values like scroll offset or animation progress.

```kotlin
// ❌ BAD: Modifier.offset(x, y) reads state during Composition phase → full recompose on every scroll
@Composable
fun ScrollingHeader(scrollState: ScrollState) {
    val offset = scrollState.value
    Box(modifier = Modifier.offset(y = (-offset).dp)) { /* header */ }
}

// ✅ CORRECT: Modifier.offset { } lambda is evaluated in Layout phase, not Composition
// → no recomposition triggered; only the layout phase re-runs
@Composable
fun ScrollingHeader(scrollState: ScrollState) {
    Box(modifier = Modifier.offset { IntOffset(0, -scrollState.value) }) { /* header */ }
}

// Similar deferred lambda variants:
// Modifier.graphicsLayer { }    instead of Modifier.graphicsLayer(alpha = ...)
// Modifier.drawBehind { }       instead of Canvas + drawBehind value
// Modifier.background { }       for dynamic colors
```

---

### 3.8 `remember` with Expensive Inline Computation — No Key

Objects created in `remember {}` without keys are created once and reused. If the creation is
expensive but should update when a dependency changes, missing the key means stale data is served.
If the key is included, stale data is avoided but the object is re-created correctly.

```kotlin
// ❌ BAD: always serves the first chart config — stale when dataSet changes
@Composable
fun ChartScreen(dataSet: DataSet) {
    val chartConfig = remember { ChartConfig.from(dataSet) }  // never updates when dataSet changes
    Chart(config = chartConfig)
}

// ✅ CORRECT: invalidate when dataSet changes
@Composable
fun ChartScreen(dataSet: DataSet) {
    val chartConfig = remember(dataSet) { ChartConfig.from(dataSet) }
    Chart(config = chartConfig)
}
```

---

## PART 4 — ANR ANALYSIS FRAMEWORK

When an ANR surfaces (from Android Vitals, a bug report, or `ApplicationExitInfo`), follow this
structured workflow to distinguish app bugs from system-induced failures and find root cause.

### 4.1 General ANR Analysis Steps

```
1. Locate the exact ANR time
   └─ Search EventLog for "am_anr" — this timestamp is the most accurate
      e.g.  am_anr: [0, 2169, com.example.app, 820526660, Input dispatching timed out ...]

2. Read the ANR reason from MainLog / SystemLog
   └─ Search for "ANR in" to find:
      • Time of ANR          • Process name & PID   • Reason string
      • CPU load (1/5/15min) • CPU usage per process (before and during ANR)
      • Memory pressure (PSI)

3. Assess system state at ANR time
   └─ Was CPU load > 3× the core count? (system-wide overload)
   └─ Was system_server or surfaceflinger consuming >50%?
   └─ Were there lowmemorykiller events? kswapd0 running continuously?
   └─ Was iowait high? (major page faults count in CPU log)
   └─ Were other apps being killed (am_kill, am_proc_died)?

4. Read the thread stacks in the ANR trace file
   └─ Is the main thread Blocked, TimedWaiting, or Native (normal idle)?
   └─ If Blocked: which lock? which thread holds it?
   └─ If Native: is it a Binder call? Which system service?
   └─ Cross-reference with worker threads — who holds the lock the main thread wants?

5. Collect context window (5 seconds before am_anr timestamp)
   └─ Combine EventLog + MainLog + SystemLog into one file
   └─ Look for: unlock events, app launches, screen on/off, OEM freeze/unfreeze logs
   └─ Look for: Slow operation, Slow dispatch, Slow delivery, dvm_lock_sample

6. If inconclusive: add tracing or reproduce locally
   └─ Enable StrictMode with penaltyDeath() in debug build
   └─ Capture Perfetto trace for timeline correlation
```

### 4.2 Reading ANR Thread State in `traces.txt` / `anr_*` Files

A normal idle main thread looks like this — `nativePollOnce` means the Looper is waiting for
messages, which is healthy:

```
"main" prio=5 tid=1 Native
  | state=S  ...
  native: #00 ... libc.so (__epoll_pwait+8)
  native: #01 ... libutils.so (android::Looper::pollInner+184)
  at android.os.MessageQueue.nativePollOnce(Native method)
  at android.os.Looper.loop(Looper.java:198)
  at android.app.ActivityThread.main(ActivityThread.java:8142)
```

An ANR-causing blocked main thread looks like this — `Blocked` state waiting for a lock:

```
"main" prio=5 tid=1 Blocked
  | state=S  ...
  at com.example.SomeClass.doWork(SomeClass.java:98)
  - waiting to lock <0x0e57c91f> (a java.lang.Object) held by thread 34
  at android.os.Handler.dispatchMessage(Handler.java:99)
  at android.os.Looper.loop(Looper.java:254)
  at android.app.ActivityThread.main(ActivityThread.java:8142)
```

**Key thread state reference** (from `art/runtime/thread_state.h`):

| State in trace | Java `Thread.State` | Meaning |
|---|---|---|
| `Native` | RUNNABLE | Executing JNI / waiting in Looper epoll (normal idle) |
| `Runnable` | RUNNABLE | Actively executing Java code |
| `Blocked` | BLOCKED | Waiting for a monitor lock (another thread holds it) |
| `Waiting` | WAITING | In `Object.wait()` with no timeout |
| `TimedWaiting` | TIMED_WAITING | In `Object.wait(timeout)` or `Thread.sleep()` |
| `Sleeping` | TIMED_WAITING | In `Thread.sleep()` |
| `kWaitingForGcToComplete` | WAITING | GC pause — GC-pressure ANR |
| `kNative` | RUNNABLE | In a JNI native method |
| `Suspended` | RUNNABLE | Suspended by GC or debugger |

When reading the trace: find the `"main"` thread entry, note its state, then follow any
`waiting to lock <0x...> held by thread N` references to thread N's stack to understand the
lock chain.

### 4.3 CPU Usage Log Interpretation

The CPU section printed in `"ANR in"` log lines contains two time windows:

```
// Window 1: ~13s window covering the ANR
CPU usage from 0ms to 13135ms later:
  191%  1948/system_server: 72% user + 119% kernel / faults: 78816 minor 9 major
  30%   5991/com.example.app: 23% user + 6.4% kernel / faults: 118172 minor 2 major

// Window 2: ~1s window (snapshot closer to ANR)
CPU usage from 246ms to 1271ms later:
  290%  1948/system_server: 114% user + 176% kernel / faults: 9353 minor
  44%   5991/com.example.app: 37% user + 7.4% kernel
```

**CPU load line**:
```
Load: 15.29 / 5.19 / 1.87   ← 1-min / 5-min / 15-min average load
```
Values significantly above the device's CPU core count indicate system-wide overload. On an
8-core device, a 1-minute load of 15 is extreme overload — system-induced ANR is likely.

**Page faults**:
- `minor` faults = page already in memory cache (normal memory access activity)
- `major` faults = page had to be read from disk = **disk I/O** = potential ANR contributor.
  A high `major` count on the ANR process itself suggests the app is doing heavy I/O.
  A high `major` count on `system_server` or `kswapd0` suggests memory pressure.

### 4.4 Distinguishing App Bug vs System-Induced ANR

**Strong signals that the ANR is an application bug**:
- Main thread `Blocked` on a lock your own code created
- Main thread in a `synchronized {}` block doing I/O or waiting for a sub-thread result
- Main thread stack shows your code in a Binder call to a service you host
- CPU usage of your process is very high before the ANR (tight loop, heavy compute)
- No system-wide load or memory pressure

**Strong signals that the ANR is system-induced**:
- Main thread `Native` (idle Looper) — message dispatch simply never arrived
- OEM freeze/unfreeze logs around the ANR time (`HansManager`, `RefrigeratorManager`, etc.)
- `system_server` or `surfaceflinger` CPU usage is extremely high
- High `major` page faults on `system_server`, or `kswapd0` continuously active
- Multiple unrelated apps ANR-ing in the same time window
- Load average >> device core count for sustained periods

If system-induced, the fix is on the OEM/system side. Your mitigation is to keep lifecycle
callbacks lightweight so the app recovers quickly after system load subsides.

---

## PART 5 — REAL-WORLD ANR PATTERNS AND DEFENSES

### 5.1 Deadlock Between Main Thread and Worker Thread (Lock Inversion)

**Pattern**: Main thread calls into a utility (e.g., logging, image cache, analytics) that holds
Lock A and tries to acquire Lock B. A background worker holds Lock B and tries to acquire Lock A.

```kotlin
// ❌ DEADLOCK PATTERN observed in production:
// Main thread:   holds nothing → acquires EventLogger lock → needs DatabaseHelper lock
// Worker thread: holds DatabaseHelper lock → needs EventLogger lock
//
// Thread 1 (main): waiting to lock EventLogger, held by thread 34
// Thread 34 (EventLogger worker): locked EventLogger, waiting on AtomicInteger in DatabaseHelper

// SYMPTOMS in ANR trace:
// "main" prio=5 tid=1 Blocked
//   at com.example.EventLogger.logEvent(EventLogger.java:98)
//   - waiting to lock <0x0d3fbd00> held by thread 34
//
// "EventLogger" prio=5 tid=34 TimedWaiting
//   at java.lang.Object.wait(...)
//   - waiting on <0x00fc7065> (AtomicInteger)
//   - locked <0x0d3fbd00> (a EventLogger)  ← holds the lock main thread wants

// ✅ PREVENTION:
// 1. Never hold a lock while calling into a system or third-party API
// 2. Use a single-threaded dispatcher instead of nested synchronized blocks
// 3. In crash/log handlers, avoid any synchronized calls that may contend with worker threads
val logDispatcher = Dispatchers.IO.limitedParallelism(1)
suspend fun logEvent(event: Event) = withContext(logDispatcher) {
    // All log writes serialized here — no explicit lock needed
    db.insert(event)
}
```

### 5.2 RenderThread Blocking Main Thread (`nSyncDraw`)

The `RenderThread` performs GPU operations independently. However, before each frame, the main
thread calls `nSyncDraw` to hand off draw commands, which **blocks the main thread** until the
RenderThread's previous frame completes. If the RenderThread is slow (heavy canvas operations,
large bitmaps, shader compilation), the main thread is directly delayed.

```
// Signature in ANR trace — main thread waiting for RenderThread:
"main" prio=5 tid=1 Native
  native: ... libhwui.so (RenderProxy::syncAndDrawFrame)
  at android.view.ThreadedRenderer.nSyncAndDrawFrame(Native method)
  at android.view.ThreadedRenderer.draw(ThreadedRenderer.java)
  at android.view.ViewRootImpl.draw(ViewRootImpl.java)
```

```kotlin
// ❌ BAD: large Bitmap decoded on Main then passed to canvas — blocks RenderThread
class HeavyView(context: Context) : View(context) {
    private var bitmap: Bitmap? = null
    fun setImage(path: String) {
        // Decoding a 10 MB image takes 100-500ms — RenderThread is then busy with it
        bitmap = BitmapFactory.decodeFile(path)
        invalidate()
    }
}

// ✅ CORRECT: decode on IO dispatcher; scale to display size before handing to RenderThread
class HeavyView(context: Context) : View(context) {
    private var bitmap: Bitmap? = null
    suspend fun setImage(path: String, targetWidth: Int, targetHeight: Int) {
        bitmap = withContext(Dispatchers.IO) {
            val opts = BitmapFactory.Options().apply {
                inJustDecodeBounds = true
                BitmapFactory.decodeFile(path, this)
                inSampleSize = calculateInSampleSize(this, targetWidth, targetHeight)
                inJustDecodeBounds = false
            }
            BitmapFactory.decodeFile(path, opts)
        }
        invalidate()   // now back on Main; bitmap is correctly sized
    }
}
```

### 5.3 `SharedPreferences.apply()` Flush at Activity Stop — Silent ANR

`apply()` writes asynchronously, but the pending write is flushed synchronously during
`QueuedWork.waitToFinish()`, which is called on the **main thread** in `handleStopActivity` and
`handleServiceArgs`. On slow storage, this causes ANRs that appear in the trace as waiting in
`QueuedWork` rather than in your own code.

```
// ANR trace signature for apply() flush:
"main" prio=5 tid=1 Waiting
  at java.lang.Object.wait(Native method)
  at com.android.internal.util.QueuedWork.waitToFinish(QueuedWork.java:...)
  at android.app.ActivityThread.handleStopActivity(ActivityThread.java:...)
```

```kotlin
// ❌ BAD: apply() accumulates pending writes that flush at Activity stop
class SettingsManager(private val prefs: SharedPreferences) {
    fun saveAll(settings: AppSettings) {
        prefs.edit()
            .putString("theme", settings.theme)
            .putBoolean("notifications", settings.notifications)
            .putInt("fontSize", settings.fontSize)
            .apply()  // safe in isolation, but if called many times, flush can take 200-500ms
    }
}

// ✅ BEST: migrate to DataStore — fully coroutine-based, no synchronous QueuedWork flush
val Context.settingsStore by dataStore("settings", SettingsSerializer)

class SettingsRepository(private val store: DataStore<AppSettings>) {
    val settings: Flow<AppSettings> = store.data
    suspend fun save(settings: AppSettings) { store.updateData { settings } }
}
```

### 5.4 Input ANR from Main Thread Blocked in `nSyncDraw` During Heavy Startup

During cold start, if the first frame takes too long (heavy `onCreate`, complex layouts,
synchronous I/O), the `InputDispatcher` 5-second clock starts as soon as the window is focused
— even before the first frame is drawn. Touches during this window can trigger input ANRs.

```kotlin
// ✅ Defence: defer all non-critical startup work past the first frame
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        // Post heavy work AFTER the first frame to avoid blocking input dispatch
        window.decorView.post {
            // This runs after the first layout and draw pass
            lifecycleScope.launch(Dispatchers.IO) { performHeavyStartup() }
        }
    }
}
```

---

## PART 6 — GUARDRAILS AND DETECTION

### 6.1 StrictMode — Catch Violations in Dev / CI

```kotlin
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) {
            StrictMode.setThreadPolicy(
                StrictMode.ThreadPolicy.Builder()
                    .detectDiskReads()
                    .detectDiskWrites()
                    .detectNetwork()
                    .detectCustomSlowCalls()
                    .penaltyLog()
                    // For CI: .penaltyDeath() to hard-fail on first violation
                    .build()
            )
            StrictMode.setVmPolicy(
                StrictMode.VmPolicy.Builder()
                    .detectLeakedSqlLiteObjects()
                    .detectLeakedClosableObjects()
                    .detectActivityLeaks()
                    .penaltyLog()
                    .build()
            )
        }
    }
}

// Mark known-slow functions to surface in StrictMode logs:
fun parseConfig(raw: String): Config {
    StrictMode.noteSlowCall("parseConfig")
    return gson.fromJson(raw, Config::class.java)
}
```

### 6.2 Macrobenchmark — Measure Startup and Frame Timing in CI

```kotlin
// androidTest module
@LargeTest
@RunWith(AndroidJUnit4::class)
class AppStartupBenchmark {
    @get:Rule val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun coldStartup() = benchmarkRule.measureRepeated(
        packageName = "com.example.app",
        metrics     = listOf(StartupTimingMetric(), FrameTimingMetric()),
        iterations  = 5,
        startupMode = StartupMode.COLD
    ) {
        pressHome()
        startActivityAndWait()
    }
}
```

### 6.3 Perfetto — Main Thread Hotspot Analysis

```sql
-- Main thread slices taking >16ms (one frame budget)
SELECT
    s.name,
    s.dur / 1e6 AS dur_ms,
    s.ts / 1e6  AS start_ms
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE t.name = 'main'
  AND s.dur > 16000000  -- 16ms in nanoseconds
ORDER BY s.dur DESC
LIMIT 50;

-- Binder transactions on main thread
SELECT s.name, s.dur / 1e6 AS dur_ms
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
WHERE t.name = 'main'
  AND s.name LIKE 'binder%'
ORDER BY s.dur DESC;
```

### 6.4 `FrameMetricsApi` — Production Frame Monitoring

```kotlin
class PerformanceActivity : AppCompatActivity() {
    private val frameListener = Window.OnFrameMetricsAvailableListener { _, frameMetrics, _ ->
        val totalDuration = frameMetrics.getMetric(FrameMetrics.TOTAL_DURATION) / 1_000_000.0
        if (totalDuration > 700.0) {
            analyticsTracker.logFrozenFrame(totalDuration)
        } else if (totalDuration > 16.0) {
            analyticsTracker.logJankFrame(totalDuration)
        }
    }

    override fun onStart()  { super.onStart(); window.addOnFrameMetricsAvailableListener(frameListener, Handler(Looper.getMainLooper())) }
    override fun onStop()   { super.onStop();  window.removeOnFrameMetricsAvailableListener(frameListener) }
}
```

### 6.5 Compose Compiler Metrics — Detect Unstable Parameters

```kotlin
// build.gradle.kts (app module)
android {
    kotlinOptions {
        freeCompilerArgs += listOf(
            "-P", "plugin:androidx.compose.compiler.plugins.kotlin:metricsDestination=${project.buildDir}/compose-metrics",
            "-P", "plugin:androidx.compose.compiler.plugins.kotlin:reportsDestination=${project.buildDir}/compose-reports"
        )
    }
}
// After build: check build/compose-reports/<module>-composables.txt
// Look for: "restartable skippable" (good) vs "restartable" without "skippable" (unstable parameters)
```

### 6.6 `ApplicationExitInfo` — Post-Mortem ANR Analysis (Android 11+)

Available from API 30 (Android 11). This is the first step in any production ANR triage
pipeline: query it at next launch to detect whether the previous session ended in an ANR.

```kotlin
// Query at app startup, e.g. in Application.onCreate() or a startup ViewModel
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
    val am = getSystemService(ActivityManager::class.java)
    am.getHistoricalProcessExitReasons(null, 0, 10).forEach { info ->
        if (info.reason == ApplicationExitInfo.REASON_ANR) {
            // info.traceInputStream contains the ANR trace (equivalent to /data/anr/anr_* content)
            info.traceInputStream?.use { stream ->
                // Parse and upload tombstone trace to your observability backend
                crashReporter.uploadAnrTrace(
                    stream.readBytes(),
                    extras = mapOf(
                        "timestamp"   to info.timestamp,
                        "description" to info.description,
                        "importance"  to info.importance  // foreground vs background at time of ANR
                    )
                )
            }
        }
    }
}
```

**ANR trace file locations** (for local debugging via `adb`):
```bash
# Pull all ANR traces from device (requires root or userdebug build)
adb pull /data/anr/ ./anr_traces/

# On older devices, single aggregated file:
#   /data/anr/traces.txt
# On newer devices (Android 11+), per-event files:
#   /data/anr/anr_YYYY-MM-DD-HH-MM-SS-mmm_<pid>

# Full bugreport (captures traces, EventLog, MainLog, CPU info — preferred for production):
adb bugreport bugreport.zip
```
```

---

## PART 7 — CODE REVIEW CHECKLIST

### ANR Design & Architecture
- [ ] All ANR types understood: Component-class (AMS), Input-class (InputDispatcher), No-Focused-Window
- [ ] Foreground service calls `startForeground()` within **3 s** (API 35+) / 5 s (API 26–34) of `onStartCommand`
- [ ] `ApplicationExitInfo` queried at startup to capture ANR traces (Android 11+ / API 30+)
- [ ] Production crash reporter uploads ANR trace bytes with timestamp, description, and importance fields
- [ ] ANR monitoring dashboard tags "OEM-freeze false positives" via `unfreeze … reason: Signal` log pattern

### View-Based System
- [ ] No network, file, DB, or ContentResolver calls in `Dispatchers.Main` or `Dispatchers.Default` context
- [ ] All JSON/Protobuf parsing on `Dispatchers.IO` or `Dispatchers.Default` — never after `observeOn(mainThread())`
- [ ] No `runBlocking` in Activity, Fragment, ViewModel, or Service code
- [ ] No `GlobalScope.launch` in production code — use injected application-scoped CoroutineScope
- [ ] `Dispatchers.IO` used for all I/O; `Dispatchers.Default` for CPU; `Dispatchers.Main` for UI only
- [ ] `lazy` on Main-only UI properties uses `LazyThreadSafetyMode.NONE`
- [ ] No `synchronized {}` block contains a `suspend` call — use `Mutex.withLock` instead
- [ ] `ReentrantLock` always uses `withLock {}` or `try/finally`; never holds lock across suspend
- [ ] Nested lock acquisitions follow a consistent, documented ordering; no cross-thread lock inversion
- [ ] Crash/logging/analytics utilities do not hold their own locks while calling into other locked utilities
- [ ] `StrictMode` enabled in debug builds; zero disk/network violations on the main thread
- [ ] `onBindViewHolder` contains only view-assignment — no filtering, mapping, or I/O
- [ ] DiffUtil calculated off-Main (or ListAdapter used)
- [ ] `onDraw` contains no object allocations
- [ ] `BroadcastReceiver.onReceive` uses `goAsync()` **only for work under 10 s**, or delegates to WorkManager
- [ ] `goAsync()` `PendingResult.finish()` is always called — including on the error path — before timeout
- [ ] `JobService.onStartJob` returns immediately and does work in a coroutine
- [ ] Services call `stopSelf()` promptly after work; foreground services call `startForeground` within allowed window
- [ ] SharedPreferences reads on `Dispatchers.IO`; writes use `apply()`, never `commit()`; consider DataStore migration
- [ ] Cancellation check (`ensureActive()` or `yield()`) in tight CPU loops
- [ ] Binder calls to system services (`PackageManager`, `AccountManager`, `ContentResolver`) are off Main
- [ ] Heavy startup work is deferred past the first frame (`window.decorView.post { }`)
- [ ] Bitmap decoding is scaled to display size before being handed to the RenderThread

### Jetpack Compose System
- [ ] No expensive computation directly in composable body — use `remember(key)` or ViewModel
- [ ] No backwards state write (writing state after reading it in same composition)
- [ ] High-frequency state reads (scroll offset, animation value) deferred via lambda-based Modifiers or `derivedStateOf`
- [ ] `derivedStateOf` used for state derived from rapidly-changing source to avoid over-recomposition
- [ ] All parameters to composables are stable (`@Immutable`, `@Stable`, primitives, or Immutable Collections)
- [ ] `LazyColumn`/`LazyRow` items have stable `key = { item.id }`
- [ ] No `runBlocking` or blocking calls inside composable body — use `LaunchedEffect`
- [ ] Side effects (Toast, analytics, network) are inside `LaunchedEffect`, not composable body
- [ ] `Modifier.offset { }` (lambda) used instead of `Modifier.offset(value)` for scroll-driven offsets
- [ ] Compose compiler metrics checked in CI — all composables are "restartable skippable" where expected
- [ ] FrameMetrics or Android Vitals monitored for frozen frame rate ≤ threshold

### ANR Analysis Readiness
- [ ] Debug builds capture and log `ApplicationExitInfo` ANR traces on next launch
- [ ] Production observability backend receives ANR trace bytes (not just stack strings)
- [ ] Team knows how to read thread state (`Blocked` vs `Native` vs `TimedWaiting`) in traces
- [ ] Team knows how to interpret CPU load lines and page fault counts in "ANR in" log entries
- [ ] Perfetto trace captured for any ANR not explained by thread stack alone
