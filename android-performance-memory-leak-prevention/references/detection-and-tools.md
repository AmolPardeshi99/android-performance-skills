# Detection and tools

## Contents
- LeakCanary in debug builds
- Leak checks in UI tests
- Keeping detection on
- dumpsys meminfo
- Heap dumps from the command line
- Perfetto heap profiling
- OOMs and low-memory kills in production

## LeakCanary in debug builds

```kotlin
// app/build.gradle.kts
dependencies {
    debugImplementation("com.squareup.leakcanary:leakcanary-android:2.14")
}
```

No init code is needed. Watch objects beyond the built-in watchers (Activities, Fragments,
Fragment views, ViewModels, Services, root views):

```kotlin
AppWatcher.objectWatcher.expectWeaklyReachable(presenter, "Presenter should be gone after detach")
```

## Leak checks in UI tests

```kotlin
// androidTestImplementation("com.squareup.leakcanary:leakcanary-android-instrumentation:2.14")
class CheckoutFlowTest {
    @get:Rule val rules: RuleChain = RuleChain.outerRule(DetectLeaksAfterTestSuccess())
        .around(ActivityScenarioRule(MainActivity::class.java))

    @Test fun completeCheckout() { /* drive the flow */ }
}
```

The test fails if a leak is found after it passes, so leaks in core flows block the merge.

## Keeping detection on

Leak detection tends to get switched off when it is noisy, and then leaks pile up unseen.

- Keep LeakCanary in every debug and internal build.
- Send leak reports to a shared place (an `EventListener` can upload analysis results), grouped
  by signature, with an owner per feature area.
- Run leak-checking UI tests on core flows (login, home, checkout, account) in CI.
- Treat a new signature in a core flow like a failing test.

## dumpsys meminfo

```bash
adb shell dumpsys meminfo <package>
```

After opening and closing a screen a few times and forcing GC, `Activities` should drop back to
the number actually open, and `Views` should not keep growing. `TOTAL PSS` trending up across
repeated journeys points to a leak or waste.

## Heap dumps from the command line

Run `scripts/capture_heap_dump.sh <package>` to capture and pull an HPROF. The script uses
`am dumpheap`, which needs a debuggable build. Open the result in Android Studio, or analyze it
with `shark-cli --hprof <file> analyze`. Convert with `hprof-conv` only for non-Android tools
such as Eclipse MAT.

## Perfetto heap profiling

- `heapprofd` samples native allocations with call stacks on profileable or debuggable apps.
- The Java heap graph data source (`android.java_hprof`) captures Java heap dumps into a trace.
- Open the trace at https://ui.perfetto.dev and use the heap graph flamegraph to see what
  retains the most memory.

## OOMs and low-memory kills in production

`ApplicationExitInfo` (API 30+) reports why the last process died.

```kotlin
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
    val am = getSystemService(ActivityManager::class.java)
    am.getHistoricalProcessExitReasons(packageName, 0, 10).forEach { info ->
        when (info.reason) {
            ApplicationExitInfo.REASON_LOW_MEMORY -> reporter.lowMemoryKill(info.timestamp, info.pss)
            ApplicationExitInfo.REASON_CRASH ->
                if (info.description?.contains("OutOfMemoryError") == true) reporter.oom(info.timestamp)
        }
    }
}
```

`REASON_LOW_MEMORY` is the system killing the process under memory pressure, not a Java OOM.
Java OOMs arrive as crashes; your crash reporter sees them directly. Track both per release.
