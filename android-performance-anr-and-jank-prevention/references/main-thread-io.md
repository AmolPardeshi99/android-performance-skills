# Main-thread I/O and parsing

## Contents
- SharedPreferences
- Parsing JSON or protobuf on main
- Static config parsed at runtime
- Decoding a big object to read one field
- Flags whose default is the slow path
- ContentProvider and startup initializers
- Files, databases, Binder queries
- How to confirm

Code for each async framework is in [../examples/coroutines-flow.md](../examples/coroutines-flow.md)
and [../examples/rxjava.md](../examples/rxjava.md).

## SharedPreferences

Three separate costs:

1. **First read of a file.** `getSharedPreferences()` starts loading on a background thread, but
   the first `getX()` blocks until the whole XML file is parsed (`awaitLoadedLocked`). Large
   files, or many files read at startup, block main.
2. **`commit()`** writes to disk synchronously on the calling thread.
3. **`apply()`** is asynchronous, but the system waits for pending writes in
   `QueuedWork.waitToFinish()` on main during activity stop and service start. Many `apply()`
   calls before a stop show up as ANRs in framework code, not yours.

Fixes, in order of preference:

- Move the data to DataStore (Preferences or Proto). No synchronous flush on lifecycle events.
- If you cannot migrate yet, wrap prefs in a store that loads into memory on a background thread
  at startup, serves reads from memory, and writes through a single background executor. Reads
  that arrive before the cache is ready can fall back to the real prefs. Measured effect in one
  large app: the prefs-related ANR rate fell by about a fifth after rollout.
- Split one large prefs file into small ones by feature, so a screen only loads what it needs.
- Never `commit()` on main.

If you build a background store, give it a **bounded** executor. An unbounded cached pool for
prefs writes was seen spawning 70 to 80 threads on some devices, about 1 MB of stack each.
Capping it at a fixed pool of 8 cut that overhead from roughly 80 MB to 8 MB. See
[threading-and-locks.md](threading-and-locks.md).

## Parsing JSON or protobuf on main

`Gson.fromJson`, Moshi adapters, `JSONObject`, and `parseFrom` are CPU work. On low-end devices
a mid-sized payload can take hundreds of milliseconds. They end up on main when:

- mapping happens after a suspend call inside `viewModelScope.launch` without `withContext`;
- `map {}` comes after `observeOn(AndroidSchedulers.mainThread())` in RxJava;
- a "simple getter" decodes JSON stored in prefs every time it is called.

Move parsing to the data layer so callers get domain objects, and make repositories main-safe.

## Static config parsed at runtime

A JSON string constant that never changes, parsed every time it is used, is pure waste. In one
case a config string unchanged for two years cost 1.5 to 2 s per parse on main; replacing it
with a typed Kotlin object took the path's ANR rate from 0.93 to 0.71.

Fix: replace the string with a Kotlin `object` or `data class` constant, or generate one at
build time. Do not just move the parse to a background thread.

## Decoding a big object to read one field

A helper like `getCountryCode()` that loads a large JSON blob from prefs and decodes it with
Gson to read one field can cost up to about 2 s in the worst case, and gets called from many
startup and navigation paths. Store the field you need as its own flat value and read that.

## Flags whose default is the slow path

A cached fast path guarded by a remote flag whose default is `false` silently falls back to the
slow path whenever the flag has not been fetched yet, which is most cold starts. When you review
a performance fix behind a flag, check what happens before remote config loads. Once a fix is
proven, make the fast path the only path and delete the flag.

## ContentProvider and startup initializers

Every `ContentProvider.onCreate()` and every Jetpack App Startup `Initializer.create()` runs on
main before `Application.onCreate()` finishes. Libraries add providers through manifest
merging, so check the merged manifest, not just yours.

- Do heavy SDK setup in a background coroutine from `Application.onCreate`, or lazily on first
  use.
- Remove SDK auto-init providers with `tools:node="remove"` when the SDK supports manual init.
- A provider is also a legitimate place to **start** background prewarming early, as long as
  `onCreate` only launches the work and returns. See
  [class-init-first-touch.md](class-init-first-touch.md).

## Files, databases, Binder queries

- File reads, Room non-suspend DAO calls, `SQLiteOpenHelper.getWritableDatabase()`,
  `BitmapFactory.decode*`, `MediaPlayer.prepare()`: always off main.
- `ContentResolver.query`, `PackageManager` calls, `AccountManager`, `Settings` reads are
  Binder calls into other processes. They are usually fast but can take seconds under system
  load. Keep them off startup and input paths.

## How to confirm

- StrictMode `detectDiskReads().detectDiskWrites().detectNetwork()` in debug builds.
- In Perfetto, look for long slices on main under `bindApplication`, `activityStart`,
  `activityResume`, and check thread state for `D` (uninterruptible, usually I/O).
- Trace sections around suspect calls: `trace("prefs:load") { ... }` from `androidx.tracing`.
