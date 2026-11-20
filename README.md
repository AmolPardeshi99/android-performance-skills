# android-performance-skills

> Agent skills that diagnose ANRs, jank, and memory leaks in Android apps, and review code for them.

[![skills.sh](https://skills.sh/b/AmolPardeshi99/android-performance-skills)](https://skills.sh/AmolPardeshi99/android-performance-skills)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

The patterns come from fixing ANRs in a large production app with over 100 million installs:
work running in the wrong process, the DI graph acting as a hidden call graph, first-touch costs
(large enums, ICU locale data, reflection), startup that leaves no gap for input, and
third-party SDKs and low-end devices. Where a fix was measured, the reference files give the
before and after numbers.

---

## Skills

| Skill | Use it to |
|---|---|
| [`android-performance-anr-and-jank-prevention`](./android-performance-anr-and-jank-prevention/) | **Triage** an ANR trace, Vitals cluster, or Perfetto trace, or **review** code for main-thread blocking and jank |
| [`android-performance-memory-leak-prevention`](./android-performance-memory-leak-prevention/) | **Investigate** a LeakCanary trace, heap dump, or OOM, or **review** code for leaks |

Each skill routes to one of its two tasks, then loads only the reference and sample files that
task needs. Code samples are split by framework, so a Compose and Koin project never loads View
or Dagger samples.

| | Views/XML | Compose | Dagger/Hilt | Koin | Coroutines/Flow | RxJava |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| ANR and jank | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Memory leaks | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Try it

After installing, ask your agent things like:

- "Here's an ANR from Play Console. Why is it happening?" (paste the trace)
- "Review `HomeActivity.kt` for ANR and jank risk."
- "Run the Perfetto queries on `startup.perfetto-trace` and tell me what blocks the main thread."
- "LeakCanary reported this. What's the fix?" (paste the leak trace)
- "Check this Fragment for leaks."

Reviews come back as findings graded CRITICAL, HIGH, MEDIUM, or LOW, each with the file and
line, the verified thread or holder, and a fix in your project's framework. Candidates that
turned out fine are listed separately with the reason.

---

## Install

### Any agent: `npx skills`

```bash
npx skills add AmolPardeshi99/android-performance-skills
```

Add `-g` to install for all projects, `-a <agent>` to pick an agent, or `--skill <name>` for one
skill. See [vercel-labs/skills](https://github.com/vercel-labs/skills).

### Claude Code: plugin marketplace

```bash
claude plugin marketplace add AmolPardeshi99/android-performance-skills
claude plugin install android-performance@android-performance-skills
```

Inside a session, use `/plugin marketplace add AmolPardeshi99/android-performance-skills`.

### GitHub Copilot: `gh skill`

```bash
gh skill install AmolPardeshi99/android-performance-skills android-performance-anr-and-jank-prevention
gh skill install AmolPardeshi99/android-performance-skills android-performance-memory-leak-prevention
```

### Manual copy

Clone once, then copy the skill folders into your agent's skills directory:

```bash
git clone https://github.com/AmolPardeshi99/android-performance-skills.git
```

```bash
cp -r android-performance-skills/android-performance-* ~/.claude/skills/
```

| Agent | Personal (all projects) | Project (commit to repo) |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| GitHub Copilot | `~/.copilot/skills/` or `~/.agents/skills/` | `.github/skills/`, `.claude/skills/`, or `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` (also reads `.claude/skills/`) |
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Cline, Amp, OpenCode, Warp, and others | `~/.agents/skills/` | `.agents/skills/` |

Each folder must contain a file named exactly `SKILL.md`. The folder name must match the `name`
in its frontmatter. Paths change; if a skill does not load, check your agent's documentation.

### Optional tools the skills can use

- `trace_processor_shell` from [Perfetto](https://perfetto.dev/docs/analysis/trace-processor),
  for `scripts/perfetto/run_queries.sh`.
- `adb` and a debuggable build, for `scripts/capture_heap_dump.sh`.
- [`shark-cli`](https://square.github.io/leakcanary/shark/) to analyze heap dumps without
  Android Studio.

---

## How the skills are built

They follow the [Agent Skills specification](https://agentskills.io/specification) and
Anthropic's [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

- A short `SKILL.md` (under 200 lines) that picks the task and holds the workflow. Agents read
  only its `name` and `description` until a request matches.
- `references/` files, one topic each, read only when a step needs them. Each starts with a
  table of contents.
- `examples/` split by framework, so only the matching samples load.
- `checklists/` with rule IDs and severity, and `templates/` for report output.
- `scripts/` that the agent runs rather than reads.
- `evals/` test cases in the layout `claude plugin eval` and Anthropic's `skill-creator` read,
  plus trigger queries for tuning each description.

They work alongside Google's official Android skills (`anr-audit-and-fix`,
`jetpack-compose-performance`, `android-profiler`) and point to them for deep Compose and trace
recording work.

```
android-performance-skills/
├── .claude-plugin/marketplace.json
├── android-performance-anr-and-jank-prevention/
│   ├── SKILL.md
│   ├── references/      anr-mechanics, trace-reading, perfetto, main-thread-io,
│   │                    threading-and-locks, di-graph-cost, class-init-first-touch,
│   │                    receivers-and-processes, startup-input-gaps,
│   │                    third-party-sdks-low-end, rendering-jank, release-watch
│   ├── examples/        views, compose, dagger-hilt, koin, coroutines-flow, rxjava
│   ├── checklists/      review-checklist
│   ├── templates/       anr-report, review-report
│   ├── scripts/perfetto/  *.sql, run_queries.sh
│   └── evals/           test cases: prompt.md, case.yaml, graders/, files/
├── android-performance-memory-leak-prevention/
│   ├── SKILL.md
│   ├── references/      memory-model, leak-trace-reading, lifecycle-and-views,
│   │                    context-and-statics, listeners-and-callbacks, async-and-scopes,
│   │                    di-scopes, resources-and-native, detection-and-tools
│   ├── examples/        views, compose, dagger-hilt, koin, coroutines-flow, rxjava
│   ├── checklists/      review-checklist
│   ├── templates/       leak-report, review-report
│   ├── scripts/         capture_heap_dump.sh
│   └── evals/           test cases: prompt.md, case.yaml, graders/, files/
├── tools/
│   ├── validate_skills.py   spec, link, eval-format, and marketplace checks (runs in CI)
│   └── trigger-evals/       20 should/should-not trigger queries per skill
└── .github/workflows/validate.yml
```

## Testing the skills

The workflow follows Anthropic's `skill-creator`: write test cases, run them with and without
the skill, grade, improve, repeat; then tune the description against trigger queries.

```bash
# Structure, links, eval format, marketplace manifest
python3 tools/validate_skills.py
```

```bash
# Run one skill's test cases with and without the skill (Claude Code; real, billed model runs)
cd android-performance-anr-and-jank-prevention && claude plugin eval . --scaffold
```

```bash
# Check which skill loads for each trigger query (real, billed model runs)
python3 tools/trigger-evals/check_triggers.py tools/trigger-evals/<file>.json <skill-name>
```

Each case folder holds the user's prompt (`prompt.md`), what a good answer does
(`case.yaml`), one check per file in `graders/`, and any input files in `files/`. To tune a
description, give the matching file in `tools/trigger-evals/` to `skill-creator`'s description
optimization loop. See [tools/trigger-evals/README.md](tools/trigger-evals/README.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New patterns are welcome, especially with a trace
signature and a measured before and after.

## License

[Apache 2.0](LICENSE).

## Author

Built by [Amol Pardeshi](https://github.com/AmolPardeshi99).
