# android-performance-skills

> Agent skills for writing ANR-free, jank-free, and memory-leak-free Android code.

[![skills.sh](https://skills.sh/b/AmolPardeshi99/android-performance-skills)](https://skills.sh/AmolPardeshi99/android-performance-skills)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Skills

| Skill | Installs | What it covers |
|---|---|---|
| [`android-performance-anr-and-jank-prevention`](./android-performance-anr-and-jank-prevention/) | [![skills.sh](https://skills.sh/b/AmolPardeshi99/android-performance-skills/android-performance-anr-and-jank-prevention)](https://skills.sh/AmolPardeshi99/android-performance-skills/android-performance-anr-and-jank-prevention) | ANR design philosophy, coroutine dispatchers, Binder IPC, BroadcastReceiver, JobService, SharedPreferences, frozen frames, Compose recomposition, ANR log analysis |
| [`android-performance-memory-leak-prevention`](./android-performance-memory-leak-prevention/) | [![skills.sh](https://skills.sh/b/AmolPardeshi99/android-performance-skills/android-performance-memory-leak-prevention)](https://skills.sh/AmolPardeshi99/android-performance-skills/android-performance-memory-leak-prevention) | ART GC model, ViewBinding, Activity/Fragment context, static fields, listeners, ViewModel, coroutine scopes, resource cleanup, Compose leaks, SharedFlow, LeakCanary, heap profiling |

Both skills cover **View-based** and **Jetpack Compose** UI systems, with Kotlin code examples for every pattern. Compatible with all major AI coding agents.

---

## Install

### Universal — one command, any agent

```bash
# Install both skills at once
npx skills add AmolPardeshi99/android-performance-skills

# Install individually
npx skills add AmolPardeshi99/android-performance-skills/android-performance-anr-and-jank-prevention
npx skills add AmolPardeshi99/android-performance-skills/android-performance-memory-leak-prevention
```

---

### Per-agent manual install

Clone the repo once, then copy to your agent's skills directory:

```bash
git clone https://github.com/AmolPardeshi99/android-performance-skills.git /tmp/android-performance-skills
```

<details>
<summary><b>Claude Code</b></summary>

```bash
# Global — available in all projects
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.claude/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.claude/skills/

# Project-level — this repo only
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention .claude/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention .claude/skills/
```
</details>

<details>
<summary><b>GitHub Copilot (VS Code)</b></summary>

```bash
# Global
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.copilot/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.copilot/skills/

# Project-level
mkdir -p .github/skills
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention .github/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention .github/skills/
```

Or use the GitHub CLI (`gh` v2.90.0+):

```bash
gh skill install AmolPardeshi99/android-performance-skills android-performance-anr-and-jank-prevention
gh skill install AmolPardeshi99/android-performance-skills android-performance-memory-leak-prevention
```
</details>

<details>
<summary><b>Cursor</b></summary>

```bash
# Global
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.cursor/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.cursor/skills/

# Project-level
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention .cursor/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention .cursor/skills/
```
</details>

<details>
<summary><b>OpenAI Codex CLI</b></summary>

```bash
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.codex/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.codex/skills/
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

```bash
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.gemini/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.gemini/skills/
```
</details>

<details>
<summary><b>Windsurf</b></summary>

```bash
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.windsurf/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.windsurf/skills/
```
</details>

<details>
<summary><b>Cline, Amp, Antigravity, OpenCode, Warp and others</b></summary>

These agents share a common skills path:

```bash
mkdir -p ~/.agents/skills
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.agents/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.agents/skills/
```
</details>

<details>
<summary><b>Goose</b></summary>

```bash
cp -r /tmp/android-performance-skills/android-performance-anr-and-jank-prevention ~/.config/goose/skills/
cp -r /tmp/android-performance-skills/android-performance-memory-leak-prevention ~/.config/goose/skills/
```
</details>

---

### Path reference

| Agent | Global path | Project path |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| Codex CLI | `~/.codex/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.agents/skills/` |
| Windsurf | `~/.windsurf/skills/` | `.agents/skills/` |
| Cline / Amp / Antigravity | `~/.agents/skills/` | `.agents/skills/` |
| Goose | `~/.config/goose/skills/` | — |

> The file inside each skill folder must be named exactly `SKILL.md` (uppercase). Most agents pick up new skills without a restart.

---

## How skills work

Skills use the open `SKILL.md` standard supported across all major AI coding agents. The agent reads only the `name` and `description` fields on startup (~100 tokens), then loads the full skill body only when your task matches — keeping context lean. Both skills activate automatically without any manual invocation.

---

## Project structure

```
android-performance-skills/
├── android-performance-anr-and-jank-prevention/
│   └── SKILL.md          # 1,667 lines — ANR, jank, main-thread safety
└── android-performance-memory-leak-prevention/
    └── SKILL.md          # 1,504 lines — memory leaks, GC, Compose leaks
```

---

## License

[Apache 2.0](LICENSE) — free to use, modify, and distribute with attribution.

---

## Author

Built by [Amol Pardeshi](https://github.com/AmolPardeshi99).
