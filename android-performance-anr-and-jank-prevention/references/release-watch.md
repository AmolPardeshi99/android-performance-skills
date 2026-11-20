# Catching regressions: release watch

## Contents
- Know your ANRs before a release ships
- Capture ANRs in the field
- Instrument hotspots
- Watch each release
- Roll out fixes safely
- Guardrails in development and CI

## Know your ANRs before a release ships

Fixes do not stay fixed. A new SDK version, a new widget on the home screen, or a new injected
field brings an ANR back a few releases later. Treat ANR rate like a test that must keep
passing.

## Capture ANRs in the field

- **Play Console and Android Vitals** give rates and clusters by version, device, and OS.
- **`ApplicationExitInfo`** (API 30+): on next launch, read `REASON_ANR` exits and upload
  `traceInputStream` with the description, timestamp, and process importance. This gives full
  thread dumps, not just the main stack.
- **Breadcrumbs.** Record what the app was doing (current screen, startup phase, last few
  messages handled) so a trace can be tied to a user journey. Some teams also intercept the
  ANR signal in native code to capture extra context at the moment of the ANR. If you ship a
  native library for this, build it for 16 KB page sizes.

```kotlin
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
    val am = getSystemService(ActivityManager::class.java)
    am.getHistoricalProcessExitReasons(packageName, 0, 5)
        .filter { it.reason == ApplicationExitInfo.REASON_ANR }
        .forEach { info ->
            val trace = info.traceInputStream?.use { it.readBytes() }
            reporter.uploadAnr(trace, info.timestamp, info.description, info.importance)
        }
}
```

Run this off main, and remember which timestamps you already uploaded.

## Instrument hotspots

- Add production traces (Firebase Performance custom traces or your own timers) to the top
  blocking methods found in analysis, so you can watch them per release instead of rediscovering
  them from ANR clusters.
- Keep the list short: the methods that appeared at the top of the main stack most often.

## Watch each release

A release-watch routine, whether a person, a dashboard, or an agent, should check for each new
version as it rolls out:

1. ANR rate and user-perceived ANR rate against the previous version, at the same rollout stage.
2. New clusters, and clusters whose share grew.
3. The startup screen's input ANR rate and cold start time.
4. The instrumented hotspot timings.
5. Per device class: a regression may only show on low-end devices.

If something regresses, check what changed in the release for that area: new SDK versions, new
injected fields, new startup initializers, and flags that were turned on.

## Roll out fixes safely

- Put any change to startup order, deferral, prewarming, or threading behind a remote flag.
- Make the safe path the default when the flag has not loaded.
- Compare both groups for ANR rate, crash rate, and startup time before going to 100%.
- Once proven, remove the flag and the old path. A forgotten flag that defaults to the slow path
  silently undoes the fix (see [main-thread-io.md](main-thread-io.md)).

## Guardrails in development and CI

- StrictMode thread policy in debug builds: `detectDiskReads`, `detectDiskWrites`,
  `detectNetwork`, `detectCustomSlowCalls`; `penaltyDeath()` in CI runs.
- Macrobenchmark with `StartupTimingMetric` and `FrameTimingMetric` on a low-end device, with
  thresholds that fail the build.
- Microbenchmark for hot components (design-system views, formatters, parsers).
- A lint or review rule for the patterns in
  [../checklists/review-checklist.md](../checklists/review-checklist.md).
