# Review report template

```markdown
**Leak risk: <none found | LOW | MEDIUM | HIGH | CRITICAL>** (highest severity found)

## Findings

### <SEVERITY> <ID> <short title> — `<file>:<line range>`
- Holder: <what holds it and how long it lives>
- Held: <what it retains and how big that is>
- Missing cleanup: <which lifecycle callback should release it>
- Fix:
  ```kotlin
  <code in the project's framework>
  ```
- Reference: <reference file>

## Dismissed candidates
- `<file>:<line>` <what it looked like> — <reason: same lifetime | removed in X | applicationContext | bounded and short>

## Not covered
- <files or areas not reviewed>
```
