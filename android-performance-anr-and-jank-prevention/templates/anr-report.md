# ANR report template

Fill every section. Write "unknown" rather than guessing.

```markdown
## Verdict
<APP_DEFECT | APP_OVERLOAD | EXTERNAL> — <one sentence: what blocked main, for how long, on which path>

## Evidence
- ANR type and reason line: `<quote>`
- Process state: <cold start for this event? yes/no/unknown>
- Main thread: state `<state>`, first app/SDK frame `<frame>`
- Lock chain (if any): main waits on <lock> held by <thread>, which is <doing what>
- System: load <x/y/z> on <n> cores, system_server CPU <n>%, OEM freeze lines <yes/no>
- Second signal: <cluster share, Perfetto slice, StrictMode, repro> (or "none yet")

## Pattern
<pattern name> — see <reference file>

## Fix
<change, in the user's framework, with code>
- Behind flag: <name and safe default>
- Risk: <what could break>

## How we will know it worked
- Metric: <ANR rate for this cluster, startup time, trace section duration>
- Expected change: <direction and rough size>
- Where to watch: <Vitals cluster, dashboard, trace>

## Open questions
- <anything that needs more data>
```
