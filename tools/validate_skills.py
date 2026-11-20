#!/usr/bin/env python3
"""Checks every skill in this repo against the Agent Skills spec and the repo's own rules.

Run from the repo root: python3 tools/validate_skills.py
Exits non-zero and prints each problem if anything fails.

Optional: a local, untracked file named .private-denylist.txt (one term per line) lists names
that must never appear in the repo. It is ignored by git and skipped when absent.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\]\(([^)#\s]+)(#[^)]*)?\)")
MAX_SKILL_LINES = 500
TOC_THRESHOLD = 100
TEXT_EXT = (".md", ".kt", ".json", ".sql", ".sh", ".txt", ".yaml", ".yml", ".py")

problems = []


def fail(path, msg):
    problems.append(f"{os.path.relpath(path, ROOT)}: {msg}")


def frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 4:]


def folded(fm, key):
    m = re.search(rf"^{key}:\s*>\s*\n((?:[ \t]+.*\n?)+)", fm, re.M)
    if m:
        return " ".join(l.strip() for l in m.group(1).splitlines()).strip()
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip('"') if m else None


def skills():
    for entry in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, entry, "SKILL.md")
        if os.path.isfile(p):
            yield os.path.join(ROOT, entry)


def check_skill(skill_dir):
    path = os.path.join(skill_dir, "SKILL.md")
    text = open(path, encoding="utf-8").read()
    fm, body = frontmatter(text)
    if fm is None:
        fail(path, "missing YAML frontmatter")
        return
    name = folded(fm, "name")
    desc = folded(fm, "description")
    if not name or not NAME_RE.match(name) or len(name) > 64:
        fail(path, f"invalid name {name!r}")
    elif name != os.path.basename(skill_dir):
        fail(path, f"name {name!r} does not match folder {os.path.basename(skill_dir)!r}")
    if not desc:
        fail(path, "missing description")
    else:
        if len(desc) > 1024:
            fail(path, f"description is {len(desc)} chars (max 1024)")
        if re.search(r"<[a-zA-Z/]", desc):
            fail(path, "description contains XML-like tags")
    lines = body.count("\n")
    if lines > MAX_SKILL_LINES:
        fail(path, f"body is {lines} lines (max {MAX_SKILL_LINES})")

    # Every bundled file is reachable directly from SKILL.md.
    for sub in ("references", "examples", "checklists", "templates"):
        d = os.path.join(skill_dir, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            rel = f"{sub}/{f}"
            if rel not in text:
                fail(path, f"{rel} is not linked from SKILL.md")

    # Long reference files start with a table of contents.
    for sub in ("references", "examples", "checklists"):
        d = os.path.join(skill_dir, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            content = open(p, encoding="utf-8").read()
            if content.count("\n") > TOC_THRESHOLD and "## Contents" not in content[:600]:
                fail(p, f"over {TOC_THRESHOLD} lines without a '## Contents' section at the top")

    check_evals(skill_dir)


def check_evals(skill_dir):
    d = os.path.join(skill_dir, "evals")
    if not os.path.isdir(d):
        fail(skill_dir, "no evals/ folder")
        return
    cases = [c for c in sorted(os.listdir(d)) if os.path.isdir(os.path.join(d, c))]
    if len(cases) < 2:
        fail(d, "fewer than 2 eval cases")
    for c in cases:
        cd = os.path.join(d, c)
        if not NAME_RE.match(c):
            fail(cd, "case folder name must be lowercase-with-hyphens")
        prompt = os.path.join(cd, "prompt.md")
        case = os.path.join(cd, "case.yaml")
        graders = os.path.join(cd, "graders")
        if not os.path.isfile(prompt):
            fail(cd, "missing prompt.md")
        elif not open(prompt, encoding="utf-8").read().startswith("---\n"):
            fail(prompt, "missing settings block")
        if not os.path.isfile(case):
            fail(cd, "missing case.yaml")
        else:
            y = open(case, encoding="utf-8").read()
            if 'schema_version: "' not in y:
                fail(case, "schema_version must be a quoted string")
            if f"name: {c}\n" not in y:
                fail(case, "name must match the folder name")
            if os.path.isdir(os.path.join(cd, "files")) and "scaffold_script:" not in y:
                fail(case, "has files/ but no scaffold_script")
        gs = sorted(os.listdir(graders)) if os.path.isdir(graders) else []
        if not gs:
            fail(cd, "no graders")
        for g in gs:
            gt = open(os.path.join(graders, g), encoding="utf-8").read()
            if not gt.startswith("---\ntype:"):
                fail(os.path.join(graders, g), "grader missing its settings block")


def walk_text_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules")]
        for f in files:
            if f.endswith(TEXT_EXT) and f != ".private-denylist.txt":
                yield os.path.join(base, f)


def check_links_and_json():
    for p in walk_text_files():
        if p.endswith(".md"):
            for m in LINK_RE.finditer(open(p, encoding="utf-8").read()):
                target = m.group(1)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), target))):
                    fail(p, f"broken link {target}")
        if p.endswith(".json"):
            try:
                json.load(open(p, encoding="utf-8"))
            except ValueError as e:
                fail(p, f"invalid JSON: {e}")


def check_marketplace():
    p = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    if not os.path.isfile(p):
        return
    data = json.load(open(p, encoding="utf-8"))
    for key in ("name", "owner", "plugins"):
        if key not in data:
            fail(p, f"missing {key}")
    for plugin in data.get("plugins", []):
        for s in plugin.get("skills", []):
            if not os.path.isfile(os.path.join(ROOT, s, "SKILL.md")):
                fail(p, f"plugin {plugin.get('name')} lists missing skill {s}")


def check_denylist():
    p = os.path.join(ROOT, ".private-denylist.txt")
    if not os.path.isfile(p):
        return
    terms = [t.strip() for t in open(p, encoding="utf-8") if t.strip() and not t.startswith("#")]
    if not terms:
        return
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.I)
    for f in walk_text_files():
        for n, line in enumerate(open(f, encoding="utf-8", errors="ignore"), 1):
            m = pattern.search(line)
            if m:
                fail(f, f"line {n} contains a denylisted term")


def main():
    found = list(skills())
    if not found:
        fail(ROOT, "no skills found")
    for s in found:
        check_skill(s)
    check_links_and_json()
    check_marketplace()
    check_denylist()
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s) found.")
        return 1
    print(f"OK: {len(found)} skills checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
