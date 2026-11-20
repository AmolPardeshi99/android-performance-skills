---
type: llm
focus: trace
weight: 1
---

If the response suggests prewarming IconStyle (or the registry) on a background thread, it also warns that this only helps if the prewarm finishes first, because main blocks on the class initialization lock when it touches a class another thread is still initializing. A response that does not suggest prewarming passes.
