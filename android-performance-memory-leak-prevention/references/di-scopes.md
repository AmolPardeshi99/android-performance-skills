# DI scopes

## Contents
- The rule
- Components that retain an Activity
- Hilt scopes
- Koin scopes
- Review checks

Framework code: [../examples/dagger-hilt.md](../examples/dagger-hilt.md),
[../examples/koin.md](../examples/koin.md).

## The rule

An object may depend only on objects with the same or a longer lifetime. A `@Singleton` that
holds anything Activity-scoped (an Activity, its Context, a presenter bound to it, a View)
leaks that Activity for the life of the process.

## Components that retain an Activity

Plain Dagger makes it easy to build a component with the Activity as a bound instance
(`@BindsInstance activity: Activity`) and then store the component somewhere longer-lived: an
`object`, the Application, or a feature singleton "so we do not rebuild it". Everything in that
component, including the Activity, then lives forever.

- Build Activity-bound components in the Activity and keep them only in the Activity.
- If something must be reused across screens, move it to a parent component that does not take
  the Activity.
- Do not cache subcomponents in app-scoped fields.

Observed: in one large app, one of the top leak signatures ran through a sign-in DI component
that kept its screen alive after the user left it.

## Hilt scopes

| Scope | Lives as long as | May hold |
|---|---|---|
| `@Singleton` | Application | `@ApplicationContext`, other singletons |
| `@ActivityRetainedScoped` | Across config changes | Not the Activity |
| `@ViewModelScoped` | The ViewModel | Not the Activity |
| `@ActivityScoped` | One Activity instance | `@ActivityContext`, the Activity |
| `@FragmentScoped` | One Fragment | The Fragment, but not its View after `onDestroyView` |

Hilt checks component hierarchy at compile time but not what your classes store in fields.

## Koin scopes

- `single {}` is app-wide. Do not inject an Activity or its Context into it.
- Use `scope<HomeActivity> { scoped { ... } }` with `activityScope()` or `fragmentScope()` so
  the scope closes with the owner.
- `factory {}` creates a new instance each time and is safe for screen-level helpers.

## Review checks

- `@Singleton` or `single {}` classes with an Activity, Fragment, View, or Activity Context in
  their constructor.
- Components or subcomponents stored in `object`s, companion fields, or the Application.
- Presenters or controllers scoped wider than the screen they control.
