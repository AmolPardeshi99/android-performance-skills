---
name: android-performance-anr-and-jank-prevention
description: >
  Diagnoses Android ANRs and jank from traces, and reviews Android code for main-thread
  blocking. Use when the user shares an ANR trace, a Play Console or Crashlytics ANR cluster,
  a bugreport, or a Perfetto trace and asks why the app froze; or asks for a performance-focused
  review of Kotlin or Java code (Activities, Fragments, Compose, receivers, services, DI modules,
  startup code, SDK initialization). Covers main-thread I/O, DI graph cost, first-touch class
  init (large enums, ICU/SimpleDateFormat, reflection), BroadcastReceiver and process isolation,
  startup that leaves no gap for input, third-party SDK and low-end device ANRs, and catching
  regressions per release. Use it even when the user only says the app freezes, hangs, is
  slow to start, drops frames, or asks whether something is safe on the main thread. Not for
  memory leaks or OOMs (use the memory-leak skill).
license: Apache-2.0
metadata:
  version: "2.0.0"
  keywords: "ANR, jank, frozen frames, main thread, startup, Perfetto, StrictMode, code review"
---

# ANR and jank: triage and review

Two tasks. Pick one before doing anything else.

| The user gives you | Task |
|---|---|
| An ANR trace, `anr_*` file, bugreport, Vitals or Crashlytics cluster, Perfetto trace, "why did this freeze" | **A. Triage** |
| Source files, a diff or PR, "review this for performance", "is this safe on the main thread" | **B. Review** |
| Both (a trace and the code it points at) | A, then B on the files the trace names |

If it is unclear, ask one question: "Do you want me to diagnose a specific ANR, or review code?"

Read a reference file only when a step below sends you there. Each one has a table of contents.

## A. Triage an ANR or trace

Copy this checklist into your reply and tick it off as you go.

```
- [ ] 1. Classify the ANR type and timeout
- [ ] 2. Read the main thread state
- [ ] 3. Decide: app defect, app overload, or external
- [ ] 4. Match to a pattern
- [ ] 5. Confirm with a second signal
- [ ] 6. Fix and guard
```

1. **Classify.** Find the reason line (`Input dispatching timed out`, `Broadcast of Intent`,
   `executing service`, `No response to onStartJob`, `Context.startForegroundService() did not
   then call Service.startForeground()`). Note whether the process was cold started for this
   event. See [references/anr-mechanics.md](references/anr-mechanics.md).
2. **Main thread.** Read the `"main"` stack top-down: state (`Runnable`, `Blocked`, `Native`,
   `Waiting`), the first app frame, any `waiting to lock ... held by thread N`. Follow lock
   owners. See [references/trace-reading.md](references/trace-reading.md).
3. **Attribute.** Use the app-vs-system table in trace-reading.md. Label the finding
   `APP_DEFECT`, `APP_OVERLOAD` (many small tasks, no single culprit), or `EXTERNAL`
   (OEM freeze, system_server load, another process). Propose code fixes only for the first two.
4. **Match a pattern.** Use the signature index below, then read that one reference.
5. **Confirm.** A single stack is a sample, not proof. Look for a second signal: the same top
   frame across a cluster, a Perfetto slice, StrictMode output, or a reproduction. For traces,
   use [references/perfetto.md](references/perfetto.md) and run the queries in
   `scripts/perfetto/` (`scripts/perfetto/run_queries.sh <trace>`) instead of reading them.
6. **Fix and guard.** Give the fix in the user's framework (see "Framework samples"), behind a
   remote flag when it changes startup order, and name the metric that proves it worked. See
   [references/release-watch.md](references/release-watch.md).

Write the result with [templates/anr-report.md](templates/anr-report.md).

### Signature index

| Top of main stack or trace shows | Likely pattern | Read |
|---|---|---|
| `SharedPreferencesImpl.awaitLoadedLocked`, `QueuedWork.waitToFinish`, `FileInputStream`, `SQLiteConnection`, `Gson.fromJson` / `JSONObject` | Main-thread I/O or parsing | [main-thread-io.md](references/main-thread-io.md) |
| `Dagger*Component.inject`, `*_Factory.get`, `DoubleCheck.get`, Koin `get`/`inject`, `Hilt_*Activity.onCreate` | DI graph cost | [di-graph-cost.md](references/di-graph-cost.md) |
| `<clinit>`, `Class.forName`, `EnumEntries`, a huge enum's `values()`, `LocaleData`, `SimpleDateFormat.<init>`, `DecimalFormatSymbols`, `Constructor.newInstance` under `LayoutInflater.createView`, `Typeface.createFromAsset` | First-touch cost | [class-init-first-touch.md](references/class-init-first-touch.md) |
| `Broadcast of Intent`, `onReceive` in the stack, push SDK frames, `bindApplication` during a receiver ANR | Receiver and process | [receivers-and-processes.md](references/receivers-and-processes.md) |
| Input ANR with many short tasks and no single culprit; `inflate`, `onCreate`/`onResume` back to back | No gap for input | [startup-input-gaps.md](references/startup-input-gaps.md) |
| Frames from an SDK package; ANRs concentrated on low-RAM devices or one OEM | SDK or device | [third-party-sdks-low-end.md](references/third-party-sdks-low-end.md) |
| `BinderProxy.transact`, `waiting to lock`, `Object.wait`, `runBlocking`, `CountDownLatch.await` | Threading and locks | [threading-and-locks.md](references/threading-and-locks.md) |
| `nSyncAndDrawFrame`, `Choreographer.doFrame`, long `RV OnBindView`, `Recomposer` | Rendering | [rendering-jank.md](references/rendering-jank.md) |

## B. Review code for performance

Copy this checklist and tick it off.

```
- [ ] 1. List candidates
- [ ] 2. Prove the executing thread
- [ ] 3. Prove it is slow or blocks
- [ ] 4. Grade with the checklist
- [ ] 5. Report findings and dismissed candidates
```

1. **List candidates** in the files under review using the "Look for" column in
   [checklists/review-checklist.md](checklists/review-checklist.md). Scan every file; do not
   stop at the first hit.
2. **Prove the thread.** For each candidate, show which thread runs it: lifecycle callbacks,
   `onReceive`, `onBindViewHolder` and composable bodies are main; `lifecycleScope` and
   `viewModelScope` default to `Dispatchers.Main`; after `observeOn(mainThread())` is main.
   When it depends on the caller, follow callers one or two hops and state the chain. If you
   cannot establish the thread, dismiss it as "thread not established".
3. **Prove the cost.** Suspension is not blocking. `StateFlow.value` and seeded in-memory reads
   return immediately. A one-off cost under a frame is not a finding. First-touch costs (class
   init, ICU, reflection, Typeface) count only on the first call, so check whether this is the
   first call on a startup or input path.
4. **Grade** each surviving finding with the severity rules in the checklist. Read the linked
   reference before you write the fix, and give the fix in the user's framework.
5. **Report** with [templates/review-report.md](templates/review-report.md): verdict line,
   findings by severity with file and line, then dismissed candidates with a one-line reason.

## Framework samples

Detect the stack from imports and build files, then load only the matching sample file.

| Area | Option 1 | Option 2 |
|---|---|---|
| UI | [examples/views.md](examples/views.md) (XML, RecyclerView, custom Views) | [examples/compose.md](examples/compose.md) |
| DI | [examples/dagger-hilt.md](examples/dagger-hilt.md) | [examples/koin.md](examples/koin.md) |
| Async | [examples/coroutines-flow.md](examples/coroutines-flow.md) | [examples/rxjava.md](examples/rxjava.md) |

For deep Compose recomposition work, Google's `jetpack-compose-performance` skill goes further.
For recording traces, Google's `android-profiler` skill covers Perfetto configs. Recommend them
if the user has them; this skill does not depend on them.

## Topic index

- [references/anr-mechanics.md](references/anr-mechanics.md): ANR types, timeouts, version changes
- [references/trace-reading.md](references/trace-reading.md): thread states, CPU block, app vs system
- [references/perfetto.md](references/perfetto.md): what to look for in a trace, query guide
- [references/main-thread-io.md](references/main-thread-io.md): prefs, files, DB, parsing, static config
- [references/threading-and-locks.md](references/threading-and-locks.md): dispatchers, locks, Binder, thread pools
- [references/di-graph-cost.md](references/di-graph-cost.md): the DI graph as a hidden call graph
- [references/class-init-first-touch.md](references/class-init-first-touch.md): enums, ICU, reflection, fonts, WebView
- [references/receivers-and-processes.md](references/receivers-and-processes.md): receivers, services, jobs, push in its own process
- [references/startup-input-gaps.md](references/startup-input-gaps.md): leaving room for input during startup
- [references/third-party-sdks-low-end.md](references/third-party-sdks-low-end.md): SDKs, low-end devices, OEM behavior
- [references/rendering-jank.md](references/rendering-jank.md): frames, layout depth, animations
- [references/release-watch.md](references/release-watch.md): instrumentation, flags, catching regressions

## Rules that apply to both tasks

- Base every claim on evidence in the trace or code, and say "likely" when inferring. ANR
  stacks are taken after the timeout, so the top frame can be a bystander.
- Do not suggest `runBlocking`, `Thread.sleep`, or a main-thread lock as a fix: each one
  makes main wait, which is the problem being fixed.
- Moving work off main is not enough if main then waits for it (`get()`, `await` inside
  `runBlocking`, a latch). Check for the wait.
- Prefer removing work over moving it: dead telemetry, never-used animations, and runtime
  parsing of static data should be deleted, not backgrounded.
- Prewarming only helps if it finishes before main needs the result. If main touches the class
  while a background thread is still initializing it, main blocks on the class init lock.
- Put startup-order changes behind a remote flag whose default is the safe path, and say which
  metric to watch.
