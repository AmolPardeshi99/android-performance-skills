# Context, statics, and singletons

## Contents
- Which Context to use
- Statics and companion objects
- Singletons that take a Context
- Inner and anonymous classes
- When WeakReference is right

## Which Context to use

| Object | Context |
|---|---|
| Singletons, repositories, Room, OkHttp, WorkManager, SDK clients | `applicationContext` |
| Inflation, dialogs, `startActivity`, themed resources | The Activity, only within its lifecycle |
| Location, alarm, camera, connectivity managers | `applicationContext` |
| RecyclerView adapters | `parent.context` in `onCreateViewHolder`; do not store the Activity |
| Composables | `LocalContext.current` inside composition; `.applicationContext` for anything remembered long-term |

`applicationContext` has no theme. Using it to inflate views or show dialogs gives wrong styling
or crashes, so do not "fix" those cases with it.

## Statics and companion objects

A static field is a GC root for the life of the process. Never store an Activity, Fragment,
View, Binding, or Drawable with callbacks in one.

```kotlin
// ❌
companion object { var current: HomeActivity? = null }

// ✅ Share state through a ViewModel or an app-scoped StateFlow instead
```

## Singletons that take a Context

```kotlin
// ❌ Keeps whichever Activity called init first
object ImageLoader { lateinit var context: Context; fun init(c: Context) { context = c } }

// ✅
object ImageLoader { lateinit var context: Context; fun init(c: Context) { context = c.applicationContext } }
```

## Inner and anonymous classes

Inner classes, anonymous `object :` expressions, and lambdas that use members of the enclosing
Activity capture it. Passing one to anything app-scoped (an event bus, SDK, singleton manager)
leaks the Activity until it is removed. Keep a reference to the listener and remove it in the
paired lifecycle callback. See [listeners-and-callbacks.md](listeners-and-callbacks.md).

In Java, use a static nested class for `Runnable`s and `Handler`s that may outlive the Activity.

## When WeakReference is right

Use it when the long-lived side genuinely does not care whether the target is still there, such
as an optional callback to a screen that may have closed. Do not use it to paper over a missing
unregister: the listener still runs until the next GC, and logic that depends on GC timing is
hard to test.
