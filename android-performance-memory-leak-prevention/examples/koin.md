# Samples: Koin

## Contents
- single only for app-wide objects
- Activity and Fragment scopes
- Passing the Activity as a parameter
- ViewModels

## single only for app-wide objects

```kotlin
val appModule = module {
    single { ImageCache(androidContext()) }   // androidContext() is the Application
    // ❌ single { Navigator(get<Activity>()) }
}
```

## Activity and Fragment scopes

```kotlin
val homeModule = module {
    scope<HomeActivity> {
        scoped { HomePresenter(get()) }        // closed with the Activity
    }
}

class HomeActivity : ScopeActivity() {        // or AppCompatActivity(), AndroidScopeComponent
    private val presenter: HomePresenter by inject()
}
```

## Passing the Activity as a parameter

```kotlin
val dialogModule = module {
    factory { (activity: Activity) -> DialogHelper(activity) }   // new instance per call; not retained
}

private val dialogs: DialogHelper by inject { parametersOf(this) }
```

## ViewModels

```kotlin
val vmModule = module { viewModel { ProfileViewModel(get()) } }
private val viewModel: ProfileViewModel by viewModel()
```

Never pass an Activity or View into a `viewModel {}` definition.
