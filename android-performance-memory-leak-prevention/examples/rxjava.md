# Samples: RxJava

## Contents
- CompositeDisposable per owner
- Fragment views: clear, not dispose
- ViewModels
- Subjects held by singletons
- Long-lived streams from screens

## CompositeDisposable per owner

```kotlin
class OrdersActivity : AppCompatActivity() {
    private val disposables = CompositeDisposable()

    override fun onStart() {
        super.onStart()
        disposables += repo.orders()
            .observeOn(AndroidSchedulers.mainThread())
            .subscribe(::render, ::showError)
    }

    override fun onStop() {
        disposables.clear()
        super.onStop()
    }
}
```

## Fragment views: clear, not dispose

```kotlin
private val viewDisposables = CompositeDisposable()

override fun onDestroyView() {
    viewDisposables.clear()        // can be reused when the view is recreated
    super.onDestroyView()
}
```

## ViewModels

```kotlin
class OrdersViewModel(repo: OrdersRepo) : ViewModel() {
    private val disposables = CompositeDisposable()
    init { disposables += repo.orders().subscribe(_orders::postValue) }
    override fun onCleared() { disposables.dispose() }
}
```

## Subjects held by singletons

```kotlin
// ❌ An app-wide BehaviorSubject of a UI object keeps the last screen's data (and anything it references)
object Bus { val lastScreen = BehaviorSubject.create<Fragment>() }

// ✅ Emit plain data, never Views, Fragments, or Activities
object Bus { val events = PublishSubject.create<NavEvent>() }
```

## Long-lived streams from screens

`Observable.interval`, location streams, and websocket streams never complete. Without
disposal they keep the observer, and the screen it captures, alive for the life of the process.
