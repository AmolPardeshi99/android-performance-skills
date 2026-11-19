# Trigger evals

Each file holds 20 realistic requests for one skill: about half should trigger it and half
should not. The should-not-trigger items are near misses: they share keywords with the skill
but need something else (the other skill in this repo, a profiler skill, a build tool, another
platform).

Use them to check and tune each skill's `description`, which is what an agent reads to decide
whether to load the skill. With Anthropic's `skill-creator` skill installed, ask it to run its
description optimization loop with one of these files as the eval set. It splits the queries
into train and held-out sets, measures the trigger rate, and proposes a better description.

Update these when a description changes or when users report the skill loading for the wrong
requests.
