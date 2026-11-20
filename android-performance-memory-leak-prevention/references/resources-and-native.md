# Resources and native memory

## Contents
- Closeables
- TypedArray
- Bitmaps and caches
- MediaPlayer and camera
- WebView
- Services that never stop

## Closeables

Streams, readers, `Cursor`, `ParcelFileDescriptor`, and database handles must be closed on every
path, including exceptions. Use `use {}`. StrictMode `detectLeakedClosableObjects()` and
`detectLeakedSqlLiteObjects()` catch the ones you miss.

## TypedArray

`obtainStyledAttributes()` returns a pooled `TypedArray`. Call `recycle()` in `finally`, or use
`androidx.core.content.res.use {}`. Forgetting it is a lint warning and wastes pooled objects;
it is not usually a large leak, but it is cheap to get right.

## Bitmaps and caches

- Never keep Bitmaps in a static `HashMap`. Use an `LruCache` sized from
  `Runtime.getRuntime().maxMemory()` with `sizeOf` returning bytes or KB.
- Prefer Coil or Glide, which pool bitmaps and bind requests to a lifecycle.
- Decode at the size you display. A full-resolution photo in a thumbnail wastes many MB.
- `Bitmap.recycle()` is rarely needed on API 26+ where pixel data is managed by the runtime;
  clear references instead.

## MediaPlayer and camera

Release `MediaPlayer`, `ExoPlayer`, `CameraDevice`, and `AudioRecord` in the teardown that
matches where you created them, and null the field.

## WebView

WebView holds native memory and can retain its Activity through callbacks.

- On teardown: remove it from its parent, `stopLoading()`, `removeAllViews()`, then `destroy()`.
- Do not hold WebViews in static pools tied to an Activity Context.
- If WebView memory affects the main process, host the WebView screen in its own process with
  `android:process` on the Activity. Weigh the cost: a second process takes extra memory and
  start time, and shared state must cross process boundaries.

## Services that never stop

A running service keeps the process at a higher priority, so the system is less likely to
reclaim its memory. Call `stopSelf(startId)` when work finishes, avoid `START_STICKY` for
one-off work, and prefer WorkManager.
