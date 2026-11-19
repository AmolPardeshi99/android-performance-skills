# The DI graph as a hidden call graph

## Contents
- Why DI hides cost
- Where it shows up
- How to measure it
- Fixes
- Review checks

Framework code: [../examples/dagger-hilt.md](../examples/dagger-hilt.md),
[../examples/koin.md](../examples/koin.md).

## Why DI hides cost

`inject(this)` and `by inject()` read like one line, but they run every constructor and
`@Provides` method in the transitive closure of what you asked for. Constructors open prefs,
build Retrofit and Gson instances, register listeners, and initialize SDKs. None of that is
visible at the call site, and it all runs on the thread that injects, which for Activities and
Fragments is main.

Compile-time DI (Dagger, Hilt) makes lookup cheap but not construction. Runtime DI (Koin) adds
lookup and resolution cost on top. Both build objects on the calling thread.

## Where it shows up

- In traces: `DaggerXComponent.inject`, `XComponentImpl.injectYActivity`, `*_Factory.get`,
  `DoubleCheck.get`, `Hilt_YActivity.onCreate`, Koin `InstanceFactory.create`.
- In `Activity.onCreate` before the first frame. Field injection happens in `super.onCreate()`
  for Hilt and wherever you call `inject(this)` for Dagger.
- In receivers and services, where a cold start plus injection eats the timeout. See
  [receivers-and-processes.md](receivers-and-processes.md).
- Nested or subcomponent creation per screen, rebuilt each time the screen opens.

## How to measure it

- Wrap the inject call in a trace section, `trace("inject:Home") { component.inject(this) }`,
  and read its duration in Perfetto across several cold starts on a low-end device.
- Add sections inside heavy `@Provides` methods to see which binding dominates.
- One home screen's injection took 130 to 150 ms. Deferring a handful of heavy bindings brought
  it to 20 to 25 ms, an 83% cut on one of the most frequently run paths in the app.

## Fixes

1. **Defer with `Lazy<T>` or `Provider<T>`.** The binding is not constructed during
   `inject(this)`, only on first `.get()`. This only helps if the first `.get()` is off main
   or after the first frame; `Lazy.get()` on main still constructs on main.
2. **Prewarm on a background thread.** After first frame, call `.get()` from an IO coroutine
   so the object is ready by the time main needs it. Make sure the binding is scoped
   (`@Singleton`, or a component scope) so main gets the same instance.
3. **Move side effects out of constructors.** A constructor that registers observers, reads
   prefs, or starts SDKs should become a plain constructor plus an explicit `start()` called
   from a background initializer.
4. **Defer whole features.** Observers that only matter after login or after the first screen,
   such as prompts and reminders, can register after first frame.
5. **Move independent checks off main.** Device checks such as SIM change detection need not
   run on main during `onCreate`.
6. **Avoid rebuilding subcomponents** per screen when the dependencies are app-scoped.
7. **For Koin**, use `lazyModules` for modules not needed at startup, avoid `createdAtStart`
   for heavy singletons, and prefer `by inject()` (lazy) over `get()` in fields.

Put each deferral behind a remote flag. Deferring changes initialization order, and the bugs it
causes (something that assumed it was initialized) show up only in some flows.

## Review checks

- `@Inject` fields on Activities, Fragments, receivers, and services whose types have heavy
  constructors or heavy transitive dependencies.
- `@Provides` methods that do I/O, parsing, SDK init, or network client construction.
- `Lazy.get()` or `Provider.get()` called on main in `onCreate` or `onResume`, which undoes
  the deferral.
- Koin `get()` in `Application.onCreate` or `Activity.onCreate` for heavy definitions.
- `@Singleton` objects created on main the first time a screen opens.
