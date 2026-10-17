#!/usr/bin/env python3
"""skills.py: the skills survey for the orchestrate skill.

  local   [--json] [--grep WORD]          every skill this machine can load (project, nested, user, synced, plugins)
  catalog [--source NAME|owner/repo[:prefix]] [--refresh]
                                          what each public catalog holds, counted by category
  search  "words ..." [--source ...] [--limit 20] [--describe] [--refresh]
                                          catalog skills matching the words, marked installed or not
  fetch   SOURCE NAME_OR_PATH --to DIR    download one skill folder into a NEW quarantine DIR and scan it
  install QUARANTINE_SKILL_DIR --target DIR --reviewed [--replace] [--fix-name]
                                          copy a vetted skill into a .claude/skills folder

Catalogs: aitmpl (aitmpl.com, built from github.com/davila7/claude-code-templates),
anthropic (github.com/anthropics/skills), superpowers (github.com/obra/superpowers),
or any public GitHub repo given as owner/repo[:path-prefix].

fetch never runs anything it downloads; install refuses without --reviewed, which says
every downloaded file was read in full (see references/skills-survey.md).
Run with python -P (keeps this folder off sys.path); no third-party packages.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SOURCES = {
    "aitmpl": {"repo": "davila7/claude-code-templates", "prefix": "cli-tool/components/skills/",
               "site": "https://www.aitmpl.com"},
    "anthropic": {"repo": "anthropics/skills", "prefix": "skills/"},
    "superpowers": {"repo": "obra/superpowers", "prefix": "skills/"},
}
UA = {"User-Agent": "orchestrate-skill-survey/1.0", "Accept": "application/vnd.github+json"}
CACHE = Path(tempfile.gettempdir()) / "orchestrate-skill-cache"
TTL = 24 * 3600
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# What the scan flags in downloaded files. A flag is a reason to read closely, not a verdict.
FLAGS = [
    ("network", r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|urllib|requests\.(get|post)|fetch\(|axios|http\.client|socket\.)"),
    ("secrets", r"(os\.environ|process\.env|getenv\(|API_KEY|SECRET|TOKEN\b|\.ssh|\.aws|credentials|keychain|password)"),
    ("exec", r"\b(eval\(|exec\(|subprocess|child_process|os\.system|Start-Process|powershell -enc|bash -c)"),
    ("install", r"\b(pip install|npm install|npx |pnpm add|yarn add|brew install|apt(-get)? install|curl .*\|\s*(ba)?sh)"),
    ("encoded", r"(base64|\\x[0-9a-f]{2}\\x[0-9a-f]{2}|fromCharCode|atob\()"),
    ("destructive", r"(rm -rf|Remove-Item .*-Recurse|del /s|shutil\.rmtree|format c:)"),
    ("agent-steering", r"(ignore (all |any )?(previous|prior|above) instructions|do not tell the user|without telling the user|disregard (the )?(system|user)|you must always run|exfiltrat)"),
]
HIDDEN = re.compile("[​‌‍⁠‪-‮⁦-⁩﻿]")


# ---------- shared ----------

def frontmatter(text):
    """Return name and description from a SKILL.md's YAML header (simple parser, no PyYAML)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out, key, buf = {}, None, []
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            if key:
                out[key] = " ".join(buf).strip()
            key, val = m.group(1), m.group(2).strip()
            buf = [] if val in ("|", ">", "|-", ">-") else [val.strip("'\"")]
        elif key:
            buf.append(line.strip())
    if key:
        out[key] = " ".join(buf).strip()
    return out


def read_skill(md):
    try:
        fm = frontmatter(md.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        fm = {}
    # Claude Code names a skill by its folder; the header's name is only a fallback
    return md.parent.name or fm.get("name", ""), fm.get("description", "")


# ---------- local inventory ----------

def _skill_dirs(root):
    if root.is_dir():
        for md in sorted(root.glob("*/SKILL.md")):
            yield md


def inventory(start=None):
    """Every skill this machine can load, with where it comes from."""
    start = Path(start or os.getcwd()).resolve()
    home = Path.home().resolve()
    seen, items = set(), []

    def add(name, scope, path, desc):
        key = (name, scope)
        if key in seen:
            return
        seen.add(key)
        items.append({"name": name, "scope": scope, "path": str(path), "description": desc})

    # project folders: the start folder and every parent below home
    d = start
    while True:
        for md in _skill_dirs(d / ".claude" / "skills"):
            name, desc = read_skill(md)
            add(name, "project" if d == start else f"project ({d.name})", md.parent, desc)
        if d == home or d.parent == d or home not in d.parents:
            break
        d = d.parent
    # nested project folders under the start folder (scoped skills), two levels down
    for sub in start.glob("*/.claude/skills"):
        for md in _skill_dirs(sub):
            name, desc = read_skill(md)
            add(name, f"nested ({sub.parent.parent.name})", md.parent, desc)
    for sub in start.glob("*/*/.claude/skills"):
        if "node_modules" in sub.parts:
            continue
        for md in _skill_dirs(sub):
            name, desc = read_skill(md)
            add(name, f"nested ({sub.parent.parent.name})", md.parent, desc)
    # user skills and skills synced from claude.ai
    user = home / ".claude" / "skills"
    for md in _skill_dirs(user):
        name, desc = read_skill(md)
        add(name, "user", md.parent, desc)
    synced = user / "synced"
    if synced.is_dir():
        for md in sorted(synced.glob("*/*/SKILL.md")):
            name, desc = read_skill(md)
            add(name, "synced (claude.ai)", md.parent, desc)
    # plugins: newest cached version of each plugin
    cache = home / ".claude" / "plugins" / "cache"
    if cache.is_dir():
        for plugin in sorted(cache.glob("*/*")):
            versions = sorted([v for v in plugin.iterdir() if v.is_dir()], key=lambda p: p.stat().st_mtime)
            if not versions:
                continue
            for md in _skill_dirs(versions[-1] / "skills"):
                name, desc = read_skill(md)
                add(f"{plugin.name}:{name}", "plugin", md.parent, desc)
    return items


def installed_names(items=None):
    names = set()
    for it in items if items is not None else inventory():
        names.add(it["name"].lower())
        names.add(it["name"].split(":")[-1].lower())
    return names


def cmd_local(a):
    items = inventory()
    if a.grep:
        w = a.grep.lower()
        items = [i for i in items if w in i["name"].lower() or w in i["description"].lower()]
    if a.json:
        print(json.dumps(items, indent=1))
        return
    print(f"{len(items)} skills\n")
    print("| Skill | Where | What it's for |\n|---|---|---|")
    for i in items:
        desc = re.sub(r"\s+", " ", i["description"])[:150]
        print(f"| `{i['name']}` | {i['scope']} | {desc} |")


# ---------- catalogs ----------

def _get(url, raw=False):
    req = urllib.request.Request(url, headers=UA if not raw else {"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _source(spec):
    if spec in SOURCES:
        s = dict(SOURCES[spec])
        s["key"] = spec
        return s
    repo, _, prefix = spec.partition(":")
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        sys.exit(f"Unknown source '{spec}'. Use {', '.join(SOURCES)} or owner/repo[:path-prefix].")
    return {"key": repo.replace("/", "__"), "repo": repo, "prefix": prefix.strip("/") + "/" if prefix else ""}


def tree(src, refresh=False):
    """The repo's file list at its default branch head, cached for a day."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{src['repo'].replace('/', '__')}.json"
    if f.exists() and not refresh and time.time() - f.stat().st_mtime < TTL:
        return json.loads(f.read_text(encoding="utf-8"))
    try:
        head = json.loads(_get(f"https://api.github.com/repos/{src['repo']}/commits/HEAD"))
        sha = head["sha"]
        t = json.loads(_get(f"https://api.github.com/repos/{src['repo']}/git/trees/{sha}?recursive=1"))
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub answered {e.code} for {src['repo']} ({e.reason}). "
                 "Unauthenticated calls are limited to 60 an hour; try again later or use the cache.")
    data = {"sha": sha, "date": head.get("commit", {}).get("committer", {}).get("date", ""),
            "truncated": t.get("truncated", False),
            "paths": [x["path"] for x in t.get("tree", []) if x.get("type") == "blob"]}
    f.write_text(json.dumps(data), encoding="utf-8")
    return data


def skills_in(src, data):
    """Skill folders (each holding a SKILL.md) under the source's prefix."""
    out = []
    for p in data["paths"]:
        if p.endswith("/SKILL.md") and p.startswith(src["prefix"]):
            d = p[: -len("/SKILL.md")]
            rel = d[len(src["prefix"]):]
            parts = rel.split("/")
            out.append({"path": d, "name": parts[-1], "category": parts[0] if len(parts) > 1 else ""})
    return out


def _sources(spec):
    return [_source(s) for s in (spec.split(",") if spec else list(SOURCES))]


def cmd_catalog(a):
    for src in _sources(a.source):
        data = tree(src, a.refresh)
        sk = skills_in(src, data)
        cats = {}
        for s in sk:
            cats[s["category"] or "(top level)"] = cats.get(s["category"] or "(top level)", 0) + 1
        print(f"\n{src['key']}: github.com/{src['repo']} @ {data['sha'][:7]} ({data['date'][:10]}): "
              f"{len(sk)} skills in {len(cats)} categories" + (" [tree truncated]" if data["truncated"] else ""))
        for c, n in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"  {n:4d}  {c}")


def cmd_search(a):
    words = [w for w in re.split(r"[^a-z0-9]+", a.words.lower()) if len(w) >= 3]
    if not words:
        sys.exit("Give at least one word of three letters or more.")
    have = installed_names()
    hits = []
    for src in _sources(a.source):
        data = tree(src, a.refresh)
        for s in skills_in(src, data):
            name_parts = s["name"].lower().split("-")
            score = 0
            for w in words:
                if w in s["name"].lower():
                    score += 3 if w in name_parts else 2
                if w in s["category"].lower():
                    score += 1
            if score:
                hits.append(dict(s, source=src["key"], repo=src["repo"], sha=data["sha"], score=score))
    hits.sort(key=lambda h: (-h["score"], h["name"]))
    hits = hits[: a.limit * (3 if a.describe else 1)]
    if a.describe:
        for h in hits:
            try:
                txt = _get(f"https://raw.githubusercontent.com/{h['repo']}/{h['sha']}/{h['path']}/SKILL.md", raw=True)
                h["description"] = frontmatter(txt.decode("utf-8", "replace")).get("description", "")
            except Exception:
                h["description"] = ""
            d = h["description"].lower()
            h["score"] += sum(1 for w in words if w in d)
        hits.sort(key=lambda h: (-h["score"], h["name"]))
    hits = hits[: a.limit]
    print(f"{len(hits)} matches for: {' '.join(words)}\n")
    print("| Score | Skill | Source | Installed? | Path | What it's for |\n|---|---|---|---|---|---|")
    for h in hits:
        inst = "yes" if h["name"].lower() in have else "no"
        desc = re.sub(r"\s+", " ", h.get("description", ""))[:140]
        print(f"| {h['score']} | `{h['name']}` | {h['source']} | {inst} | {h['path']} | {desc} |")
    print("\nNext: skills.py fetch <source> <name or path> --to <new empty folder>")


def _scan(root):
    report = []
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(root)
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.append(f"  BINARY  {rel} ({f.stat().st_size} bytes): not text; read why it's there")
            continue
        if HIDDEN.search(text):
            report.append(f"  HIDDEN  {rel}: zero-width or direction-control characters")
        for n, line in enumerate(text.splitlines(), 1):
            for tag, pat in FLAGS:
                if re.search(pat, line, re.I):
                    report.append(f"  {tag.upper():<8}{rel}:{n}: {line.strip()[:120]}")
        hosts = sorted(set(re.findall(r"https?://([\w.-]+)", text)))
        if hosts:
            report.append(f"  LINKS   {rel}: {', '.join(hosts[:12])}{' …' if len(hosts) > 12 else ''}")
    return report


def cmd_fetch(a):
    src = _source(a.source)
    data = tree(src, a.refresh)
    sk = skills_in(src, data)
    pick = [s for s in sk if s["path"] == a.skill.strip("/")] or [s for s in sk if s["name"] == a.skill]
    if not pick:
        sys.exit(f"No skill '{a.skill}' in {src['repo']}. Run: skills.py search \"{a.skill}\" --source {a.source}")
    if len(pick) > 1:
        sys.exit("Several skills share that name; give the path:\n" + "\n".join("  " + s["path"] for s in pick))
    s = pick[0]
    dest_root = Path(a.to)
    if dest_root.exists() and any(dest_root.iterdir()):
        sys.exit(f"{dest_root} isn't empty. Quarantine each download in a new, empty folder.")
    dest = dest_root / s["name"]
    files = [p for p in data["paths"] if p.startswith(s["path"] + "/")]
    total = 0
    for p in files:
        rel = p[len(s["path"]) + 1:]
        if ".." in Path(rel).parts:
            continue
        body = _get(f"https://raw.githubusercontent.com/{src['repo']}/{data['sha']}/{p}", raw=True)
        total += len(body)
        if total > 5_000_000:
            sys.exit("Over 5 MB: too big for a skill; skipped.")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
    (dest_root / "SOURCE.json").write_text(json.dumps({
        "source": src["key"], "repo": src["repo"], "path": s["path"], "commit": data["sha"],
        "commit_date": data["date"], "fetched": time.strftime("%Y-%m-%d %H:%M"),
        "url": f"https://github.com/{src['repo']}/tree/{data['sha']}/{s['path']}"}, indent=1), encoding="utf-8")
    print(f"Fetched {len(files)} files ({total:,} bytes) from github.com/{src['repo']} @ {data['sha'][:7]} into {dest}\n")
    for p in files:
        print("  " + p[len(s["path"]) + 1:])
    print("\nScan (each line is a place to read closely, not a verdict):")
    rep = _scan(dest)
    print("\n".join(rep) if rep else "  nothing flagged")
    print("\nNow read EVERY file above in full. Install only if it passes the checklist in references/skills-survey.md:\n"
          f"  skills.py install \"{dest}\" --target <project>/.claude/skills --reviewed")


def cmd_install(a):
    src = Path(a.skill_dir)
    md = src / "SKILL.md"
    if not md.exists():
        sys.exit(f"No SKILL.md in {src}.")
    if not a.reviewed:
        sys.exit("Refused: pass --reviewed to confirm you read every file in full and it passed the checklist.")
    text = md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    name = fm.get("name", "")
    if not fm.get("description"):
        sys.exit("SKILL.md has no description; it would never trigger.")
    if name != src.name or not NAME_RE.match(name):
        if not a.fix_name:
            sys.exit(f"Frontmatter name '{name}' must be lowercase-hyphen and match the folder '{src.name}'. "
                     "Pass --fix-name to set it to the folder name.")
        if not NAME_RE.match(src.name):
            sys.exit(f"Folder name '{src.name}' isn't lowercase-hyphen; rename the folder first.")
        text = re.sub(r"(?m)^name:.*$", f"name: {src.name}", text, count=1)
        md.write_text(text, encoding="utf-8")
        name = src.name
    target = Path(a.target)
    if target.name != "skills" or target.parent.name != ".claude":
        sys.exit(f"--target should be a .claude/skills folder, not {target}.")
    dest = target / name
    clash = [i for i in inventory() if i["name"].split(":")[-1].lower() == name.lower()]
    if dest.exists() and not a.replace:
        sys.exit(f"{dest} exists. Pass --replace to overwrite it (only for a newer copy of the same skill).")
    if clash and not dest.exists() and not a.replace:
        where = ", ".join(f"{c['scope']}: {c['path']}" for c in clash)
        sys.exit(f"A skill named '{name}' is already loadable ({where}). Skip it or pass --replace on purpose.")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    meta = src.parent / "SOURCE.json"
    if meta.exists():
        shutil.copy(meta, dest / ".source.json")
        info = json.loads(meta.read_text(encoding="utf-8"))
        origin = f"{info['repo']} `{info['path']}` @ {info['commit'][:7]}"
    else:
        origin = "unknown source"
    print(f"Installed {name} -> {dest}")
    print(f"Record it (e.g. SKILLS_MAP.md): | `{name}` | {fm['description'][:90]}... | from {origin}, "
          f"read in full and installed {time.strftime('%Y-%m-%d')} |")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("local"); s.add_argument("--json", action="store_true"); s.add_argument("--grep")
    s.set_defaults(fn=cmd_local)
    s = sub.add_parser("catalog"); s.add_argument("--source"); s.add_argument("--refresh", action="store_true")
    s.set_defaults(fn=cmd_catalog)
    s = sub.add_parser("search"); s.add_argument("words"); s.add_argument("--source")
    s.add_argument("--limit", type=int, default=20); s.add_argument("--describe", action="store_true")
    s.add_argument("--refresh", action="store_true"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("fetch"); s.add_argument("source"); s.add_argument("skill"); s.add_argument("--to", required=True)
    s.add_argument("--refresh", action="store_true"); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("install"); s.add_argument("skill_dir"); s.add_argument("--target", required=True)
    s.add_argument("--reviewed", action="store_true"); s.add_argument("--replace", action="store_true")
    s.add_argument("--fix-name", action="store_true"); s.set_defaults(fn=cmd_install)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
