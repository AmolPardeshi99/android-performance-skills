---
name: android-performance-memory-leak-prevention
description: >
  Exhaustive Android memory leak prevention skill for writing leak-free code across View-based
  and Jetpack Compose UI systems. Use this skill whenever writing, reviewing, or auditing Android
  code that involves: Fragment or Activity lifecycle and ViewBinding (onDestroyView, _binding null),
  Context usage in singletons or long-lived objects (applicationContext vs Activity context),
  static fields or companion objects holding Views or Activities, listeners, observers, or
  BroadcastReceivers without symmetric unregistration, LiveData or Flow collection in Fragments
  (viewLifecycleOwner, repeatOnLifecycle), ViewModel holding UI references or callbacks,
  coroutine scopes (GlobalScope, CoroutineScope, viewModelScope, lifecycleScope), resource
  management (Cursor, InputStream, MediaPlayer, Bitmap, SQLite), custom Views (onDetachedFromWindow,
  animators, bitmaps), Handler and Runnable with postDelayed, WebView lifecycle, Hilt or DI scope
  alignment, or any Jetpack Compose memory concerns (remember, DisposableEffect, LaunchedEffect,
  rememberCoroutineScope, RememberObserver, LocalContext, composable lambdas in ViewModels).
  Also trigger for detection and tooling questions: LeakCanary setup, Android Studio Memory
  Profiler, heapprofd, Perfetto heap graphs, ApplicationExitInfo OOM detection. Trigger even for
  casual phrasings like "why is my app crashing with OOM", "is this a memory leak", "should I
  use applicationContext here", "how do I clean up in onDestroyView", or "my Activity is leaking".
  Covers Android API levels 21 through 35+.
---

# SKILL: Memory-Leak-Free Android Codebase (Exhaustive)

## Purpose and Scope

Use this skill when **writing, reviewing, or auditing** Android code for memory leaks across
both the **View-based** and **Jetpack Compose** UI systems. Every section states the root cause,
shows the broken pattern, and provides the correct fix with Kotlin code.

**What a memory leak is**: an object that is no longer needed by the app but cannot be freed by
the garbage collector because something else still holds a strong reference to it. The ART GC
traces live references from GC roots (static fields, thread stacks, JNI globals) to heap objects;
anything reachable survives, anything not reachable is collected. Leaks happen when a GC root —
a singleton, a static field, a running thread — keeps a reference chain alive to an object
(usually Activity / Fragment / View) that should have been collected.

**Why it matters on Android**:
- The heap is constrained per process. A leaked Activity carries its entire View tree (often MBs).
- Leaks accumulate across screen navigations → GC runs more frequently → jank.
- Enough leaks → `OutOfMemoryError` crashes or ANRs from GC pauses.
- Leaked processes consume device RAM, causing LMK (Low Memory Killer) to terminate other apps.

---

## PART 0 — ANDROID MEMORY MODEL AND GC ROOTS

Understanding how ART's garbage collector traces the object graph is the foundation for
recognising and preventing every type of leak covered in this skill.

### 0.1 How ART Garbage Collection Works

ART uses a **tracing GC**: starting from a fixed set of **GC roots**, it walks every reachable
reference chain. Any object reachable from a root survives; anything not reachable is collected.
A leak is simply an object that is still reachable from a root even though the app no longer
needs it.

**GC roots on Android**:
| Root type | Examples |
|---|---|
| Static fields | `companion object` fields, `object` singletons, Java `static` variables |
| Thread stacks | Local variables and parameters on any running thread's call stack |
| JNI globals | References held by native code via `NewGlobalRef` |
| Running threads | The `Thread` object itself, plus everything it references |
| System class loader | Class objects and their static fields |

**The classic Android leak chain**:
```
Static field (GC root)
  └─ Singleton / long-lived object
       └─ Listener / callback / lambda
            └─ Activity / Fragment (captures `this` implicitly)
                 └─ ViewBinding / View tree  (tens of MBs)
```

### 0.2 Java / Kotlin Reference Strength

| Reference type | GC behaviour | Android use case |
|---|---|---|
| **Strong** (default) | Object survives as long as the reference exists | Everything unless you explicitly weaken it |
| **SoftReference** | Collected only when JVM is low on memory | Image caches — JVM decides when to evict |
| **WeakReference** | Collected at next GC cycle when no strong refs remain | Safe back-reference from long-lived object to Activity |
| **PhantomReference** | Collected after finalization; never returns object | Low-level cleanup hooks; rarely used in app code |

```kotlin
// WeakReference pattern — safe back-reference without preventing GC
class LocationManager {
    private var weakCallback: WeakReference<LocationCallback>? = null

    fun register(cb: LocationCallback) { weakCallback = WeakReference(cb) }

    fun onLocationUpdate(loc: Location) {
        weakCallback?.get()?.onLocation(loc)  // null-safe; GC'd callback is simply skipped
            ?: cleanup()                       // callback was GC'd → clean up subscription
    }
}
```

### 0.3 Why Activity / Fragment Leaks Are Especially Costly

A single leaked `Activity` retains:
- Its entire **View tree** (every `TextView`, `RecyclerView`, `ImageView`, etc.)
- Every **Bitmap** loaded into those views
- The **Context** — which itself references the `WindowManager`, `LayoutInflater`, theme resources
- Any **ViewBinding** object referencing all of the above

On a typical screen this is **5–50 MB per leaked instance**. With Navigation Component
back-stack depth of 5, one systematic leak pattern produces 25–250 MB of unreclaimable heap,
guaranteed OOM or LMK kill on mid-range devices.

---

## PART 1 — VIEW-BASED SYSTEM

---

### 1.1 Fragment ViewBinding Not Nulled in `onDestroyView`

**Root cause**: A Fragment lives on the back stack across navigation but its View is destroyed on
every pop/replace. A `ViewBinding` object holds a reference to the entire inflated View tree. If
the `_binding` field is not explicitly nulled in `onDestroyView`, the Fragment instance (which is
still alive on the back stack) keeps the destroyed View tree in memory.

```kotlin
// ❌ LEAK: binding outlives the view
class HomeFragment : Fragment(R.layout.fragment_home) {
    private lateinit var binding: FragmentHomeBinding

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        binding = FragmentHomeBinding.inflate(inflater, container, false)
        return binding.root
    }
    // Missing onDestroyView → entire View tree stays in memory while Fragment is back-stacked
}

// ✅ CORRECT
class HomeFragment : Fragment(R.layout.fragment_home) {
    private var _binding: FragmentHomeBinding? = null
    // Only access this property between onCreateView and onDestroyView
    private val binding get() = _binding!!

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentHomeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.myButton.setOnClickListener { /* ... */ }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null  // REQUIRED: breaks the reference → View tree can be GC'd
    }
}
```

---

### 1.2 Context Misuse — Activity Context in Long-Lived Objects

**Root cause**: `Activity` is a `Context`. Any long-lived object storing an Activity reference
prevents that Activity from being GC'd. The worst offenders are singletons and static fields,
which are GC roots and survive the process lifetime.

```kotlin
// ❌ LEAK: singleton stores Activity context
object ImageLoader {
    private var context: Context? = null
    fun init(activity: Activity) { context = activity }  // Activity is never GC'd
}

// ❌ LEAK: custom View stores Activity as a field
class BadView(context: Context) : View(context) {
    private val hostActivity = context as Activity  // strong ref; outlives View
}

// ✅ CORRECT: use applicationContext in singletons
object ImageLoader {
    private lateinit var appContext: Context
    fun init(ctx: Context) { appContext = ctx.applicationContext }  // lives as long as app
}

// ✅ CORRECT: WeakReference when Activity access is genuinely needed in long-lived objects
class SmartView(context: Context) : View(context) {
    private val weakActivity = WeakReference(context as? Activity)

    fun doActivityWork() {
        weakActivity.get()?.let { activity ->
            if (!activity.isFinishing && !activity.isDestroyed) {
                // safe to use
            }
        }
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        // release all resources
    }
}
```

**Context selection quick reference**:
| Object lifetime | Correct context |
|---|---|
| Singletons, Room, OkHttpClient, WorkManager | `applicationContext` |
| View inflation, dialogs, `startActivity` | `Activity` context — only within lifecycle |
| System services tied to UI (LayoutInflater) | `Activity` context |
| System services hardware-related (LocationManager, AlarmManager, CameraManager) | `applicationContext` |
| RecyclerView Adapters | `view.context` — never store the Activity reference |
| Composables | `LocalContext.current` — never hoist into ViewModel or singleton |

---

### 1.3 Static Fields and Companion Objects Holding Views or Activities

**Root cause**: Static fields are GC roots. Any object stored in a static field lives for the
process lifetime. A `View` holds a reference to its `Context` (usually an Activity) — a static
View leaks the entire Activity plus the View tree.

```kotlin
// ❌ LEAK
class SplashActivity : AppCompatActivity() {
    companion object {
        var instance: SplashActivity? = null   // GC root → Activity never GC'd
        var logoView: ImageView? = null        // View → Context → Activity
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        instance = this
        logoView = binding.logo
    }
}

// ✅ CORRECT: share state via ViewModel or application-scoped event bus; no static UI references
class SplashViewModel : ViewModel() {
    val splashComplete = MutableStateFlow(false)
}

// ✅ If a static reference is truly unavoidable: WeakReference + null in onDestroy
class SplashActivity : AppCompatActivity() {
    companion object {
        private var weakRef: WeakReference<SplashActivity>? = null
        fun instance(): SplashActivity? = weakRef?.get()
    }
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); weakRef = WeakReference(this) }
    override fun onDestroy() { super.onDestroy(); weakRef = null }
}
```

---

### 1.4 Non-Static Inner Classes and Anonymous Classes / Lambdas

**Root cause**: In Kotlin and Java, a non-static inner class or an anonymous class defined inside
an Activity or Fragment captures an implicit `this` reference to the outer class. If the inner
class is passed to a long-lived object, the outer class is retained.

```kotlin
// ❌ LEAK: anonymous object captures 'this' (Activity) → EventBus (singleton) holds it forever
class OrderActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        EventBus.subscribe(object : EventListener {
            override fun onOrderUpdate(event: OrderEvent) {
                updateUI(event)  // captures OrderActivity implicitly
            }
        })
        // No matching unsubscribe → Activity leaks for app lifetime
    }
}

// ✅ CORRECT: store listener reference; unsubscribe in lifecycle teardown
class OrderActivity : AppCompatActivity() {
    private val orderListener = EventListener { event -> updateUI(event) }

    override fun onStart()  { super.onStart(); EventBus.subscribe(orderListener) }
    override fun onStop()   { super.onStop(); EventBus.unsubscribe(orderListener) }
}

// ✅ CORRECT (Java static inner class pattern to avoid implicit reference)
class MyActivity extends AppCompatActivity {
    // Non-static: captures outer class → potential leak
    // class BadRunnable implements Runnable { void run() { doUiWork(); } }

    // Static: no implicit outer reference
    static class SafeRunnable implements Runnable {
        private final WeakReference<MyActivity> ref;
        SafeRunnable(MyActivity a) { ref = new WeakReference<>(a); }
        @Override public void run() {
            MyActivity a = ref.get();
            if (a != null && !a.isFinishing()) a.doUiWork();
        }
    }
}
```

---

### 1.5 Handler and Runnable — Delayed Message Leaks

**Root cause**: `Handler.postDelayed()` enqueues a `Runnable` on the main Looper's `MessageQueue`.
The chain `MessageQueue → Handler → Runnable → Activity` keeps the Activity alive until the
message is processed. If the Activity is destroyed before that happens, the Activity leaks.

```kotlin
// ❌ LEAK: delayed Runnable captures Activity, never removed on destroy
class OnboardingActivity : AppCompatActivity() {
    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handler.postDelayed({
            advanceToNextStep()  // lambda captures 'this' OnboardingActivity
        }, 8_000L)
        // If user presses Back before 8s, Activity leaks for 8s (plus what it holds)
    }
}

// ✅ CORRECT option A: explicit cancel in onDestroy
class OnboardingActivity : AppCompatActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private val advanceRunnable = Runnable { advanceToNextStep() }

    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); handler.postDelayed(advanceRunnable, 8_000L) }
    override fun onDestroy() { super.onDestroy(); handler.removeCallbacks(advanceRunnable) }
}

// ✅ CORRECT option B (preferred): lifecycle-aware coroutine — auto-cancelled on destroy
class OnboardingActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lifecycleScope.launch {
            delay(8_000)
            advanceToNextStep()
        }
    }
}
```

---

### 1.6 Listeners, Observers, BroadcastReceivers Not Unregistered

**Root cause**: Any system service, library, or custom manager that stores a listener keeps a
reference to the registering object. Without symmetric unregistration, the hosting component leaks.

```kotlin
// ❌ LEAK: sensor listener never removed
class CompassFragment : Fragment() {
    private val sensorManager by lazy { requireContext().getSystemService(SensorManager::class.java)!! }
    private val sensor by lazy { sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD) }
    private val listener = object : SensorEventListener {
        override fun onSensorChanged(e: SensorEvent) { updateCompass(e.values) }
        override fun onAccuracyChanged(s: Sensor, a: Int) {}
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        sensorManager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_UI)
        // No matching unregister → SensorManager holds CompassFragment reference
    }
}

// ✅ CORRECT: symmetric pairing
class CompassFragment : Fragment() {
    override fun onResume() { super.onResume(); sensorManager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_UI) }
    override fun onPause()  { super.onPause();  sensorManager.unregisterListener(listener) }
}

// ❌ LEAK: BroadcastReceiver registered without unregister
//          Also: CONNECTIVITY_ACTION is deprecated since API 28 — use NetworkCallback instead
class NetworkFragment : Fragment() {
    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) { checkNetwork() }
    }
    override fun onStart() {
        super.onStart()
        @Suppress("DEPRECATION")
        requireContext().registerReceiver(receiver, IntentFilter(ConnectivityManager.CONNECTIVITY_ACTION))
        // No unregister → receiver holds Fragment reference
    }
}
// ✅ CORRECT unregister pairing (if BroadcastReceiver is still needed):
override fun onStop() { super.onStop(); requireContext().unregisterReceiver(receiver) }

// ✅ PREFERRED (API 28+): NetworkCallback — no BroadcastReceiver, no unregister leak risk
class NetworkFragment : Fragment() {
    private val connectivityManager by lazy {
        requireContext().getSystemService(ConnectivityManager::class.java)
    }
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network)  { checkNetwork(available = true)  }
        override fun onLost(network: Network)       { checkNetwork(available = false) }
    }

    override fun onStart() {
        super.onStart()
        connectivityManager.registerDefaultNetworkCallback(networkCallback)
    }
    override fun onStop() {
        super.onStop()
        connectivityManager.unregisterNetworkCallback(networkCallback)
    }
}
```

**Lifecycle pairing table**:
| Register in | Unregister in |
|---|---|
| `onCreate` | `onDestroy` |
| `onStart` | `onStop` |
| `onResume` | `onPause` |
| `onCreateView` / `onViewCreated` | `onDestroyView` |

### LiveData / Flow — Wrong Lifecycle Owner in Fragments

```kotlin
// ❌ LEAK: using Fragment 'this' as observer — observer never removed when View is destroyed
// After navigating away and back, a second observer is added → duplicate callbacks
viewModel.data.observe(this) { render(it) }

// ✅ CORRECT: viewLifecycleOwner is destroyed with the View
viewModel.data.observe(viewLifecycleOwner) { render(it) }

// ✅ CORRECT for Flow — repeatOnLifecycle suspends collection in background, resumes in foreground
viewLifecycleOwner.lifecycleScope.launch {
    viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect { render(it) }
    }
}
// ❌ BAD: bare launch collects even when app is backgrounded — wastes CPU and may leak
// lifecycleScope.launch { viewModel.uiState.collect { render(it) } }
```

---

### 1.7 ViewModel Holding UI References

ViewModel survives configuration changes. Anything stored in it lives at least until the owner
Activity / NavGraph is permanently finished.

```kotlin
// ❌ LEAK: Activity, View, or Binding stored in ViewModel
class DashboardViewModel : ViewModel() {
    var activity: Activity? = null         // leaks across rotation
    var chart: ChartView? = null           // leaks View tree
    lateinit var binding: ActivityDashboardBinding  // leaks Context
}

// ❌ LEAK: lambda from Activity stored in Repository singleton → ViewModel retained
// The lambda captures ViewModel implicitly, Repository (singleton) holds the lambda,
// so ViewModel lives forever
class OrderRepository {
    private var onComplete: (() -> Unit)? = null
    fun setCallback(cb: () -> Unit) { onComplete = cb }
    // Caller must call clearCallback() or ViewModel leaks
}

class OrderViewModel(private val repo: OrderRepository) : ViewModel() {
    init { repo.setCallback { _uiState.value = UiState.Done } }
    override fun onCleared() { super.onCleared(); repo.clearCallback() }  // REQUIRED
}

// ✅ CORRECT: ViewModels contain only application-scoped objects
class DashboardViewModel(
    private val dashboardRepo: DashboardRepository,  // no Android framework types
    @ApplicationContext private val context: Context  // applicationContext is fine
) : ViewModel() {
    val stats: StateFlow<Stats> = dashboardRepo.stats
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), Stats.Empty)
}
```

---

### 1.8 Coroutine Scope and GlobalScope Leaks

**Root cause**: A coroutine captures every variable it references from its outer scope, including
`binding` (View), `this` (Activity / Fragment). If the coroutine runs on a scope that outlives
the screen, all those references are retained.

```kotlin
// ❌ LEAK: GlobalScope — no lifecycle, captures binding, runs until app death
class OrderFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        GlobalScope.launch {
            val order = api.fetchOrder()
            withContext(Dispatchers.Main) {
                binding.total.text = order.total  // binding captured; Fragment is gone
            }
        }
    }
}

// ❌ LEAK: manual CoroutineScope not cancelled on destroy
class OrderFragment : Fragment() {
    private val scope = CoroutineScope(Dispatchers.Main)
    // Missing: override fun onDestroyView() { scope.cancel() }
}

// ✅ CORRECT: lifecycle-bound scopes
class OrderFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        // viewLifecycleOwner.lifecycleScope is cancelled in onDestroyView automatically
        viewLifecycleOwner.lifecycleScope.launch {
            val order = withContext(Dispatchers.IO) { api.fetchOrder() }
            binding.total.text = order.total
        }
    }
}

// ✅ In ViewModel: viewModelScope cancelled in onCleared()
class OrderViewModel(private val api: OrderApi) : ViewModel() {
    fun loadOrder(id: String) {
        viewModelScope.launch {
            val order = withContext(Dispatchers.IO) { api.fetchOrder(id) }
            _uiState.value = UiState.Success(order)
        }
    }
}

// ✅ Application-level background work: inject a custom application-scoped CoroutineScope
// (not GlobalScope) via DI
@Singleton
class AppCoroutineScope @Inject constructor() : CoroutineScope by CoroutineScope(
    SupervisorJob() + Dispatchers.Default
)
```

---

### 1.9 Resource Leaks — Streams, Cursors, Databases, MediaPlayer

```kotlin
// ❌ LEAK: BufferedReader never closed on exception path
fun readConfig(file: File): Config {
    val reader = BufferedReader(FileReader(file))
    return Json.decodeFromReader(reader)
    // If decodeFromReader throws, reader is never closed → file handle + memory leak
}

// ✅ CORRECT: Kotlin use {} closes on success AND exception (try-with-resources)
fun readConfig(file: File): Config =
    BufferedReader(FileReader(file)).use { Json.decodeFromReader(it) }

// ✅ Cursor via use {}
fun getNames(db: SQLiteDatabase): List<String> =
    db.rawQuery("SELECT name FROM users", null).use { cursor ->
        buildList { while (cursor.moveToNext()) add(cursor.getString(0)) }
    }

// ✅ MediaPlayer in a Fragment
class AudioFragment : Fragment() {
    private var player: MediaPlayer? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        player = MediaPlayer.create(requireContext(), R.raw.bgm).also { it.start() }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        player?.stop()
        player?.release()
        player = null
    }
}
```

---

### 1.10 Custom View — Animators, Bitmaps, Listeners

Custom Views must release every resource they acquire when detached from the window.

```kotlin
class AnimatedRingView(context: Context) : View(context) {
    private var pulseAnimator: ObjectAnimator? = null
    private var iconBitmap: Bitmap? = null
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) { invalidate() }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        pulseAnimator = ObjectAnimator.ofFloat(this, "alpha", 0f, 1f).apply {
            repeatCount = ObjectAnimator.INFINITE; start()
        }
        val cm = context.getSystemService(ConnectivityManager::class.java)
        cm.registerDefaultNetworkCallback(networkCallback)
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        pulseAnimator?.cancel()
        pulseAnimator = null
        iconBitmap?.recycle()
        iconBitmap = null
        val cm = context.getSystemService(ConnectivityManager::class.java)
        cm.unregisterNetworkCallback(networkCallback)
    }
}
```

---

### 1.11 Bitmap and Large Object Memory Management

```kotlin
// ❌ LEAK: unbounded static cache of Bitmaps
companion object {
    val bitmapCache = HashMap<String, Bitmap>()  // grows forever; bitmaps are large
}

// ✅ CORRECT: LruCache with size-aware eviction
val bitmapCache = object : LruCache<String, Bitmap>(
    (Runtime.getRuntime().maxMemory() / 1024L / 8L).toInt()  // 1/8 of max heap in KB
) {
    override fun sizeOf(key: String, value: Bitmap) = value.byteCount / 1024
}

// ✅ Always prefer Glide / Coil for image loading — they manage pooling, lifecycle binding, and OOM
Glide.with(viewLifecycleOwner).load(url).into(imageView)
// Coil:
imageView.load(url) { lifecycle(viewLifecycleOwner) }
```

---

### 1.12 Services Running Unnecessarily

Per Android official memory guidance: *"leaving unnecessary services running is one of the worst
memory-management mistakes an Android app can make."* The process for a running service is
expensive and is kept alive preferentially by the OS.

```kotlin
// ❌ WRONG: service that never stops itself; stays alive indefinitely
class SyncService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        doSync()
        return START_STICKY  // restarts forever — keeps process alive; RAM never freed
    }
}

// ✅ CORRECT: stop self after work is done
class SyncService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        CoroutineScope(Dispatchers.IO + Job()).launch {
            doSync()
            stopSelf(startId)  // releases service memory
        }
        return START_NOT_STICKY
    }
}

// ✅ BETTER: use WorkManager for background, deferrable, or constraint-based work
val request = OneTimeWorkRequestBuilder<SyncWorker>()
    .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
    .build()
WorkManager.getInstance(context).enqueue(request)
```

---

### 1.13 WebView Process Isolation

WebView has well-documented native memory leaks that affect the host process.

```xml
<!-- Isolate WebView in a separate process to prevent its leaks from affecting your app -->
<activity
    android:name=".WebViewActivity"
    android:process=":webview" />
```

```kotlin
override fun onDestroy() {
    (binding.webView.parent as? ViewGroup)?.removeView(binding.webView)
    binding.webView.apply {
        stopLoading()
        clearHistory()
        removeAllViews()
        destroy()
    }
    super.onDestroy()
}
```

---

### 1.14 `TypedArray` Not Recycled in Custom View `init {}`

**Root cause**: `context.obtainStyledAttributes()` allocates a `TypedArray` backed by a native
pointer into the resource framework. If `recycle()` is not called, the native memory is never
returned to the pool. This is a native/heap leak that LeakCanary won't always surface.

```kotlin
// ❌ LEAK: TypedArray never recycled — native memory held forever
class RatingBarView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {
    init {
        val ta = context.obtainStyledAttributes(attrs, R.styleable.RatingBarView)
        val starColor = ta.getColor(R.styleable.RatingBarView_starColor, Color.YELLOW)
        val starCount = ta.getInt(R.styleable.RatingBarView_starCount, 5)
        // ta.recycle() missing → native resource pool exhausted over time
    }
}

// ✅ CORRECT option A: manual recycle in finally block
class RatingBarView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {
    init {
        val ta = context.obtainStyledAttributes(attrs, R.styleable.RatingBarView)
        try {
            val starColor = ta.getColor(R.styleable.RatingBarView_starColor, Color.YELLOW)
            val starCount = ta.getInt(R.styleable.RatingBarView_starCount, 5)
        } finally {
            ta.recycle()  // REQUIRED: always in finally so it runs even on exception
        }
    }
}

// ✅ CORRECT option B: Kotlin use {} extension (clean, exception-safe)
class RatingBarView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {
    init {
        context.obtainStyledAttributes(attrs, R.styleable.RatingBarView).use { ta ->
            val starColor = ta.getColor(R.styleable.RatingBarView_starColor, Color.YELLOW)
            val starCount = ta.getInt(R.styleable.RatingBarView_starCount, 5)
        }  // recycle() called automatically
    }
}
```

---

### 1.15 `registerForActivityResult` — Lambda Capture Outside `onCreate`

**Root cause**: `ActivityResultLauncher` must be registered during `onCreate` (or `init` of a
Fragment). Registering it in `onViewCreated`, `onStart`, or inside a click listener creates a
new registration on every call, stacking multiple launchers and leaking the previous callbacks.
Each callback lambda implicitly captures `this` (the Fragment or Activity).

```kotlin
// ❌ LEAK: registered in onViewCreated — new launcher + captured reference every time
//          the Fragment's view is re-created (e.g. back-stack navigation)
class ProfileFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val launcher = registerForActivityResult(
            ActivityResultContracts.PickVisualMedia()
        ) { uri -> updateAvatar(uri) }  // new lambda captures Fragment on every view creation
        binding.avatarButton.setOnClickListener { launcher.launch(PickVisualMediaRequest()) }
    }
}

// ✅ CORRECT: register at Fragment construction time — single registration, single reference
class ProfileFragment : Fragment() {
    private val avatarLauncher = registerForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> updateAvatar(uri) }  // registered once; Fragment reference is lifecycle-scoped

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        binding.avatarButton.setOnClickListener {
            avatarLauncher.launch(PickVisualMediaRequest())
        }
    }
}
```

---

### 1.16 `NavController` Destination Changed Listener Not Removed

**Root cause**: `NavController.addOnDestinationChangedListener` registers a listener on the
controller, which outlives individual Fragment views. If added in `onViewCreated` without
removal in `onDestroyView`, a new listener is stacked on every navigation cycle, each one
capturing the Fragment instance.

```kotlin
// ❌ LEAK: new listener added every time view is recreated — stacks up on the NavController
class MainFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        findNavController().addOnDestinationChangedListener { _, destination, _ ->
            updateToolbar(destination)  // captures MainFragment implicitly
        }
        // No removal → NavController holds growing list of captured Fragment references
    }
}

// ✅ CORRECT: remove listener in onDestroyView
class MainFragment : Fragment() {
    private val destinationListener =
        NavController.OnDestinationChangedListener { _, destination, _ ->
            updateToolbar(destination)
        }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        findNavController().addOnDestinationChangedListener(destinationListener)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        findNavController().removeOnDestinationChangedListener(destinationListener)
    }
}

// ✅ ALTERNATIVE: use a lifecycle-aware approach via viewLifecycleOwner
// navController.currentBackStackEntryAsFlow() collects only while view is alive
```

---

### 1.17 `by lazy` in Fragment Capturing Outer `this`

**Root cause**: A `private val x by lazy { Something(this) }` in a Fragment captures the
Fragment instance inside the lambda. The lazy delegate holds a strong reference to that lambda
until after first access, and if the resulting object is long-lived or stored externally, the
Fragment is never GC'd.

```kotlin
// ❌ SUBTLE LEAK: lazy lambda captures Fragment 'this'; if AnalyticsHelper stores the
//                 reference beyond Fragment lifetime, the Fragment leaks
class OrderFragment : Fragment() {
    private val analytics by lazy { AnalyticsHelper(this) }  // 'this' captured in lambda
    // If AnalyticsHelper passes 'this' to a singleton tracker, Fragment is pinned forever
}

// ✅ CORRECT option A: pass applicationContext, not Fragment reference
class OrderFragment : Fragment() {
    private val analytics by lazy {
        AnalyticsHelper(requireContext().applicationContext)  // no Fragment reference captured
    }
}

// ✅ CORRECT option B: initialise in onViewCreated and clear in onDestroyView
class OrderFragment : Fragment() {
    private var analytics: AnalyticsHelper? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        analytics = AnalyticsHelper(requireContext().applicationContext)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        analytics = null
    }
}
```

---

### 1.18 `Choreographer` Frame Callbacks Not Removed

**Root cause**: `Choreographer.getInstance().postFrameCallback()` schedules a callback for the
next vsync. If the callback re-posts itself for animation or FPS monitoring, and is never
removed on lifecycle teardown, it holds a reference to the enclosing class and runs indefinitely
after the screen is gone.

```kotlin
// ❌ LEAK: self-rescheduling frame callback never cancelled on Fragment destroy
class FpsMonitorFragment : Fragment() {
    private val frameCallback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            recordFrame(frameTimeNanos)
            Choreographer.getInstance().postFrameCallback(this)  // re-posts itself
            // Nothing stops this after Fragment is destroyed → Fragment leaks
        }
    }

    override fun onResume() {
        super.onResume()
        Choreographer.getInstance().postFrameCallback(frameCallback)
    }
    // Missing onPause cleanup
}

// ✅ CORRECT: symmetric remove in onPause
class FpsMonitorFragment : Fragment() {
    private val frameCallback = Choreographer.FrameCallback { frameTimeNanos ->
        recordFrame(frameTimeNanos)
        if (isResumed) Choreographer.getInstance().postFrameCallback(this::doFrame)
    }

    override fun onResume() {
        super.onResume()
        Choreographer.getInstance().postFrameCallback(frameCallback)
    }

    override fun onPause() {
        super.onPause()
        Choreographer.getInstance().removeFrameCallback(frameCallback)  // REQUIRED
    }
}
```

---

### 1.19 `ProcessLifecycleOwner` Observer Never Removed

**Root cause**: `ProcessLifecycleOwner` represents the entire app process — its lifecycle never
reaches `DESTROYED` while the app is running. Observers added to it are never auto-removed.
If you add an observer from an Activity or Fragment instance, that instance is pinned for the
rest of the app's lifetime.

```kotlin
// ❌ LEAK: Activity instance added as observer to ProcessLifecycleOwner —
//          Activity is never GC'd because ProcessLifecycle never reaches DESTROYED
class HomeActivity : AppCompatActivity(), DefaultLifecycleObserver {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ProcessLifecycleOwner.get().lifecycle.addObserver(this)
        // No matching removeObserver → HomeActivity held for app lifetime
    }
    override fun onStart(owner: LifecycleOwner) { showForegroundBanner() }
}

// ✅ CORRECT: use an application-scoped observer; never add Activity/Fragment instances
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ProcessLifecycleOwner.get().lifecycle.addObserver(AppForegroundObserver())
        // AppForegroundObserver holds only applicationContext — process-scoped; safe
    }
}

class AppForegroundObserver : DefaultLifecycleObserver {
    override fun onStart(owner: LifecycleOwner)  { /* app moved to foreground */ }
    override fun onStop(owner: LifecycleOwner)   { /* app moved to background */ }
}

// ✅ If Activity-level reaction is needed: observe from Activity's own lifecycle instead
class HomeActivity : AppCompatActivity() {
    override fun onStart()  { super.onStart();  showForegroundBanner() }
    override fun onStop()   { super.onStop();   hideForegroundBanner() }
}
```

---

## PART 2 — JETPACK COMPOSE SYSTEM

---

### 2.1 `remember` Without a Key — Stale Object Retention

**Root cause**: `remember {}` caches across recompositions. Without a key, the same object
instance is used even when a meaningful input changes. If the object opens resources
(threads, DB connections, subscriptions), those remain tied to stale inputs.

```kotlin
// ❌ LEAK: ExpensiveResource created for first itemId is never released or updated when itemId changes
@Composable
fun ItemDetail(itemId: String) {
    val resource = remember { ExpensiveResource(itemId) }  // never re-created for new itemId
}

// ✅ CORRECT: key remember to inputs that should invalidate the object
@Composable
fun ItemDetail(itemId: String) {
    val resource = remember(itemId) { ExpensiveResource(itemId) }
    DisposableEffect(itemId) {
        onDispose { resource.close() }  // released when itemId changes OR composable leaves
    }
}
```

---

### 2.2 Resources Created in Composition Without `DisposableEffect`

**Root cause**: Composable function bodies run on every recomposition. Resources created without
`DisposableEffect` are opened repeatedly and never closed when the composable leaves the tree.

```kotlin
// ❌ LEAK: Room database created on every recomposition; never closed
@Composable
fun DataScreen() {
    val context = LocalContext.current
    val db = Room.databaseBuilder(context, AppDatabase::class.java, "app.db").build()
    // db.close() never called; new instance opened every recompose
}

// ✅ CORRECT: DisposableEffect lifecycle matches the composable's presence in the Composition
@Composable
fun DataScreen() {
    val context = LocalContext.current.applicationContext
    DisposableEffect(Unit) {
        val db = Room.databaseBuilder(context, AppDatabase::class.java, "app.db").build()
        onDispose { db.close() }  // closed when composable leaves the tree
    }
}
```

---

### 2.3 Activity Context Captured in `remember` — Configuration Change Leak

**Root cause**: `LocalContext.current` in a composable may return an Activity instance. Capturing
that in `remember {}` without a key means the same Activity instance is referenced across
recompositions, including those triggered after a configuration change where a new Activity is
created — the old one is leaked.

```kotlin
// ❌ LEAK: remember captures an Activity context; after rotation old Activity is retained
@Composable
fun MyScreen() {
    val context = LocalContext.current  // may be Activity
    val helper = remember { SomeSdkHelper(context) }  // keeps old Activity after rotation
}

// ✅ CORRECT: use applicationContext for long-lived remembered objects
@Composable
fun MyScreen() {
    val appContext = LocalContext.current.applicationContext
    val helper = remember { SomeSdkHelper(appContext) }  // safe across rotations
}
```

---

### 2.4 Lambdas Capturing Composition-Scoped References in Long-Lived Objects

**Root cause**: Lambdas in composables capture all referenced variables from the enclosing scope.
Passing such a lambda to a singleton or SDK stores a reference to composition-scoped objects
(state, binding context) in a long-lived location.

```kotlin
// ❌ LEAK: lambda captures composition state; LocationSdk (singleton) holds it forever
@Composable
fun TrackingScreen(viewModel: TrackingViewModel) {
    val currentState by viewModel.state.collectAsState()

    LaunchedEffect(Unit) {
        LocationSdk.setCallback { location ->
            viewModel.onLocation(location, currentState)  // currentState captured by closure — stale
        }
        // No cleanup → LocationSdk holds the lambda forever after composable leaves
    }
}

// ✅ CORRECT: rememberUpdatedState for stable latest-value access; DisposableEffect for cleanup
@Composable
fun TrackingScreen(viewModel: TrackingViewModel) {
    val latestState by rememberUpdatedState(viewModel.state.collectAsState().value)

    DisposableEffect(Unit) {
        val callback = LocationCallback { loc -> viewModel.onLocation(loc, latestState) }
        LocationSdk.setCallback(callback)
        onDispose { LocationSdk.clearCallback() }  // cleanup when composable leaves
    }
}
```

---

### 2.5 Composable Lambda / Composition Reference Stored in ViewModel

**Root cause**: A composable lambda captures the entire composition context (slot table,
snapshot scope). Storing it in a ViewModel prevents the composition — and everything it
references — from being GC'd.

```kotlin
// ❌ LEAK: ViewModel holds composable lambda → entire composition tree retained
class ProfileViewModel : ViewModel() {
    var onLoaded: (@Composable () -> Unit)? = null  // NEVER store composable lambdas in VM
}

@Composable
fun ProfileScreen(vm: ProfileViewModel) {
    vm.onLoaded = { Text("Profile loaded") }  // composition scope captured in ViewModel
}

// ✅ CORRECT: expose state via StateFlow; composable observes and reacts
class ProfileViewModel : ViewModel() {
    private val _profile = MutableStateFlow<Profile?>(null)
    val profile: StateFlow<Profile?> = _profile.asStateFlow()
    fun load() { viewModelScope.launch { _profile.value = repo.fetch() } }
}

@Composable
fun ProfileScreen(vm: ProfileViewModel) {
    val profile by vm.profile.collectAsState()
    profile?.let { ProfileContent(it) }
}
```

---

### 2.6 Bare `CoroutineScope()` in a Composable — Orphaned Jobs

**Root cause**: A `CoroutineScope()` created without `remember` is re-created on every
recomposition with no lifecycle binding. The old scope is orphaned and any running jobs continue
until they complete, holding captured references.

```kotlin
// ❌ LEAK: new CoroutineScope created on every recomposition; previous jobs orphaned
@Composable
fun SearchScreen() {
    val scope = CoroutineScope(Dispatchers.IO)  // new scope, new Job, every recompose
    Button(onClick = { scope.launch { search() } }) { Text("Search") }
}

// ✅ CORRECT: rememberCoroutineScope — stable across recompositions, cancelled when composable leaves
@Composable
fun SearchScreen() {
    val scope = rememberCoroutineScope()
    Button(onClick = { scope.launch { search() } }) { Text("Search") }
}

// ✅ For work keyed to composition entry: LaunchedEffect
@Composable
fun AutoSearch(query: String) {
    LaunchedEffect(query) {          // cancels previous, restarts when query changes, cleans up on exit
        delay(300)                   // debounce
        performSearch(query)
    }
}
```

---

### 2.7 Side Effect API Selection — `SideEffect` vs `LaunchedEffect` vs `DisposableEffect`

Choosing the wrong effect API causes orphaned work, missed cleanup, or double registration.

```kotlin
// SideEffect: runs after EVERY successful recomposition; no key, no cleanup.
// Use only to push Compose state into non-Compose systems.
SideEffect { analyticsTracker.setScreen("Home") }

// LaunchedEffect: launches a suspending coroutine; cancels and restarts when key changes;
// cancelled automatically when composable leaves.
// Use for async work triggered by entering composition or state changes.
LaunchedEffect(userId) { viewModel.loadUser(userId) }

// DisposableEffect: for non-suspend side effects that need cleanup.
// onDispose runs when the key changes OR composable leaves. Always provide cleanup.
DisposableEffect(lifecycle) {
    val observer = LifecycleEventObserver { _, event -> viewModel.onLifecycle(event) }
    lifecycle.addObserver(observer)
    onDispose { lifecycle.removeObserver(observer) }  // always required
}

// ❌ WRONG: using LaunchedEffect for a non-suspend listener registration
// (no cleanup possible — the listener leaks when composable leaves)
LaunchedEffect(Unit) {
    SomeSdk.addListener { event -> handle(event) }
    // Never removed
}
// ✅ Use DisposableEffect instead for any registration that needs cleanup
```

---

### 2.8 Object Allocation Churn During Recomposition

**Root cause**: Objects allocated inline in a composable body — lambdas, collections, derived
lists — are re-created on every recomposition. In fast-recomposing screens (scroll, animation),
this produces GC pressure and jank.

```kotlin
// ❌ CHURN: new filtered List and new onClick lambdas created on every recomposition
@Composable
fun FeedScreen(posts: List<Post>, onLike: (Post) -> Unit) {
    val activePosts = posts.filter { it.isActive }  // new List every time
    LazyColumn {
        items(activePosts) { post ->
            PostCard(post, onClick = { onLike(post) })  // new lambda per item per recompose
        }
    }
}

// ✅ CORRECT: cache expensive computations; pass stable lambdas from ViewModel
@Composable
fun FeedScreen(posts: List<Post>, onLike: (Post) -> Unit) {
    val activePosts = remember(posts) { posts.filter { it.isActive } }  // recomputed only when posts changes
    LazyColumn {
        items(activePosts, key = { it.id }) { post ->   // stable key avoids full rebind
            PostCard(post, onClick = { onLike(post) })
        }
    }
}
// Move filtering to ViewModel so composable receives already-filtered list
```

---

### 2.9 `MutableState` / Scope Stored in Application-Scoped Singletons

```kotlin
// ❌ LEAK: Compose snapshot state in a singleton → snapshot system retains composition reference
object GlobalUiState {
    val isLoading = mutableStateOf(false)     // prevents composition GC
    val appScope = CoroutineScope(Dispatchers.Main)  // never cancelled
}

// ✅ CORRECT: ViewModel-scoped state; application-scoped scope via DI
class AppViewModel : ViewModel() {
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()
}

@Singleton
class AppCoroutineScope @Inject constructor() : CoroutineScope by CoroutineScope(
    SupervisorJob() + Dispatchers.Default
)
```

---

### 2.10 `RememberObserver` Work Started in Constructor

Per the official Android Compose documentation, objects implementing `RememberObserver` must
start cancellable work in `onRemembered`, not in `init {}`. Work started in the constructor
runs during the composition phase and may be orphaned if composition is abandoned or deferred.

```kotlin
// ❌ LEAK: coroutine started in init{} before onRemembered; orphaned if composition is abandoned
class DataPoller : RememberObserver {
    private val job = Job()
    private val scope = CoroutineScope(Dispatchers.Main + job)

    init {
        scope.launch { poll() }  // starts during composition — may be orphaned
    }

    override fun onRemembered() {}
    override fun onForgotten() { job.cancel() }
    override fun onAbandoned() { job.cancel() }
}

// ✅ CORRECT
class DataPoller : RememberObserver {
    private val job = Job()
    private val scope = CoroutineScope(Dispatchers.Main + job)

    override fun onRemembered() {
        scope.launch { poll() }  // starts only when composition is applied
    }
    override fun onForgotten() { job.cancel() }
    override fun onAbandoned() { job.cancel() }
}
```

---

### 2.11 `LocalContext` in `remember` Without `applicationContext` — Rotation Leak

```kotlin
// ❌ LEAK: Activity context cached in remember across rotations
@Composable
fun LocationScreen() {
    val context = LocalContext.current
    val fusedClient = remember { LocationServices.getFusedLocationProviderClient(context) }
    // After rotation, old Activity is retained by fusedClient
}

// ✅ CORRECT: applicationContext is rotation-safe
@Composable
fun LocationScreen() {
    val context = LocalContext.current.applicationContext
    val fusedClient = remember { LocationServices.getFusedLocationProviderClient(context) }
}
```

---

### 2.12 Recomposition-Triggered Side Effects — Toast, Log, Analytics in Composable Body

```kotlin
// ❌ WRONG: Toast shown on every recomposition (including trivial state changes)
@Composable
fun WelcomeScreen() {
    Toast.makeText(LocalContext.current, "Welcome!", Toast.LENGTH_SHORT).show()
}

// ✅ CORRECT: wrap in LaunchedEffect(Unit) — runs once on entry;
//             use applicationContext for Toast to avoid capturing the Activity context
@Composable
fun WelcomeScreen() {
    val context = LocalContext.current.applicationContext  // applicationContext — rotation-safe
    LaunchedEffect(Unit) {
        Toast.makeText(context, "Welcome!", Toast.LENGTH_SHORT).show()
    }
}
```

---

### 2.13 `SharedFlow` / `StateFlow` Replay Buffer Holding Large Objects

**Root cause**: `SharedFlow(replay = N)` keeps the last N emitted values in memory regardless
of whether any collector is active. If those values contain large domain objects, Bitmaps, or
Parcelables, they are pinned in the replay cache indefinitely — invisible to LeakCanary because
it is technically a valid strong reference from a live ViewModel, but functionally wasted memory.

```kotlin
// ❌ MEMORY WASTE: replay buffer retains the last emission of a large search result page
class SearchViewModel : ViewModel() {
    private val _results = MutableSharedFlow<SearchResultPage>(replay = 1)
    // SearchResultPage contains a List<Product> with thumbnails — potentially MBs
    // Even after the user navigates away, the last page stays pinned in the replay cache
    val results: SharedFlow<SearchResultPage> = _results
}

// ✅ CORRECT option A: use StateFlow — single cached value, clearly intentional
class SearchViewModel : ViewModel() {
    private val _results = MutableStateFlow<SearchResultPage?>(null)
    val results: StateFlow<SearchResultPage?> = _results.asStateFlow()

    fun clearResults() { _results.value = null }  // explicitly release on navigate away
}

// ✅ CORRECT option B: replay = 0 for event streams where no cache is needed
class SearchViewModel : ViewModel() {
    private val _events = MutableSharedFlow<SearchEvent>(replay = 0, extraBufferCapacity = 1)
    val events: SharedFlow<SearchEvent> = _events
}

// ✅ CORRECT option C: if large payload is needed, emit only IDs and load on demand
class SearchViewModel : ViewModel() {
    private val _resultIds = MutableStateFlow<List<String>>(emptyList())
    val resultIds: StateFlow<List<String>> = _resultIds.asStateFlow()
    // UI fetches full objects from Room cache by ID — no large objects pinned in Flow
}
```

**Replay buffer sizing guide**:
| Use case | Recommended type | Replay |
|---|---|---|
| UI state (single source of truth) | `StateFlow` | 1 (built-in) |
| One-shot events (snackbar, navigation) | `SharedFlow` | 0 |
| Event history needed for late subscribers | `SharedFlow` | N — but only with small payloads |
| Large paginated results | `StateFlow<PagingData>` or `StateFlow<List<Id>>` | 1, clear on exit |

---

### 3.1 LeakCanary (debug builds — mandatory)

```kotlin
// build.gradle.kts (app module)
dependencies {
    debugImplementation("com.squareup.leakcanary:leakcanary-android:2.14")
    // No code init required; installs via ContentProvider automatically
}

// Watch custom objects beyond the built-in Activity/Fragment watchers
AppWatcher.objectWatcher.expectWeaklyReachable(myObject, "Should be GC'd after screen close")

// CI gate: fail test suite on any leak
class AllScreensTest {
    @get:Rule val rule = DetectLeaksAfterTestSuccess()  // LeakCanary assertion in test
    @Test fun traverseAllScreens() { /* Espresso / UI Automator flow */ }
}
```

### 3.2 Android Studio Memory Profiler

1. Run → Profile → Memory tab
2. Navigate between screens multiple times
3. Tap the GC bucket icon (force GC)
4. Capture Heap Dump
5. Filter → "Show Activity/Fragment leaks"
6. Look for objects with large Retained Size that should have been freed
7. Click an instance → "References" pane → trace to GC root to find the leak path

### 3.3 `adb shell dumpsys meminfo` — Quick Field Check

```bash
adb shell dumpsys meminfo com.your.package.name

# Key fields to watch:
# Activities:  N  ← should drop to 1 after pressing Back on a screen
# Views:       N  ← high count after navigation = View leak
# AppContexts: N
# TOTAL: xx MB ← compare before/after repeated navigation to detect growth
```

### 3.4 `adb shell am dumpheap` — CLI Heap Dump for CI / Automation

Use this to capture an HPROF without Android Studio — useful in CI pipelines or on
devices without USB debugging UI.

```bash
# 1. Find the PID of your app
adb shell pidof com.your.package.name

# 2. Dump the heap to device storage
adb shell am dumpheap <PID> /data/local/tmp/heap.hprof

# 3. Pull the HPROF to your machine
adb pull /data/local/tmp/heap.hprof ./heap.hprof

# 4. Convert to Android Studio-compatible format (required before opening in Studio)
hprof-conv heap.hprof heap_converted.hprof

# 5. Open in Android Studio: File → Open → heap_converted.hprof
#    Or analyse with LeakCanary CLI: https://square.github.io/leakcanary/shark/

# For debuggable builds on API 30+, you can also trigger via shell:
adb shell cmd activity dumpheap com.your.package.name /data/local/tmp/heap2.hprof
``` 

### 3.5 Perfetto + heapprofd — Production-Grade Native and Java Heap Profiling

```bash
# Java heap sampling via Perfetto (no recompile; works on user builds with debuggable=true)
# Configure in Perfetto config:
# track_event { name_filter_type: MATCH_ANY name_filter: "com.your.package" }
# java_hprof_config { continuous_dump_config { dump_phase_ms: 0 dump_interval_ms: 10000 } }

# Open resulting trace at https://ui.perfetto.dev → Memory → Java Heap Graph
```

### 3.6 `ApplicationExitInfo` — Post-Mortem OOM Detection in Production

```kotlin
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val am = getSystemService(ActivityManager::class.java)
            am.getHistoricalProcessExitReasons(packageName, 0, 5).forEach { info ->
                if (info.reason == ApplicationExitInfo.REASON_LOW_MEMORY) {
                    // Report to crash analytics; optionally parse HPROF
                    crashReporter.logOomExit(info.description, info.timestamp)
                }
            }
        }
    }
}
```

### 3.7 Hilt / DI Scope Alignment

Mismatched DI scopes cause objects to live longer than necessary.

```kotlin
// ❌ WRONG: @Singleton dependency holds an @ActivityScoped resource
@Singleton
class GlobalCache @Inject constructor(
    private val userPrefs: UserPrefsStore  // if UserPrefsStore is @ActivityScoped, it leaks
)

// ✅ CORRECT: match lifetimes — only inject dependencies with equal or wider scope
@ActivityScoped  // lives only for one Activity
class UserDashboard @Inject constructor(
    @ActivityContext private val context: Context,  // Hilt provides activity context safely
    private val repo: DashboardRepository           // @Singleton — wider scope; fine
)
```

---

## PART 4 — CODE REVIEW CHECKLIST

### View-Based System
- [ ] Every Fragment with ViewBinding nulls `_binding` in `onDestroyView`
- [ ] No Activity, Fragment, View, or Binding stored in ViewModel, singleton, or companion object
- [ ] All singletons and long-lived objects use `applicationContext`, not Activity context
- [ ] Every listener/observer/receiver registration has a symmetric unregister in the paired lifecycle method
- [ ] `ConnectivityManager.CONNECTIVITY_ACTION` not used (deprecated API 28+) — use `NetworkCallback`
- [ ] LiveData observed with `viewLifecycleOwner` (not `this`) in Fragments
- [ ] Flow collected inside `repeatOnLifecycle(STARTED)` block
- [ ] No `GlobalScope.launch` in any production code
- [ ] All Cursor, InputStream, OutputStream, MediaPlayer, DB connections use `use {}`
- [ ] Handler `postDelayed` runnables have matching `removeCallbacks` in teardown
- [ ] Custom Views release animators, bitmaps, and listeners in `onDetachedFromWindow`
- [ ] Custom Views call `TypedArray.recycle()` (or `use {}`) in `init {}` — always in `finally`
- [ ] `registerForActivityResult` called at Fragment/Activity construction time, not in `onViewCreated`
- [ ] `NavController.addOnDestinationChangedListener` paired with `removeOnDestinationChangedListener` in `onDestroyView`
- [ ] `by lazy {}` in Fragment does not capture `this` — uses `applicationContext` or deferred init pattern
- [ ] `Choreographer.postFrameCallback` has matching `removeFrameCallback` in `onPause`/`onDestroyView`
- [ ] `ProcessLifecycleOwner` observers use only application-scoped objects — never Activity/Fragment instances
- [ ] Services call `stopSelf()` on task completion; WorkManager preferred over long-running services
- [ ] WebView hosted in a separate process via `android:process`
- [ ] LeakCanary in debug builds; zero leaked signatures suppressed without documented justification
- [ ] Hilt / DI scope annotations match the actual lifetime of each dependency

### Jetpack Compose System
- [ ] `remember(key)` correctly parameterized to invalidate when meaningful input changes
- [ ] All resources opened in composables (DB, streams, players, SDK clients) use `DisposableEffect` with `onDispose` cleanup
- [ ] `LocalContext.current.applicationContext` used for long-lived remembered objects and Toast (not Activity context)
- [ ] Lambdas passed to long-lived objects use `rememberUpdatedState`; paired with `DisposableEffect` for cleanup
- [ ] No composable lambdas or composition-scoped objects stored in ViewModels
- [ ] No `CoroutineScope()` created bare in a composable — use `rememberCoroutineScope()`
- [ ] `LaunchedEffect` keys correctly represent when the effect should restart
- [ ] Every `DisposableEffect` has a non-empty `onDispose` block
- [ ] No `MutableState` or naked `CoroutineScope` in application-scoped singletons
- [ ] `RememberObserver` implementations launch work in `onRemembered`, not `init {}`
- [ ] `SharedFlow` replay buffer sized to minimum needed; large-payload flows use `StateFlow` or ID-only emission
- [ ] Expensive in-composable computations wrapped in `remember(key)` or moved to ViewModel
- [ ] `LazyColumn`/`LazyRow` items use stable `key = { item.id }`
- [ ] Toast, analytics, and other side-effects placed in `LaunchedEffect` with `applicationContext`

### Detection and Tooling
- [ ] LeakCanary 2.14 in debug builds with `DetectLeaksAfterTestSuccess` rule in UI tests
- [ ] `adb shell dumpsys meminfo` Activity count checked after navigation — drops to 1 after Back
- [ ] Heap dump captured via `adb shell am dumpheap` or Memory Profiler after repeated navigation
- [ ] `ApplicationExitInfo` queried at startup to detect `REASON_LOW_MEMORY` exits in production
