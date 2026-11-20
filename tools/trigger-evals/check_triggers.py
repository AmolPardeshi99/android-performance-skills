#!/usr/bin/env python3
"""Check which skill an agent loads for each query in a trigger eval file.

Copies the skills in this repo into a scratch project's .claude/skills/, runs each query
through `claude -p`, and records every Skill tool call. A query passes when the target
skill loads (should_trigger: true) or does not load (should_trigger: false). Other skills
installed for your user stay visible, so the result reflects real competition.

Usage:
  python3 tools/trigger-evals/check_triggers.py tools/trigger-evals/<file>.json <skill-name>

Each query is a real, billed model run.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run(query, cwd, env):
    proc = subprocess.run(
        ["claude", "-p", query, "--output-format", "stream-json", "--verbose",
         "--max-turns", "3", "--allowedTools", "Skill,Read,Glob,Grep"],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=300,
    )
    used = set()
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant":
            continue
        for item in event["message"]["content"]:
            if item.get("type") == "tool_use" and item["name"] == "Skill":
                used.add(item["input"].get("skill", ""))
    return used


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    if shutil.which("claude") is None:
        sys.exit("error: the claude CLI is not on PATH")
    queries = json.loads(Path(sys.argv[1]).read_text())
    target = sys.argv[2]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp) / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        for skill in REPO.glob("android-performance-*/SKILL.md"):
            shutil.copytree(skill.parent, skills_dir / skill.parent.name)
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda q: (q, run(q["query"], tmp, env)), queries))
    passed = 0
    for q, used in results:
        hit = any(target in name for name in used)
        ok = hit == q["should_trigger"]
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  should_trigger={q['should_trigger']!s:5}  "
              f"loaded={sorted(used) or '-'}  {q['query'][:80]}")
    print(f"{target}: {passed}/{len(results)}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
