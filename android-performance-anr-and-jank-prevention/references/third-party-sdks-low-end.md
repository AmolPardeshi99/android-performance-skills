# Third-party SDKs, low-end devices, and OEM behavior

## Contents
- SDK ANRs
- An SDK upgrade process
- Low-end devices
- Device performance classes
- Animations on low-end devices
- Wasted work you cannot see
- OEM freezing and system load
- Review checks

## SDK ANRs

SDK frames at the top of a main stack usually come from one of these:

- **Synchronous init** in `Application.onCreate` or an auto-init `ContentProvider`.
- **Internal lock contention**: the SDK's main-thread API takes a lock that its own worker holds
  during I/O. Seen with a time-sync SDK.
- **Main-thread callbacks** that do I/O inside the SDK.
- **First use of a heavy engine** on main, such as maps or a WebView-based component.

Steps:

1. Check the SDK's changelog and issue tracker for the frame you see. Upgrading to a version
   with an upstream fix, behind a flag, resolved a lock-contention ANR in one app without any
   local patch.
2. If there is no fix, move init off main or defer it until the feature is used.
3. Wrap calls in trace sections so the SDK's cost is visible in your traces.
4. Remove auto-init providers you do not need with `tools:node="remove"` in the manifest.

## An SDK upgrade process

ANRs from SDKs linger when no one owns the SDK. A short written process helps:

- Name an owner for every SDK in the app.
- Read the changelog for ANR, threading, and startup changes on every upgrade.
- Ship upgrades behind a flag when the SDK runs at startup.
- Compare ANR and startup metrics for the new version against the old one during rollout.

## Low-end devices

ANR rate is usually several times higher on devices with 2 to 4 GB RAM and slow storage. The
same main-thread work takes longer, storage reads are slower, and memory pressure brings GC
pauses and process kills.

- Always profile on a real low-end device, in a release build with Baseline Profiles.
- Break down ANR clusters by RAM and device model before choosing a fix.
- Play's per-device-model threshold (8%) can be crossed on popular low-end models even when
  the overall rate looks fine.

## Device performance classes

Classify the device once at startup and use it to tune behavior:

- `androidx.core:core-performance` exposes a media performance class on newer devices; combine
  it with `ActivityManager.isLowRamDevice()`, total RAM, and core count for older ones.
- Use the class to size caches (an HTTP cache size per device class was one first use), reduce
  prefetching, lower image quality, and turn off decorative animation.
- Cache the result; do not recompute it on main.

## Animations on low-end devices

Looping decorative animations (Lottie, animated vectors) cost main-thread and RenderThread time
every frame. On low-end devices they can leave no room for input.

- Offer a low-end mode that shows the final frame instead of playing.
- To apply it across many modules without touching each call site, one team used a Gradle
  plugin with AGP's bytecode instrumentation API (`AsmClassVisitorFactory`) to rewrite calls to
  `LottieAnimationView.playAnimation()` so the view jumps to the final frame on low-end
  devices. It was applied through a shared convention plugin and controlled by remote flags.
- First check whether the animation is used at all. A home bar component turned out to have
  never displayed anything but a static image; replacing `LottieAnimationView` with an
  `ImageView` removed all animation setup.

## Wasted work you cannot see

Work that does nothing useful but still runs on hot paths:

- Telemetry events built and serialized on every image request although sampling had been set
  to 0 months earlier, at 1 to 5 ms each, hundreds of times a session. Fix: check the flag
  before creating the event, and do not initialize the tracker when it is off.
- Debug logging that formats strings even when the log level is off.
- Analytics SDK calls on main for events no one reads.

## OEM freezing and system load

Some OEM builds freeze background apps to save power. If an event arrives while the app is
frozen, the system can raise an ANR even though the app did nothing wrong.

- Signs: log lines about freezing or unfreezing your uid near the ANR time, often with an
  unfreeze only after the ANR.
- Treat these as `EXTERNAL`, tag them in your dashboard, and keep `onStart` and `onResume`
  light so the app responds as soon as it is unfrozen.
- Very high system_server CPU, load far above core count, or many apps ANR at once also point
  to `EXTERNAL`.

## Review checks

- SDK init in `Application.onCreate` or providers without a reason to be synchronous.
- SDK calls on main inside lifecycle callbacks or bind methods.
- Decorative looping animations with no low-end switch.
- Telemetry or logging that builds payloads before checking whether it is enabled.
- Caches and prefetch sizes that ignore device class.
