# Trigger evals

Each file holds 20 realistic requests for one skill: about half should trigger it and half
should not. The should-not-trigger items are near misses: they share keywords with the skill
but need something else (the other skill in this repo, a profiler skill, a build tool, another
platform).

Use them to check and tune each skill's `description`, which is what an agent reads to decide
whether to load the skill.

## Check

```bash
python3 tools/trigger-evals/check_triggers.py tools/trigger-evals/<file>.json <skill-name>
```

This installs both skills in a scratch project, runs each query through `claude -p`, and
reports which skills loaded. Your other installed skills stay visible, so it measures real
competition (for example with Google's `android-profiler`). Each query is a billed run.

Agents answer many short questions from their own knowledge without loading any skill, so
expect some misses on one-line questions. Do not count a miss as a failure until it repeats.
Check a changed description against a few new queries too, not only these, so it does not
overfit this list.

## Tune

With Anthropic's `skill-creator` skill installed, ask it to run its
description optimization loop with one of these files as the eval set. It splits the queries
into train and held-out sets, measures the trigger rate, and proposes a better description.

Update these when a description changes or when users report the skill loading for the wrong
requests.
