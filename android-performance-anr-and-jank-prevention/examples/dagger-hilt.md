# Samples: Dagger and Hilt

## Contents
- Measure injection
- Defer heavy bindings with Lazy
- Prewarm after first frame
- Constructors without side effects
- Application scope for background work
- Receivers and services
- Process-aware Application

## Measure injection

```kotlin
@AndroidEntryPoint
class HomeActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        trace("home:super.onCreate+inject") { super.onCreate(savedInstanceState) } // Hilt injects here
        ...
    }
}

// Plain Dagger
trace("home:inject") { (application as App).component.homeComponent().inject(this) }
```

## Defer heavy bindings with Lazy

```kotlin
// ❌ Every provider runs inside inject(this), on main, before the first frame
@Inject lateinit var authStartup: AuthStartup
@Inject lateinit var signalTracker: SignalTracker

// ✅ Built on first .get(), not during injection
@Inject lateinit var authStartup: dagger.Lazy<AuthStartup>
@Inject lateinit var signalTracker: dagger.Lazy<SignalTracker>
```

`Lazy.get()` on main still constructs on main. Pair it with a background prewarm, or make the
first `.get()` happen off main or after first frame.

## Prewarm after first frame

```kotlin
@Inject lateinit var reminderScheduler: dagger.Lazy<ReminderScheduler>   // scoped (@Singleton or component scope)
@Inject @ApplicationScope lateinit var appScope: CoroutineScope

override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContentView(binding.root)
    window.decorView.post {                       // after first layout and draw
        appScope.launch(Dispatchers.IO) { reminderScheduler.get() }
    }
}
```

The binding must be scoped, or main gets a fresh instance later and the prewarm is wasted.

## Constructors without side effects

```kotlin
// ❌ Construction does I/O and registers observers
class LoginPromptObserver @Inject constructor(prefs: SharedPreferences, bus: EventBus) {
    private val shown = prefs.getBoolean("shown", false)
    init { bus.register(this) }
}

// ✅ Plain constructor, explicit start() called from a deferred initializer
class LoginPromptObserver @Inject constructor(
    private val prefs: Lazy<SharedPreferences>,
    private val bus: EventBus,
) {
    fun start() { bus.register(this) }
}
```

## Application scope for background work

```kotlin
@Qualifier annotation class ApplicationScope

@Module
@InstallIn(SingletonComponent::class)
object CoroutinesModule {
    @Provides @Singleton @ApplicationScope
    fun appScope(): CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
}
```

## Receivers and services

```kotlin
// ❌ Injecting a large graph into a receiver that runs on cold start
@AndroidEntryPoint
class PushReceiver : BroadcastReceiver() {
    @Inject lateinit var handler: PushHandler    // pulls in analytics, SDKs, repositories
    ...
}

// ✅ Inject a small entry point lazily and hand off quickly
@AndroidEntryPoint
class PushReceiver : BroadcastReceiver() {
    @Inject lateinit var handler: dagger.Lazy<PushHandler>
    @Inject @ApplicationScope lateinit var appScope: CoroutineScope

    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        appScope.launch(Dispatchers.IO) {
            try { handler.get().handle(intent) } finally { pending.finish() }
        }
    }
}
```

## Process-aware Application

```kotlin
@HiltAndroidApp
class App : Application() {
    override fun onCreate() {
        super.onCreate()                      // Hilt builds the SingletonComponent here
        if (!isMainProcess()) return          // skip app init in :push and other processes
        startMainProcessInit()
    }

    private fun isMainProcess(): Boolean =
        if (Build.VERSION.SDK_INT >= 28) Application.getProcessName() == packageName
        else true // check /proc/self/cmdline on older devices if you use extra processes
}
```

Hilt still creates the singleton component in every process; keep `@Singleton` constructors
cheap so that is not expensive.
