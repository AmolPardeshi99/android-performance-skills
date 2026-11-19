# Memory model: roots, references, and cost

## Contents
- How ART decides what to collect
- GC roots on Android
- The classic leak chain
- Reference types
- Why a leaked Activity is expensive
- Leak versus waste

## How ART decides what to collect

ART uses a tracing collector. It starts from a set of roots and marks everything reachable.
Anything not reachable is freed. A leak is an object the app no longer needs that is still
reachable from a root.

## GC roots on Android

| Root | Examples |
|---|---|
| Static fields | `companion object` fields, `object` singletons, Java `static` fields |
| Thread stacks | Locals and parameters on any running thread, including pool threads waiting for work |
| Running threads | The `Thread` object and its `Runnable` |
| JNI global references | Objects held by native code, including some SDKs and WebView |
| Main looper queue | Pending `Message`s, reachable through the main thread |

## The classic leak chain

```
static field / singleton (root)
  └─ manager, SDK, or event bus
       └─ listener, callback, or lambda
            └─ Activity or Fragment (captured as `this`)
                 └─ View tree, Binding, Bitmaps
```

## Reference types

| Type | Collected when | Use |
|---|---|---|
| Strong | Never while reachable | Default |
| `SoftReference` | Under memory pressure | Rarely a good idea on Android; prefer `LruCache` |
| `WeakReference` | At the next GC once no strong refs remain | Optional back-references from long-lived objects |
| `PhantomReference` | After finalization | Low-level cleanup; not app code |

## Why a leaked Activity is expensive

A leaked Activity retains its whole View tree, every Bitmap those views hold, its Binding, its
`Window`, and anything its fields reference. On a typical screen that is several MB, and leaks
repeat each time the user opens the screen. More retained memory means more frequent GC (jank),
and eventually `OutOfMemoryError` or the system killing the process in the background.

## Leak versus waste

- **Leak**: reachable but no longer needed because of a missing cleanup. LeakCanary finds the
  common ones (Activities, Fragments, Views, ViewModels, Services).
- **Waste**: reachable and arguably needed, but far bigger than necessary: an unbounded cache, a
  replay buffer holding a large page, 80 idle pool threads each with a 1 MB stack. LeakCanary
  does not report these. Look at retained size in a heap dump and at thread counts.
