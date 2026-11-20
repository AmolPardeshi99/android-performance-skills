# Samples: Koin

## Contents
- Measure startKoin and resolution
- Lazy modules
- createdAtStart
- inject versus get
- Prewarm off main
- Receivers and extra processes

Koin resolves definitions at run time on the calling thread. Resolution of a deep graph from an
Activity is main-thread work, in addition to constructor cost.

## Measure startKoin and resolution

```kotlin
class App : Application() {
    override fun onCreate() {
        super.onCreate()
        trace("koin:start") {
            startKoin {
                androidContext(this@App)
                modules(coreModule)
            }
        }
    }
}
```

## Lazy modules

```kotlin
// Modules not needed for the first screen load in the background (Koin 3.5+)
val featureModules = lazyModule { includes(paymentsModule, promoModule) }

startKoin {
    androidContext(this@App)
    modules(coreModule)
    lazyModules(featureModules)
}

// Before the first use of a feature, wait for background loading off main if needed:
// KoinPlatform.getKoin().waitAllStartJobs()
```

## createdAtStart

```kotlin
// ❌ Built on main during startKoin
single(createdAtStart = true) { AnalyticsClient(get(), get()) }

// ✅ Built on first use; prewarm it off main if the first use is on a hot path
single { AnalyticsClient(get(), get()) }
```

## inject versus get

```kotlin
class HomeActivity : AppCompatActivity() {
    // ❌ Resolved and constructed when the Activity is created
    private val tracker: SignalTracker = get()

    // ✅ Resolved on first access
    private val tracker: SignalTracker by inject()
}
```

## Prewarm off main

```kotlin
override fun onResume() {
    super.onResume()
    lifecycleScope.launch(Dispatchers.IO) { get<ReminderScheduler>() }   // must be a single {}
}
```

## Receivers and extra processes

```kotlin
class PushReceiver : BroadcastReceiver(), KoinComponent {
    private val handler: PushHandler by inject()
    private val appScope: CoroutineScope by inject(named("app"))

    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        appScope.launch(Dispatchers.IO) {
            try { handler.handle(intent) } finally { pending.finish() }
        }
    }
}
```

In apps with extra processes, call `startKoin` with only the modules that process needs.
