# Contributing

## Adding a pattern

1. Put the explanation in the matching `references/` file, or add a new one if it is a new
   topic. Each reference covers one topic and starts with a table of contents.
2. Include:
   - what it looks like in an ANR trace, leak trace, or Perfetto trace;
   - why it happens;
   - the fix, and how to roll it out safely;
   - a measured before and after if you have one, with the device class it was measured on.
3. Put framework-specific code in `examples/` for each framework it applies to, not in the
   reference.
4. Add a row to `checklists/review-checklist.md` with an ID, what to look for, a default
   severity, and a link to the reference.
5. If the pattern has a recognizable trace signature, add it to the index in `SKILL.md`.
6. Add or update a test case in the skill's `evals/` folder (`prompt.md`, `case.yaml`, one
   grader per check in `graders/`, inputs in `files/`) and run it before and after your change.
7. Run `python3 tools/validate_skills.py` before opening a pull request. CI runs it too.
8. If you change a `description`, re-check it against `tools/trigger-evals/`.

## Rules

- Keep each `SKILL.md` under 500 lines; aim for under 200. Detail goes in references.
- Link every reference file directly from `SKILL.md`. Do not chain references through other
  references for required reading.
- Write descriptions in the third person, saying what the skill does and when to use it.
- No company, product, internal SDK, or ticket names. Describe the pattern, not where it was
  found.
- Mark guesses as guesses. Thresholds that vary by OEM or Android version should say so.
- Scripts must fail with a clear message when a tool is missing.
