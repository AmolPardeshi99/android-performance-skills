---
name: android-performance-memory-leak-prevention
description: >
  Investigates Android memory leaks, OOMs, and memory waste, and reviews Android code for them.
  Use whenever an Android question involves something staying in memory too long: a LeakCanary
  trace, a heap dump (including how to capture or analyze one from the command line), an
  OutOfMemoryError, dumpsys meminfo, memory or thread count that keeps growing, or a leak review
  of Activities, Fragments, ViewBinding, custom Views, ViewModels, Compose effects, coroutine or
  Rx scopes, DI scopes, listeners, Handlers, WebView, bitmaps, or executors. Also use it for
  short questions such as "is it OK to hold this Context or listener here", which Context a
  singleton should keep, whether a register/addListener call needs a matching remove, or what to
  clear in onDestroyView. Covers Views and Compose, Dagger/Hilt and Koin, coroutines and RxJava.
  Not for ANRs or jank (use the ANR skill).
license: Apache-2.0
metadata:
  version: "2.0.0"
  keywords: "memory leak, OOM, LeakCanary, heap dump, ViewBinding, Compose, lifecycle, code review"
---

# Memory leaks: investigation and review

Two tasks. Pick one first.

| The user gives you | Task |
|---|---|
| A LeakCanary trace, heap dump, OOM stack, `dumpsys meminfo`, "memory keeps growing" | **A. Investigate** |
| Source files, a diff or PR, "review this for leaks", "is this safe to hold here" | **B. Review** |
| Both | A, then B on the classes in the leak trace |

If unclear, ask: "Do you want me to explain a specific leak, or review code for leaks?"

Read a reference only when a step sends you there. Each one has a table of contents.

## A. Investigate a leak or OOM

```
- [ ] 1. Identify the evidence type
- [ ] 2. Find the leaking object and the reference that should not exist
- [ ] 3. Match to a pattern
- [ ] 4. Fix at the owner of the reference
- [ ] 5. Verify the leak is gone
```

1. **Evidence.** LeakCanary trace, HPROF, OOM stack, or meminfo. For anything but a LeakCanary
   trace, follow [references/detection-and-tools.md](references/detection-and-tools.md) to get
   one, or to read the heap dump. To capture a heap dump, run
   `scripts/capture_heap_dump.sh <package>` instead of reading it.
2. **Read the trace.** Go from the GC root down. Find the last object marked `Leaking: NO` and
   the first marked `Leaking: YES`. The reference between them (underlined with `~~~`) is the
   one to break. See [references/leak-trace-reading.md](references/leak-trace-reading.md).
3. **Match a pattern** using the index below, then read that one reference.
4. **Fix at the owner.** Break the reference where the long-lived object holds it: unregister,
   clear, scope correctly, or stop capturing. Do not just wrap it in `WeakReference` unless the
   reference is genuinely optional.
5. **Verify.** Repeat the journey, force GC, and confirm LeakCanary stays quiet and the
   Activity count in `dumpsys meminfo` drops back.

Write the result with [templates/leak-report.md](templates/leak-report.md).

### Pattern index

| Leak trace shows | Pattern | Read |
|---|---|---|
| `Fragment.mView` or a `*Binding` field after `onDestroyView` | View outliving its Fragment | [lifecycle-and-views.md](references/lifecycle-and-views.md) |
| A singleton, `companion object`, or static field holding an Activity, View, or Context | Context and statics | [context-and-statics.md](references/context-and-statics.md) |
| A manager, SDK, `NavController`, `Choreographer`, `ProcessLifecycleOwner` holding a listener or lambda | Listener not removed | [listeners-and-callbacks.md](references/listeners-and-callbacks.md) |
| `MessageQueue` → `Message` → `Handler`/`Runnable` | Delayed message | [listeners-and-callbacks.md](references/listeners-and-callbacks.md) |
| A coroutine `Job`, `StandaloneCoroutine`, Rx `Disposable`, `SharedFlow` replay cache, or a `Thread` | Async work outliving its owner | [async-and-scopes.md](references/async-and-scopes.md) |
| A DI component or scoped object holding an Activity, Presenter, or View | DI scope mismatch | [di-scopes.md](references/di-scopes.md) |
| `ViewModel` holding a View, Activity, Binding, or composable lambda | ViewModel holding UI | [lifecycle-and-views.md](references/lifecycle-and-views.md) |
| Native memory, Bitmaps, WebView, cursors, file handles | Resources | [resources-and-native.md](references/resources-and-native.md) |

## B. Review code for leaks

```
- [ ] 1. List every long-lived holder
- [ ] 2. List what each one holds
- [ ] 3. Check each registration has a matching removal
- [ ] 4. Grade with the checklist
- [ ] 5. Report findings and dismissed candidates
```

1. **Long-lived holders** in the files under review: singletons, `object`s, companion fields,
   DI singletons and scoped components, `ViewModel`s, app-scoped coroutine scopes, SDK managers,
   system services, `Handler`s, threads and pools.
2. **What they hold**: an Activity or Fragment, a View or Binding, a lambda or anonymous class
   that captures one, a composition-scoped value, or a large payload.
3. **Symmetry.** Every `register`/`add`/`subscribe`/`observe`/`post` must have its removal in
   the paired lifecycle callback (`onStart`/`onStop`, `onViewCreated`/`onDestroyView`, effect
   `onDispose`). See the pairing table in
   [references/listeners-and-callbacks.md](references/listeners-and-callbacks.md).
4. **Grade** with [checklists/review-checklist.md](checklists/review-checklist.md). Read the
   linked reference before writing the fix, and give the fix in the user's framework.
5. **Report** with [templates/review-report.md](templates/review-report.md). Dismiss
   candidates where the holder's lifetime is equal to or shorter than what it holds.

## Framework samples

Detect the stack from imports and build files, then load only the matching file.

| Area | Option 1 | Option 2 |
|---|---|---|
| UI | [examples/views.md](examples/views.md) | [examples/compose.md](examples/compose.md) |
| DI | [examples/dagger-hilt.md](examples/dagger-hilt.md) | [examples/koin.md](examples/koin.md) |
| Async | [examples/coroutines-flow.md](examples/coroutines-flow.md) | [examples/rxjava.md](examples/rxjava.md) |

## Topic index

- [references/memory-model.md](references/memory-model.md): GC roots, reference types, leak versus waste
- [references/leak-trace-reading.md](references/leak-trace-reading.md): reading LeakCanary traces and heap dumps
- [references/lifecycle-and-views.md](references/lifecycle-and-views.md): Fragment views, ViewModels, presenters, custom views
- [references/context-and-statics.md](references/context-and-statics.md): which Context, statics, singletons, inner classes
- [references/listeners-and-callbacks.md](references/listeners-and-callbacks.md): registration pairing, Handlers, frame callbacks
- [references/async-and-scopes.md](references/async-and-scopes.md): coroutine scopes, Rx disposables, flows, threads and pools
- [references/di-scopes.md](references/di-scopes.md): DI scopes and components that retain UI
- [references/resources-and-native.md](references/resources-and-native.md): streams, TypedArray, bitmaps, WebView, services
- [references/detection-and-tools.md](references/detection-and-tools.md): LeakCanary, heap dumps, meminfo, OOM tracking, CI

## Rules that apply to both tasks

- Base every claim on the trace or code. Say "likely" when inferring.
- The fix goes where the long-lived reference is created, not where the leaked object lives.
- Treat `WeakReference` as a last resort: it hides the missing cleanup, and the code then
  behaves differently depending on when GC runs.
- `applicationContext` fixes Context leaks only for objects that do not need a themed or
  Activity context (dialogs, inflation, `startActivity` need the Activity).
- A cached value that is legitimately reachable but large is memory waste, not a leak.
  LeakCanary will not report it; a heap dump will.
