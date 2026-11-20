---
tags: [android-performance-anr-and-jank-prevention]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

QA got this ANR on a test phone while switching back to our app. The main thread is in our
MainActivity, so I guess we need to fix something there? What should we change?

Input files: anr_resume_trace.txt, logcat_around_anr.txt
