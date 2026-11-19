# Samples: Jetpack Compose

## Contents
- Heavy work in composition
- Fast-changing state read too high
- Deferred reads with lambda modifiers
- Backwards writes
- Stable parameters
- Lazy list keys
- Side effects
- Formatters and first-touch costs
- Deferring below-the-fold content
- Compiler reports

For deeper recomposition work, Google's `jetpack-compose-performance` skill goes further.

## Heavy work in composition

```kotlin
// ❌ Sorts on every recomposition, on main
@Composable
fun ContactList(contacts: List<Contact>, comparator: Comparator<Contact>) {
    val sorted = contacts.sortedWith(comparator)
    LazyColumn { items(sorted) { ContactRow(it) } }
}

// ✅ Recomputed only when inputs change
@Composable
fun ContactList(contacts: List<Contact>, comparator: Comparator<Contact>) {
    val sorted = remember(contacts, comparator) { contacts.sortedWith(comparator) }
    LazyColumn { items(sorted, key = { it.id }) { ContactRow(it) } }
}

// ✅ Best: the ViewModel does it off main
val sortedContacts: StateFlow<List<Contact>> =
    combine(contactsFlow, comparatorFlow) { list, cmp -> list.sortedWith(cmp) }
        .flowOn(Dispatchers.Default)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
```

## Fast-changing state read too high

```kotlin
// ❌ Whole screen recomposes on every scroll pixel
val offset = listState.firstVisibleItemScrollOffset

// ✅ Recomposes only when the boolean flips
val collapsed by remember { derivedStateOf { listState.firstVisibleItemIndex > 0 } }
```

## Deferred reads with lambda modifiers

```kotlin
// ❌ Reads state in composition
Box(Modifier.offset(y = (-scrollState.value).dp))

// ✅ Reads state in layout; no recomposition
Box(Modifier.offset { IntOffset(0, -scrollState.value) })

// Same idea: Modifier.graphicsLayer { alpha = ... }, Modifier.drawBehind { drawRect(color) }
```

## Backwards writes

```kotlin
// ❌ Writes state after reading it in the same composition: endless recomposition
@Composable
fun BadCounter() {
    var count by remember { mutableIntStateOf(0) }
    Text("$count")
    count++
}

// ✅ Write in event handlers or effects only
@Composable
fun GoodCounter() {
    var count by remember { mutableIntStateOf(0) }
    Button(onClick = { count++ }) { Text("Count: $count") }
}
```

## Stable parameters

```kotlin
@Immutable
data class OrderUi(val id: String, val total: String)

@Composable
fun OrderList(orders: ImmutableList<OrderUi>) { /* kotlinx.collections.immutable */ }
```

With strong skipping (default from Kotlin 2.0.20), unstable parameters are compared by
instance, so stability matters less than before, but new list instances each emission still
defeat skipping.

## Lazy list keys

```kotlin
LazyColumn {
    items(notes, key = { it.id }, contentType = { it.type }) { NoteRow(it) }
}
```

## Side effects

```kotlin
// ❌ Blocks main and repeats on each recomposition
val product = runBlocking { repo.fetch(id) }

// ✅
LaunchedEffect(id) { viewModel.load(id) }
val product by viewModel.product.collectAsStateWithLifecycle()
```

## Formatters and first-touch costs

```kotlin
// ❌ New formatter (and possibly ICU load) per recomposition
Text(SimpleDateFormat("dd MMM", Locale.getDefault()).format(date))

// ✅ Format in the ViewModel, or reuse one formatter
private val dayFormatter = DateTimeFormatter.ofPattern("dd MMM", Locale.getDefault())
val dateLabel = remember(date) { dayFormatter.format(date) }
```

## Deferring below-the-fold content

```kotlin
@Composable
fun HomeScreen(state: HomeUi) {
    LazyColumn {
        item(key = "header") { Header(state.header) }
        items(state.sections, key = { it.id }) { Section(it) }  // composed only when visible
    }
}

// For a heavy overlay that is not needed for the first frame:
var showOverlay by remember { mutableStateOf(false) }
LaunchedEffect(Unit) { withFrameNanos { }; delay(20); showOverlay = true }
if (showOverlay) DecorativeOverlay()
```

## Compiler reports

```kotlin
// build.gradle.kts
composeCompiler {
    reportsDestination = layout.buildDirectory.dir("compose_compiler")
    metricsDestination = layout.buildDirectory.dir("compose_compiler")
}
```

Look for composables that are `restartable` but not `skippable`, and parameters marked
`unstable`.
