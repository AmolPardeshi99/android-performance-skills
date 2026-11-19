# Review report template

```markdown
**ANR and jank risk: <none found | LOW | MEDIUM | HIGH | CRITICAL>** (highest severity found)

## Findings

### <SEVERITY> <ID> <short title> — `<file>:<line range>`
- Thread: <main | binder | ...>, via <call chain you verified>
- Why it is slow or blocks: <concrete reason; first-touch? I/O? lock?>
- Fix:
  ```kotlin
  <code in the project's framework>
  ```
- Reference: <reference file>

(repeat, most severe first)

## Dismissed candidates
- `<file>:<line>` <what it looked like> — <reason: thread not established | suspends, does not block | in-memory read | under a frame, one-off | owned by caller>

## Not covered
- <files or areas not reviewed, and why>
```
