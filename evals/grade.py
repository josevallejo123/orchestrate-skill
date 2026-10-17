#!/usr/bin/env python3
"""Grade one test run of the orchestrate skill: python -P grade.py <run-dir> <eval-name>

Reads <run-dir>/outputs/, writes <run-dir>/grading.json in the skill-creator viewer's format
(expectations with text / passed / evidence). Checks are mechanical, so they run the same on
the skill's runs and the baseline's.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORCH = HERE.parent / "scripts" / "orch.py"
SKILLS = HERE.parent / "scripts" / "skills.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


orch = load("orch", ORCH)
skills = load("skills", SKILLS)


def find_file(out):
    cands = [p for p in out.rglob("*.md") if "quarantine" not in p.parts
             and p.name.lower() not in ("notes.md", "skills_survey.md")]
    pref = [p for p in cands if p.name.upper().startswith("PROMPTS")]
    return (pref or cands), (pref or cands)[0] if (pref or cands) else None


def grade(run, eval_name):
    out = run / "outputs"
    exp = []

    def add(text, ok, ev):
        exp.append({"text": text, "passed": bool(ok), "evidence": ev})

    files, f = find_file(out)
    add("One PROMPTS file was produced", len(files) == 1 and f is not None,
        f"found: {', '.join(p.name for p in files) or 'none'}")
    if f is None:
        return exp
    text = f.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    try:
        plan = orch.Plan(f)
        plan.check()
    except SystemExit as e:
        add("The board is machine-readable (an ID column and a needs column)", False, str(e))
        return exp
    ps = plan.prompts()
    jobs = [p for p in plan.order if plan.items[p]["you"]]

    # 1. the box at the top
    head = "\n".join(lines[:45])
    m = re.search(r"^#{1,3}\s*.*(what to do now|do this now|start here|next up|what to paste)", head, re.I | re.M)
    names_ids = m and any(re.search(rf"\b{re.escape(p)}\b", head[m.start():]) for p in ps)
    add("A 'what to do now' box near the top names the prompts to paste now", bool(m and names_ids),
        (m.group(0).strip() if m else "no such heading in the first 45 lines"))

    # 2. board columns
    h = plan.board["header"]
    tog = orch.col(h, "same time", "together", "beside", "parallel")
    add("The board says, per prompt, what must be done first and what runs at the same time",
        plan.cols["needs"] is not None and tog is not None, f"board columns: {h}")

    # 3. tracker
    done_tables = [tb for tb in orch.tables(plan.lines) if orch.col(tb["header"], "done") is not None]
    row_text = " ".join(" ".join(c) for tb in done_tables for _, c in tb["rows"])
    missing = [p for p in plan.order if not re.search(rf"\b{re.escape(p)}\b", row_text)]
    add("A tracker with a Done box covers every prompt", bool(done_tables) and not missing,
        ("missing rows: " + (", ".join(missing) if missing else "none")) if done_tables else "no table with a Done column")

    # 4. decisions
    rows, empty, yc = 0, [], False
    for t in plan.decisions:
        hh = t["header"]
        cr, cy = orch.col(hh, "recommended"), orch.col(hh, "your call")
        yc = yc or cy is not None
        for _, cells in t["rows"]:
            rows += 1
            if cr is None or cr >= len(cells) or not cells[cr].strip(" -—"):
                empty.append(cells[0])
    add("Decisions carry a recommended default and a 'Your call' cell (at least 3)",
        rows >= 3 and yc and not empty, f"{rows} decision rows; 'Your call' column: {yc}; empty recommendations: {empty or 'none'}")

    # 5. prompt sections complete
    bad = []
    for p in ps:
        sec = plan.sections.get(p)
        if sec is None:
            bad.append(f"{p}: no section")
            continue
        miss = [n for n, pat in (("Your part", r"\*\*Your part\b[^*\n]*\*\*"), ("Skills line", r"\*\*Skills, in order of use\b[^*\n]*\*\*"),
                                 ("code block", r"```|~~~")) if not re.search(pat, sec)]
        if miss:
            bad.append(f"{p}: no {', '.join(miss)}")
    add("Every prompt has a 'Your part' box, a 'Skills, in order of use' line and a code block to paste",
        not bad, "; ".join(bad) or f"all {len(ps)} complete")

    # 6. skills named exist (installed, bundled, or listed to install in the survey)
    have = skills.installed_names(skills.inventory(Path.cwd()))
    survey = (out / "skills_survey.md").read_text(encoding="utf-8", errors="replace") if (out / "skills_survey.md").exists() else ""
    unknown = set()
    for p, sec in plan.sections.items():
        mm = re.search(r"\*\*Skills, in order of use\b[^*\n]*\*\*(.*(?:\n>.*)*)", sec)
        if not mm:
            continue
        for name in re.findall(r"`/?([a-z0-9][a-z0-9:-]{2,})`", mm.group(1)):
            base = name.split(":")[-1]
            if name in have or base in have or base in orch.BUILTIN_COMMANDS or base in orch.EFFORT_WORDS:
                continue
            rec = [l for l in survey.splitlines() if base in l and re.search(r"would install|install|✓|pass", l, re.I)
                   and not re.search(r"skip", l, re.I)]
            if rec:
                continue
            unknown.add(name)
    add("Every skill a prompt names is installed (or vetted and listed to install)", not unknown,
        "not found: " + (", ".join(sorted(unknown)) if unknown else "none"))

    # 7. parallel claims are safe (the file's own 'runs at the same time' claims)
    unsafe = []
    if tog is not None:
        for p in ps:
            cells = plan.items[p]["cells"]
            if tog >= len(cells):
                continue
            for q in re.findall(r"\b[A-Z][A-Z0-9-]{0,7}\b", orch.strip_parens(cells[tog])):
                if q in plan.items and not plan.items[q]["you"] and q != p:
                    rel, hits = plan.relation(p, q)
                    if rel != "free":
                        unsafe.append(f"{p}~{q} ({rel}{': ' + ', '.join(hits) if hits else ''})")
    add("No two prompts the file says run at the same time depend on each other or write the same files",
        tog is not None and not unsafe, "; ".join(sorted(set(unsafe))) or ("no 'same time' column" if tog is None else "all claims safe"))

    # 8. orch.py check
    r = subprocess.run([sys.executable, "-P", str(ORCH), "check", str(f)], capture_output=True, text=True, encoding="utf-8")
    errs = [l for l in r.stdout.splitlines() if l.startswith("ERROR")]
    add("orch.py check finds no errors", r.returncode == 0, "; ".join(errs[:4]) or r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])

    # 9. prompts update the tracker and write a handoff
    noupd = [p for p in ps if p in plan.sections and not re.search(r"orch\.py done|tick .{0,40}done|done.{0,20}box", plan.sections[p], re.I)]
    nohand = [p for p in ps if p in plan.sections and "handoff" not in plan.sections[p].lower()]
    add("Every prompt ends by writing a handoff and marking itself done in the tracker", not noupd and not nohand,
        f"no tracker update: {noupd or 'none'}; no handoff: {nohand or 'none'}")

    # 10. skills survey covers the catalogs
    cat = bool(re.search(r"aitmpl|claude-code-templates|anthropics/skills|superpowers", survey, re.I))
    add("A skills survey was done: installed skills plus the public catalogs (aitmpl.com and others)", cat,
        "skills_survey.md " + ("mentions the catalogs" if cat else ("exists but doesn't search the catalogs" if survey else "missing")))

    # 11. the count is explained
    add("The file explains why it has this many prompts", bool(re.search(r"because|so that|since", "\n".join(lines[:12]), re.I)),
        lines[2][:160] if len(lines) > 2 else "")

    # eval-specific
    lv = plan.levels() if not plan.cycle() else {}
    wave1 = [p for p in ps if lv.get(p) == 0]
    if eval_name in ("launch-readiness", "blog-round"):
        add("Wave 1 starts at least three prompts at once", len(wave1) >= 3, f"wave 1: {', '.join(wave1)}")
        last = plan.sections.get(ps[-1], "") if ps else ""
        add("The last prompt merges results into the project records", bool(re.search(r"ingest|merge|decision log", last, re.I)),
            f"last prompt {ps[-1] if ps else '?'}: " + ("mentions a merge step" if re.search(r"ingest|merge|decision log", last, re.I) else "no merge step"))
    if eval_name == "blog-round":
        site = [p for p in ps if any(w.rstrip('/').startswith("site") for w in plan.items[p]["writes"])]
        clash = [f"{a}~{b}" for i, a in enumerate(site) for b in site[i + 1:] if plan.relation(a, b)[0] == "free"]
        add("Only one prompt at a time writes site/ (its git tree deploys on push)", bool(site) and not clash,
            f"site writers: {site or 'none listed in backticks'}; concurrent pairs: {clash or 'none'}")
    if eval_name == "launch-readiness":
        add("Counsel review and the pre-formation limits are carried (verify with counsel; nothing issued before the company is formed)",
            bool(re.search(r"counsel", text, re.I) and re.search(r"LLC|formation|incorporat", text, re.I)), "")
    if eval_name == "small-followup":
        add("Not over-split: three prompts or fewer", 1 <= len(ps) <= 3, f"{len(ps)} prompts: {', '.join(ps)}")
        add("The email stays the user's to send", bool(re.search(r"(user|you) sends?|never send|don't send|do not send", text, re.I)), "")
    return exp


def main():
    run, name = Path(sys.argv[1]), sys.argv[2]
    exp = grade(run, name)
    n = sum(e["passed"] for e in exp)
    data = {"expectations": exp, "summary": {"passed": n, "failed": len(exp) - n, "total": len(exp),
                                              "pass_rate": round(n / len(exp), 2) if exp else 0}}
    (run / "grading.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"{run.parent.name}/{run.name}: {n}/{len(exp)}")
    for e in exp:
        print(("  PASS " if e["passed"] else "  FAIL ") + e["text"] + (f"  [{e['evidence'][:140]}]" if not e["passed"] else ""))


if __name__ == "__main__":
    main()
