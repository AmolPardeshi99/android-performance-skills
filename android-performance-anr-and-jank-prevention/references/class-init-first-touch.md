# First-touch costs

## Contents
- What a first-touch cost is
- Large enum classes
- ICU locale data: SimpleDateFormat, DecimalFormat, String.format
- Reflection during layout inflation
- Typeface and font loading
- WebView first use
- Prewarming correctly
- Review checks

## What a first-touch cost is

Some work happens once per process, the first time something is used: loading and verifying a
class, running its static initializer, loading locale data, creating a font, starting a
browser engine. The cost is invisible in code review because the call looks cheap, and
invisible in warm-start benchmarks because it already happened. It lands on whichever thread
touches it first, often main during startup or the first tap on a screen.

Signs in a trace: `<clinit>`, `ClassLinker::InitializeClass`, `VerifyClass`, `Class.forName`,
`LocaleData`, `ICU`, `Typeface.create*`, `nativeCreateFromArray`, `WebViewChromiumFactoryProvider`.
A Baseline Profile reduces class load and verify cost but does not remove static initializer
work.

## Large enum classes

An enum's static initializer creates every constant and the `values()` array. Design-system
enums for icons and typography styles can have more than a thousand constants, each holding
resource ids, strings, or nested objects.

- Observed: a typography style enum with over a thousand entries cost 1 to 2 s of main-thread
  blocking on first use; an icon enum of similar size cost 400 ms to 1 s during the home
  screen's `onCreate`.
- Fix used: start a background thread from an early `ContentProvider.onCreate` (or the
  `Application`) that touches the enum, so main later finds the class already initialized. No
  call-site changes are needed.
- Better long-term: replace giant enums with sealed interfaces, generated `object`s, or plain
  `Int` resource ids, so only the entries used are loaded.

## ICU locale data

`SimpleDateFormat`, `DateFormat.getDateInstance`, `DecimalFormat`, `NumberFormat`,
`String.format` with a locale, and `Calendar.getInstance` load ICU locale data the first time a
locale is used (`LocaleData.initLocaleData`). On low-end devices that can take tens to hundreds
of milliseconds.

- Observed: a date-format helper creating `SimpleDateFormat` on main during the home tab's
  refresh appeared repeatedly at the top of ANR stacks.
- Fix used: create one `SimpleDateFormat` with the app's default locale on a background thread
  early in startup, so the native ICU cache is filled before main needs it. Rolled out behind a
  remote flag.
- Better: use `java.time.format.DateTimeFormatter` (with core library desugaring on older API
  levels), create formatters once and reuse them, and never create formatters inside
  `onBindViewHolder` or a composable body.

## Reflection during layout inflation

`LayoutInflater` creates custom views by reflection: it looks up the class, finds the
two-argument constructor, and caches it. The first inflation of each custom class pays class
loading plus reflection lookup. A home screen with dozens of custom widgets pays it dozens of
times in one frame.

- Observed: prewarming the custom view classes behind the heaviest layouts cut about 1 s of
  layout inflation in a single launch, measured on the home screen's `onResume`.
- Fix options:
  - Load the classes off main early (`Class.forName(name, true, loader)` for each), so main only
    pays the cheap cached lookup.
  - Use a `LayoutInflater.Factory2` that creates known custom views with `new` instead of
    reflection.
  - Inflate the heavy layout asynchronously. See [startup-input-gaps.md](startup-input-gaps.md).
  - Move to Compose, which has no reflective inflation.

## Typeface and font loading

`Typeface.createFromAsset` and `ResourcesCompat.getFont` read and parse font files. A text
component that loads its font and reapplies its style on every inflation multiplies that cost
across every screen.

- Observed: caching `Typeface` instances in a design-system text view and skipping redundant
  `setStyle` calls during init made median inflation about 18% faster with 17.5% fewer
  allocations per inflation, measured on a low-end Android 11 device with 3 GB RAM.
- Fix: cache typefaces in an app-scoped map keyed by font, apply style once, and benchmark the
  component with Microbenchmark before and after.

## WebView first use

The first `WebView` creation in a process loads and starts the Chromium engine, which can take
hundreds of milliseconds and must happen on main.

- Fix: create and discard (or keep) a `WebView` during an idle moment after first frame, using
  `Looper.myQueue().addIdleHandler { ... false }`, so the first real screen with a WebView does
  not pay it during a tap. Do this only if a large share of sessions open a WebView.
- If WebView memory is a problem, host it in its own process. See the memory-leak skill.

## Prewarming correctly

- **Start early, finish early.** Prewarming helps only if it finishes before main touches the
  same class. If main touches it while a worker is still running the static initializer, main
  blocks on the class init lock and you gain nothing.
- **Touch only what is needed.** Warming everything moves the cost to a different thread but
  still competes for CPU during startup, especially on 4-core devices.
- **Gate it.** Put prewarming behind a remote flag and compare cold start and ANR rate for both
  groups.
- **Do not prewarm on main.** An idle handler on main is fine for work that must run on main
  (WebView); for everything else use a background thread.

## Review checks

- Enums with hundreds of entries or heavy constructors referenced from startup paths.
- `SimpleDateFormat`, `DecimalFormat`, `NumberFormat`, `String.format(Locale, ...)` created in
  bind methods, composables, getters, or on first screen load.
- Custom views inflated many times per screen with no async inflation or prewarm.
- `Typeface.createFromAsset` or `getFont` called per view instance.
- First `WebView` constructed in response to a tap.
