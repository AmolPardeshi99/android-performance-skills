# Startup that leaves no gap for input

## Contents
- The pattern
- How to recognize it
- Fix 1: defer whatever is not on screen
- Fix 2: show a skeleton, then fill it
- Fix 3: inflate or build off main
- Fix 4: break work into separate messages
- Measure
- Review checks

Framework code: [../examples/views.md](../examples/views.md),
[../examples/compose.md](../examples/compose.md).

## The pattern

An input ANR needs only one thing: a touch event that the main thread does not start handling
within 5 s. During startup, main often runs task after task: `onCreate`, injection, inflation,
`onResume`, data callbacks, widget setup, more inflation. No single task is long, so no single
stack looks guilty, but the queue never has a gap for the input event. Users tap during this
window because the screen already looks ready.

## How to recognize it

- Input ANRs concentrated in the first seconds after launch, on the main screen.
- A cluster whose top frames vary (inflation, a view constructor, a JSON parse, a prefs read)
  but which all sit under the same activity's `onCreate` or `onResume`.
- A Perfetto trace where main is busy for seconds with many medium slices and very little idle
  time between them.

## Fix 1: defer whatever is not on screen

- Wrap optional widgets (floating buttons, banners, overlays, below-the-fold sections) in a
  deferred holder that creates the real view only when `activate()` is called, after the first
  frame or when the user scrolls near it.
- Use `ViewStub` for optional layout parts. In Compose, do not compose content that is not
  visible.
- When a deferred widget is activated during a refresh, post it with a short delay so the
  looper gets a chance to handle pending input before the heavy inflation. In one app 20 ms was
  enough. Measure on your own low-end devices rather than copying the number.
- Make deferred widgets nullable and null-safe; code that assumed they exist will now see null
  for a while.

## Fix 2: show a skeleton, then fill it

A common shape: `onCreate` inflates the full layout, then `onResume` updates it again when API
results arrive, paying inflation and binding twice.

- Return a lightweight skeleton from `onCreate` and fill it when data arrives.
- Inflate the full layout asynchronously while the skeleton is shown.
- Activate independent heavy widgets in parallel off main where their setup allows it, then
  attach on main.

Observed together with Fix 1 on one home screen: ANR rate fell from 0.88 to 0.56, and home
screen load time from over 2 s to 800 to 900 ms.

## Fix 3: inflate or build off main

- `AsyncLayoutInflater` (or a small pool of prewarmed views) for heavy layouts that do not
  depend on the activity's theme in unusual ways.
- Build view data (formatted strings, spans, sorted lists) off main and hand the result to the
  view.
- In Compose, move work from composition into the ViewModel and use lazy layouts.

## Fix 4: break work into separate messages

If several independent steps must run on main, post them as separate messages instead of one
long block, so input can be handled between them. Do not use this to hide a long task; split
only work that is genuinely independent.

Also move off main the small things that add up:

- Remove `observeOn(mainThread())` from data providers that only parse; observe on main only at
  the UI edge.
- Move experiment and config lookups (prefs reads plus Gson parsing) to IO.
- Move sync work, such as shortcut updates, to IO; a coroutine bridge over an existing Rx call
  (`rxSingle.await()`) is enough.

Observed on one instrumented startup path after these moves: the measured end-to-end time went
from 3,622 ms to 1,447 ms (60%), with 61% less in `onCreate` and 28% less in `onResume`.

## Measure

- Trace sections per step: `trace("home:inflate") { ... }`.
- Macrobenchmark `StartupTimingMetric` for time to initial and full display; call
  `reportFullyDrawn()` when real content is shown.
- Watch input ANR rate on the startup screen per release, not just total ANR rate.

## Review checks

- Activities that inflate everything in `onCreate`, including optional or below-the-fold UI.
- Layouts inflated twice per launch (once empty, once with data).
- Many independent `post {}` or `runOnUiThread` calls fired back to back at startup.
- Data providers that switch to main before parsing.
