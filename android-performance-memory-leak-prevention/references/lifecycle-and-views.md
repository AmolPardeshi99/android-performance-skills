# Lifecycle and views

## Contents
- Fragment view lifetime
- Observing in Fragments
- ViewModels holding UI
- Presenters holding their view
- Custom views that register with long-lived objects
- Activity result launchers
- by lazy capturing the Fragment

Framework code: [../examples/views.md](../examples/views.md),
[../examples/compose.md](../examples/compose.md).

## Fragment view lifetime

A Fragment on the back stack outlives its View. Anything the Fragment holds that points into
the View tree keeps the destroyed tree alive.

- Clear the binding in `onDestroyView`. The `_binding` / `binding` pattern, or a property
  delegate that clears on the view lifecycle's `ON_DESTROY`.
- Clear adapters set on `RecyclerView`s (`recyclerView.adapter = null`) if the adapter is a
  Fragment field and holds view references.
- Anything created in `onViewCreated` is released in `onDestroyView`, not `onDestroy`.

## Observing in Fragments

- `LiveData.observe(viewLifecycleOwner)`, not `observe(this)`.
- Collect flows with `viewLifecycleOwner.repeatOnLifecycle(STARTED)` or
  `flowWithLifecycle`; a bare `lifecycleScope.launch { collect }` keeps collecting into a dead
  view.

## ViewModels holding UI

A ViewModel outlives configuration changes. It must not hold an Activity, Fragment, View,
Binding, Activity Context, or composable lambda. Expose state with `StateFlow` and let the UI
observe it. `@ApplicationContext` is fine.

Callbacks registered from a ViewModel into a singleton must be removed in `onCleared()`.

## Presenters holding their view

MVP presenters often get the view (an Activity or Fragment) in `attach(view)` and are kept in a
retained scope or a DI component. If `detach()` is not called in the matching lifecycle
callback, or the presenter lives in a wider scope than the view, the view leaks.

- Call `detach()` in `onDestroy` (or `onDestroyView` for Fragments) and null the reference.
- Do not scope presenters wider than the screen. See [di-scopes.md](di-scopes.md).

## Custom views that register with long-lived objects

A header or banner view that subscribes to an app-wide manager (session, config, a carousel
timer) from its constructor or `onAttachedToWindow` leaks its Activity if it never
unsubscribes.

- Register in `onAttachedToWindow`, unregister in `onDetachedFromWindow`.
- Cancel animators and stop any timers there too.
- Prefer passing data into the view over letting the view reach out to singletons.

## Activity result launchers

Register `registerForActivityResult` as a field initializer or in `onCreate`, never in
`onViewCreated` or a click handler. Registering repeatedly stacks callbacks that capture the
Fragment.

## by lazy capturing the Fragment

`private val helper by lazy { Helper(this) }` captures the Fragment. That is fine if `Helper`
lives no longer than the Fragment. It leaks if `Helper` hands `this` to anything app-scoped.
Pass `requireContext().applicationContext` or create the helper in `onViewCreated` and clear it
in `onDestroyView`.
