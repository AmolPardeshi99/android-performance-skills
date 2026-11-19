# Leak report template

```markdown
## Verdict
<Leak | Memory waste | Not a leak> — <object> is retained by <holder> after <lifecycle event>, about <size> per occurrence

## Evidence
- Source: <LeakCanary trace | HPROF | meminfo | OOM>
- GC root: <root>
- Last `Leaking: NO`: <object>
- First `Leaking: YES`: <object> (<reason>)
- Reference to break: `<Class.field>`

## Pattern
<pattern name> — see <reference file>

## Fix
<change at the owner of the reference, in the project's framework, with code>

## Verify
- Repeat <journey> <n> times, force GC
- Expect: LeakCanary quiet; `dumpsys meminfo` Activities back to <n>
```
