# Rendering and jank

## Contents
- Frame budget
- View hierarchy depth
- RecyclerView
- onDraw and custom views
- Bitmaps and RenderThread
- Compose
- Measuring frames

Framework code: [../examples/views.md](../examples/views.md),
[../examples/compose.md](../examples/compose.md).

## Frame budget

At 60 Hz a frame has about 16 ms, at 90 Hz 11 ms, at 120 Hz 8 ms. Frames over 700 ms count as
frozen in Android Vitals. Jank and ANRs share causes: a 5 s input ANR is many missed frames in
a row.

## View hierarchy depth

Deep or wide hierarchies cost measure and layout on every pass, and inflation cost once.

- Replace nested `LinearLayout` and `FrameLayout` with one `ConstraintLayout` where it flattens
  the tree.
- Use `<merge>` as the root of layouts that are always included into a parent of the same type.
- Remove views that are never visible, and the code that drives them.
- Check with Layout Inspector or `adb shell dumpsys activity top`.

## RecyclerView

- `onBindViewHolder` only assigns precomputed values. No filtering, parsing, formatting with new
  `SimpleDateFormat` objects, or I/O.
- Use `ListAdapter` or `AsyncListDiffer` so diffing runs off main.
- Set stable ids or use DiffUtil item ids.
- Use `setHasFixedSize(true)` when item changes do not change the list size.
- Share a `RecycledViewPool` across nested lists of the same type.

## onDraw and custom views

- No allocations in `onDraw`: create `Paint`, `Path`, and `RectF` once and reuse them.
- Do not call `requestLayout()` from `onDraw` or `onLayout`.
- Cache `Typeface` objects instead of loading them per instance. See
  [class-init-first-touch.md](class-init-first-touch.md).

## Bitmaps and RenderThread

The main thread hands each frame to RenderThread in `syncAndDrawFrame`. If RenderThread is still
busy (huge bitmap uploads, shader compilation, complex paths), main waits there.

- Decode bitmaps off main and downsample to the view's size. Prefer Coil or Glide.
- Avoid very large bitmaps in `ImageView`s that show them small.
- Signature in traces: main in `nSyncAndDrawFrame`, RenderThread busy in `Upload` or
  `shader_compile`.

## Compose

The most common Compose causes of main-thread time:

- Heavy work in the composable body instead of `remember(key)` or the ViewModel.
- Reading fast-changing state (scroll, animation) high in the tree; read it in a lambda
  modifier or behind `derivedStateOf`.
- Unstable parameters that stop skipping; check compiler reports.
- Missing `key` in lazy lists.
- Side effects in composition instead of `LaunchedEffect` or `DisposableEffect`.

Code for all of these is in [../examples/compose.md](../examples/compose.md). For deeper Compose
work, Google's `jetpack-compose-performance` skill covers recomposition in more detail.

## Measuring frames

- Macrobenchmark `FrameTimingMetric` for scroll and animation journeys in CI.
- `JankStats` (androidx.metrics) in production to log janky frames with UI state.
- Perfetto: `Choreographer#doFrame` slices on main, `DrawFrame` on RenderThread. See
  [perfetto.md](perfetto.md).
