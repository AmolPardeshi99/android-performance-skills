# Samples: Coroutines and Flow

## Contents
- Main-safe repositories
- Mapping after a suspend call
- runBlocking on main
- GlobalScope
- Batch dispatcher switches
- Mutex instead of synchronized
- Serial dispatcher instead of nested locks
- Cancellation in loops
- Bridging an Rx call
- Prefs off main, and DataStore
- Bounded waits

## Main-safe repositories

```kotlin
class UserRepository(private val api: UserApi, private val io: CoroutineDispatcher = Dispatchers.IO) {
    // Callers can use this from main; network and mapping run on IO.
    suspend fun getUser(id: String): User = withContext(io) { api.fetchUser(id).toUser() }
}
```

## Mapping after a suspend call

```kotlin
// ❌ Retrofit runs the network call off main, but toUser() runs back on main
viewModelScope.launch {
    val dto = api.fetchUser(id)
    _state.value = UiState.Success(dto.toUser())
}

// ✅
viewModelScope.launch {
    val user = withContext(Dispatchers.Default) { api.fetchUser(id).toUser() }
    _state.value = UiState.Success(user)
}
```

## runBlocking on main

```kotlin
// ❌ Blocks main; deadlocks if the inner code needs main
val config = runBlocking { configRepo.fetch() }

// ✅
lifecycleScope.launch { applyConfig(configRepo.fetch()) }
```

## GlobalScope

```kotlin
// ❌ No owner, no cancellation, errors lost
GlobalScope.launch(Dispatchers.IO) { repo.sync() }

// ✅ Injected application scope
class SyncUseCase(private val appScope: CoroutineScope) {
    fun sync(): Job = appScope.launch(Dispatchers.IO) { repo.sync() }
}
```

## Batch dispatcher switches

```kotlin
suspend fun loadOrder(id: String) {
    showLoading()
    val (order, history) = withContext(Dispatchers.IO) {
        coroutineScope {
            val o = async { api.fetch(id) }
            val h = async { api.fetchHistory(id) }
            o.await() to h.await()
        }
    }
    show(order, history)
}
```

## Mutex instead of synchronized

```kotlin
// ❌ Monitor held across a suspension point
suspend fun refresh() = synchronized(lock) { cache.put(fetch()) }

// ✅
private val mutex = Mutex()
suspend fun refresh() {
    val data = fetch()                  // suspend outside the lock
    mutex.withLock { cache.put(data) }
}
```

## Serial dispatcher instead of nested locks

```kotlin
private val serial = Dispatchers.IO.limitedParallelism(1)
suspend fun log(event: Event) = withContext(serial) { db.insert(event) }
```

## Cancellation in loops

```kotlin
suspend fun crunch(items: List<Item>) = withContext(Dispatchers.Default) {
    items.forEachIndexed { i, item ->
        if (i % 200 == 0) ensureActive()
        compute(item)
    }
}
```

## Bridging an Rx call

```kotlin
// kotlinx-coroutines-rx3
lifecycleScope.launch {
    withContext(Dispatchers.IO) { shortcutsRepo.syncRx().await() }   // Completable.await()
}
```

## Prefs off main, and DataStore

```kotlin
class TokenStore(context: Context, private val appScope: CoroutineScope) {
    private val prefs = appScope.async(Dispatchers.IO) {
        context.getSharedPreferences("auth", Context.MODE_PRIVATE).also { it.all } // force load
    }
    suspend fun token(): String? = prefs.await().getString("token", null)
}

// Preferred
val Context.settings by preferencesDataStore("settings")
val darkMode: Flow<Boolean> = context.settings.data.map { it[DARK_MODE] ?: false }
```

## Bounded waits

```kotlin
// Waiting for a cross-process service connection, with an upper bound
val messenger: Messenger? = withTimeoutOrNull(4_000) { connection.awaitMessenger() }
if (messenger == null) fallbackHandle(payload) else messenger.send(toMessage(payload))
```
