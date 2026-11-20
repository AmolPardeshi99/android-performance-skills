---
type: llm
focus: trace
weight: 1
---

The response flags the fixed thread pool created per ViewModel and never shut down (no shutdown in onCleared), so each screen open leaves 12 idle threads alive, and recommends shutting it down in onCleared or using a shared dispatcher or executor.
