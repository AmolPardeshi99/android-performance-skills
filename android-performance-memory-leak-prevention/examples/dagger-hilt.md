# Samples: Dagger and Hilt

## Contents
- Singletons take only application-scoped dependencies
- Activity context only in Activity scope
- Do not cache Activity-bound components
- Presenters scoped to the screen
- App coroutine scope

## Singletons take only application-scoped dependencies

```kotlin
// ❌ A singleton holding an Activity-scoped dependency keeps that Activity forever
@Singleton
class GlobalCache @Inject constructor(private val navigator: ActivityNavigator) // @ActivityScoped

// ✅
@Singleton
class GlobalCache @Inject constructor(
    @ApplicationContext private val context: Context,
    private val repo: CacheRepository,   // @Singleton
)
```

## Activity context only in Activity scope

```kotlin
@ActivityScoped
class DialogHelper @Inject constructor(@ActivityContext private val context: Context)
```

## Do not cache Activity-bound components

```kotlin
// ❌ Component built with the Activity, stored app-wide "to avoid rebuilding"
object SignInComponentHolder { var component: SignInComponent? = null }

class SignInActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SignInComponentHolder.component = appComponent.signInComponent().create(this)
        SignInComponentHolder.component!!.inject(this)
    }
}

// ✅ Keep it in the Activity; it dies with the Activity
class SignInActivity : AppCompatActivity() {
    private lateinit var component: SignInComponent
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        component = appComponent.signInComponent().create(this)
        component.inject(this)
    }
}
```

## Presenters scoped to the screen

```kotlin
// ❌ @Singleton presenter keeps the last attached view
@Singleton class LogoutPresenter @Inject constructor(...)

// ✅
@ActivityScoped class LogoutPresenter @Inject constructor(...) {
    private var view: LogoutView? = null
    fun attach(v: LogoutView) { view = v }
    fun detach() { view = null }
}
```

## App coroutine scope

```kotlin
@Module @InstallIn(SingletonComponent::class)
object ScopeModule {
    @Provides @Singleton @ApplicationScope
    fun appScope(): CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
}
```

Work launched in it must not capture Views, Bindings, or Activities.
