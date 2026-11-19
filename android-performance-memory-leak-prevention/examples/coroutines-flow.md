# Samples: Coroutines and Flow

## Contents
- Scope per owner
- Hand-made scopes
- App-scoped work without UI references
- Collecting with the view lifecycle
- SharedFlow replay
- stateIn sharing

## Scope per owner

```kotlin
// Fragment view
viewLifecycleOwner.lifecycleScope.launch { binding.total.text = repo.total() }
// ViewModel
viewModelScope.launch { _state.value = repo.load() }
```

## Hand-made scopes

```kotlin
class Player(private val view: PlayerView) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    fun start() { scope.launch { tick() } }
    fun release() { scope.cancel() }              // call from the owner's teardown
}
```

## App-scoped work without UI references

```kotlin
// ❌ Captures the Fragment and its binding in an app-wide coroutine
appScope.launch { val r = api.upload(file); binding.status.text = r.message }

// ✅ App scope does the work; UI observes a result
appScope.launch { uploads.emit(api.upload(file)) }
viewLifecycleOwner.lifecycleScope.launch {
    viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
        uploads.collect { binding.status.text = it.message }
    }
}
```

## Collecting with the view lifecycle

```kotlin
viewModel.state
    .flowWithLifecycle(viewLifecycleOwner.lifecycle, Lifecycle.State.STARTED)
    .onEach(::render)
    .launchIn(viewLifecycleOwner.lifecycleScope)
```

## SharedFlow replay

```kotlin
// ❌ Last page of results pinned with or without collectors
private val _results = MutableSharedFlow<SearchPage>(replay = 1)

// ✅ Events: no replay
private val _events = MutableSharedFlow<SearchEvent>(extraBufferCapacity = 1)

// ✅ State: StateFlow, cleared when the user leaves
private val _results = MutableStateFlow<SearchPage?>(null)
fun clear() { _results.value = null }
```

## stateIn sharing

```kotlin
val profile = repo.profile.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
```
