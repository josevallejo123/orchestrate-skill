#!/usr/bin/env python3
"""orch.py: keeps a PROMPTS orchestration file honest, so the person running it always knows what to paste next.

  check FILE [--fill]   validate the board: unknown or circular needs, prompts that would write the same files
                        at the same time, prompt sections missing their "Your part" box, skills line, code block
                        or closing steps, skills that aren't installed, decisions used by unknown prompts.
                        Prints the waves and what can run together. --fill rewrites the waves block and the
                        "Runs at the same time as" column from the needs and the files each prompt writes.
  now FILE [--write]    print the "What to do now" box; --write also puts it in the file and refreshes the
                        tracker's State column.
  start FILE ID         a session's first command: ticks its "Started" box, refreshes the box.
  done FILE ID          a session's last command (or the person's, for a J-item): ticks "Done", refreshes the box.
  log FILE ID TEXT      appends a dated line to the file's log (decisions changed along the way, surprises).

The file's format is in assets/PROMPTS_TEMPLATE.md. Run with python -P. No third-party packages.
"""
import argparse
import importlib.util
import os
import re
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NOW_START, NOW_END = "<!-- orch:now:start -->", "<!-- orch:now:end -->"
WAVES_START, WAVES_END = "<!-- orch:waves:start -->", "<!-- orch:waves:end -->"
LOG_END = "<!-- orch:log:end -->"
EFFORT_WORDS = {"low", "medium", "high", "xhigh", "max", "ultra"}
ID_RE = re.compile(r"^[A-Z][A-Z0-9-]{0,7}$")
BUILTIN_COMMANDS = {"code-review", "simplify", "security-review", "init", "review", "loop", "schedule", "run",
                    "ingest", "next", "board", "fewer-permission-prompts", "plugin-authoring", "update-config",
                    "keybindings-help", "claude-api", "workflow-authoring", "orchestrate", "dataviz",
                    "artifact-design", "artifact-diagramming", "artifact-capabilities"}  # bundled with Claude Code


# ---------- reading the file ----------

def split_cells(line):
    """Split a Markdown table row on | that aren't escaped or inside backticks."""
    s = line.strip().rstrip("\r")
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, tick, i = [], "", False, 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "\\|"
            i += 2
            continue
        if c == "`":
            tick = not tick
        if c == "|" and not tick:
            cells.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur.strip())
    return cells


def norm(h):
    return re.sub(r"[*`_]", "", h).strip().lower()


FENCE_RE = re.compile(r"^\s*(```|~~~)")


def fenced(lines):
    """For each line, True if it sits inside a ``` or ~~~ code block (fence lines count as inside)."""
    out, fence = [], None
    for ln in lines:
        m = FENCE_RE.match(ln)
        if m and fence is None:
            fence = m.group(1)
            out.append(True)
        elif m and m.group(1) == fence:
            fence = None
            out.append(True)
        else:
            out.append(fence is not None)
    return out


def first_block(sec):
    """The text of the first fenced code block in a section, or None."""
    m = re.search(r"^\s*(```|~~~)[^\n]*\n(.*?)^\s*\1", sec, re.S | re.M)
    return m.group(2) if m else None


def tables(lines):
    out, i = [], 0
    inside = fenced(lines)
    while i < len(lines) - 1:
        if not inside[i] and lines[i].lstrip().startswith("|") and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            header = [norm(c) for c in split_cells(lines[i])]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j, split_cells(lines[j])))
                j += 1
            out.append({"start": i, "header": header, "rows": rows})
            i = j
        else:
            i += 1
    return out


def col(header, *names):
    for n in names:
        for k, h in enumerate(header):
            if n in h:
                return k
    return None


def clean_id(cell):
    return re.sub(r"[*`\s]", "", cell)


def strip_parens(s):
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\([^()]*\)", " ", s)
    return s


class Plan:
    def __init__(self, path):
        self.path = Path(path)
        raw = self.path.read_bytes().decode("utf-8")
        self.nl = "\r\n" if raw.count("\r\n") > raw.count("\n") / 2 else "\n"
        self.lines = raw.split("\n")
        self.errors, self.warnings, self.notes = [], [], []
        self.parse()

    # -- model --
    def parse(self):
        ts = tables(self.lines)
        self.board = next((t for t in ts if "id" in t["header"] and col(t["header"], "needs", "start when") is not None), None)
        self.tracker = next((t for t in ts if "id" in t["header"] and col(t["header"], "done") is not None
                             and t is not self.board), None)
        if self.tracker is None and self.board and col(self.board["header"], "done") is not None:
            self.tracker = self.board
        self.decisions = [t for t in ts if col(t["header"], "recommended") is not None]
        if not self.board:
            sys.exit(f"{self.path.name}: no board table (a table with an 'ID' column and a 'Needs' column).")
        h = self.board["header"]
        c_id = h.index("id")
        c_prompt = col(h, "prompt", "what")
        c_needs = col(h, "needs")
        self.legacy = c_needs is None
        if self.legacy:
            c_needs = col(h, "start when")
            self.warnings.append("Board uses a 'Start when' column; needs were read from its prose. Use a 'Needs' column of IDs.")
        c_together = col(h, "same time", "together", "beside")
        c_writes = col(h, "writes")
        self.cols = dict(id=c_id, prompt=c_prompt, needs=c_needs, together=c_together, writes=c_writes)
        self.items, self.order = {}, []
        for ln, cells in self.board["rows"]:
            pid = clean_id(cells[c_id]) if c_id < len(cells) else ""
            if not ID_RE.match(pid):
                continue
            title = cells[c_prompt] if c_prompt is not None and c_prompt < len(cells) else ""
            you = bool(re.match(r"^J\d+$", pid)) or re.match(r"^\**\s*you\b", title, re.I) is not None
            self.items[pid] = dict(id=pid, line=ln, cells=cells, title=title, you=you,
                                   needs_raw=cells[c_needs] if c_needs < len(cells) else "",
                                   writes=self._writes(cells[c_writes]) if c_writes is not None and c_writes < len(cells) else [],
                                   started=False, done=False, started_at="", done_at="")
            self.order.append(pid)
        for it in self.items.values():
            text = strip_parens(it["needs_raw"])
            found = re.findall(r"\b[A-Z][A-Z0-9-]{0,7}\b", text)
            it["needs"] = [x for x in dict.fromkeys(found) if x in self.items and x != it["id"]]
            unknown = [x for x in dict.fromkeys(found) if x not in self.items and re.search(r"\d", x)]
            if unknown and not self.legacy:
                self.errors.append(f"{it['id']} needs {', '.join(unknown)}, which isn't on the board.")
        self._read_tracker()
        self._read_sections()

    @staticmethod
    def _writes(cell):
        out = []
        for t in re.findall(r"`([^`]+)`", cell):
            t = t.strip().replace("\\", "/")
            if "<" in t or not t or re.fullmatch(r"\.[A-Za-z0-9]+", t):  # skip bare extensions like .pdf
                continue
            t = re.sub(r"^\./", "", t).split("*")[0]  # compared case-insensitively in overlap()
            out.append(t)
        return out

    def _read_tracker(self):
        if not self.tracker:
            self.warnings.append("No tracker table (a table with 'ID' and 'Done' columns).")
            return
        h = self.tracker["header"]
        self.tcols = dict(id=h.index("id"), state=col(h, "state"), started=col(h, "started", "pasted"), done=col(h, "done"))
        seen = set()
        for ln, cells in self.tracker["rows"]:
            pid = clean_id(cells[self.tcols["id"]])
            if pid not in self.items:
                continue
            seen.add(pid)
            it = self.items[pid]
            it["trow"] = ln
            for key in ("started", "done"):
                c = self.tcols[key]
                if c is not None and c < len(cells) and re.search(r"\[[xX✓]\]|^\s*✓|^\s*done", cells[c]):
                    it[key] = True
                    it[key + "_at"] = re.sub(r"\[[xX✓]\]", "", cells[c]).strip()
            if it["done"]:
                it["started"] = True
        for pid in self.order:
            if pid not in seen and self.tracker is not self.board:
                self.warnings.append(f"{pid} has no row in the tracker.")

    def _read_sections(self):
        self.sections = {}
        cur, buf = None, []
        inside = fenced(self.lines)
        for k, ln in enumerate(self.lines):
            m = None if inside[k] else re.match(r"^###\s+\**([A-Z][A-Z0-9-]{0,7})\**\s*[:—–·.-]", ln)
            if m or (not inside[k] and re.match(r"^#{1,2}\s", ln)):
                if cur:
                    self.sections[cur] = "\n".join(buf)
                cur, buf = (m.group(1) if m and m.group(1) in self.items else None), []
            elif cur:
                buf.append(ln)
        if cur:
            self.sections[cur] = "\n".join(buf)

    # -- graph --
    def ancestors(self, pid, seen=None):
        seen = set() if seen is None else seen
        for n in self.items[pid]["needs"]:
            if n not in seen:
                seen.add(n)
                self.ancestors(n, seen)
        return seen

    def cycle(self):
        state = {}

        def visit(p, stack):
            state[p] = 1
            for n in self.items[p]["needs"]:
                if state.get(n) == 1:
                    return stack + [p, n]
                if not state.get(n):
                    r = visit(n, stack + [p])
                    if r:
                        return r
            state[p] = 2
            return None

        for p in self.order:
            if not state.get(p):
                r = visit(p, [])
                if r:
                    return r
        return None

    def levels(self):
        lv = {}

        def level(p):
            if p not in lv:
                lv[p] = 0
                lv[p] = 1 + max((level(n) for n in self.items[p]["needs"]), default=-1)
            return lv[p]

        for p in self.order:
            level(p)
        return lv

    @staticmethod
    def overlap(a, b):
        hits = []
        for x in a:
            for y in b:
                xs, ys = x.rstrip("/").lower(), y.rstrip("/").lower()
                if xs == ys or xs.startswith(ys + "/") or ys.startswith(xs + "/"):
                    hits.append(min(x, y, key=len))
        return sorted(set(hits))

    def relation(self, a, b):
        """'order' if one needs the other (directly or not), 'shared' if they write the same files, else 'free'."""
        if a in self.ancestors(b) or b in self.ancestors(a):
            return "order", []
        hits = self.overlap(self.items[a]["writes"], self.items[b]["writes"])
        return ("shared", hits) if hits else ("free", [])

    def prompts(self):
        return [p for p in self.order if not self.items[p]["you"]]

    def together(self, pid):
        return [q for q in self.prompts() if q != pid and self.relation(pid, q)[0] == "free"]

    def exclusive_pairs(self):
        ps, out = self.prompts(), []
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                rel, hits = self.relation(a, b)
                if rel == "shared":
                    out.append((a, b, hits))
        return out

    def longest_chain(self):
        best = {}

        def chain(p):
            if p not in best:
                tails = [chain(n) for n in self.items[p]["needs"]]
                best[p] = (max(tails, key=len) if tails else []) + [p]
            return best[p]

        return max((chain(p) for p in self.order), key=len, default=[])

    # -- checks --
    def check(self):
        cyc = self.cycle()
        if cyc:
            self.errors.append("Circular needs: " + " -> ".join(cyc))
            return
        for a, b, hits in self.exclusive_pairs():
            self.notes.append(f"One at a time, either order: {a} / {b} (both write {', '.join('`'+h+'`' for h in hits)})")
        for o, mine, paths in self.foreign_overlaps():
            self.warnings.append(f"Another round isn't finished: {o['file']} {o['id']} also writes "
                                 f"{', '.join('`'+h+'`' for h in paths)}, like {', '.join(mine)} here. Say in §0 and in "
                                 f"those prompts which goes first (the box holds them while it runs).")
        c_tog = self.cols["together"]
        for pid in self.prompts():
            it = self.items[pid]
            if c_tog is not None and not self.legacy and c_tog < len(it["cells"]):
                named = [x for x in re.findall(r"\b[A-Z][A-Z0-9-]{0,7}\b", strip_parens(it["cells"][c_tog])) if x in self.items]
                for q in named:
                    if self.items[q]["you"]:
                        continue
                    rel, hits = self.relation(pid, q)
                    if rel == "order":
                        self.errors.append(f"{pid} says it runs beside {q}, but one needs the other. Run check --fill.")
                    elif rel == "shared":
                        self.errors.append(f"{pid} says it runs beside {q}, but both write {', '.join(hits)}. Run check --fill.")
            if not it["writes"] and self.cols["writes"] is not None:
                self.warnings.append(f"{pid} lists no files in backticks under Writes, so nothing guards it against a parallel session.")
            sec = self.sections.get(pid)
            if sec is None:
                self.errors.append(f"{pid} has no prompt section (a '### {pid}: …' heading).")
                continue
            if not re.search(r"\*\*Your part\b[^*\n]*\*\*", sec):
                self.errors.append(f"{pid}: no **Your part:** box.")
            if not re.search(r"\*\*Skills, in order of use\b[^*\n]*\*\*", sec):
                self.errors.append(f"{pid}: no **Skills, in order of use:** line.")
            block = first_block(sec)
            if block is None:
                self.errors.append(f"{pid}: no code block to paste.")
            elif not self.legacy:
                if "orch.py start" not in block:
                    self.warnings.append(f"{pid}: the prompt never runs 'orch.py start', so the tracker won't show it running.")
                if "orch.py done" not in block:
                    self.warnings.append(f"{pid}: the prompt never runs 'orch.py done', so the next prompts won't show as ready.")
                if "handoff" not in block.lower():
                    self.warnings.append(f"{pid}: the prompt doesn't write a handoff.")
        self._check_skills()
        for t in self.decisions:
            h = t["header"]
            cu, cr, cy = col(h, "used by"), col(h, "recommended"), col(h, "your call")
            if cy is None:
                self.warnings.append("A decisions table has no 'Your call' column.")
            for ln, cells in t["rows"]:
                did = clean_id(cells[0]) if cells else "?"
                if cr is not None and cr < len(cells) and not cells[cr].strip(" -—"):
                    self.errors.append(f"Decision {did} has no recommended option.")
                if cu is not None and cu < len(cells):
                    for x in re.findall(r"\b[A-Z][A-Z0-9-]{0,7}\b", cells[cu]):
                        if re.search(r"\d", x) and x not in self.items:
                            self.warnings.append(f"Decision {did} is used by {x}, which isn't on the board.")
        if not self.legacy:
            text = "\n".join(self.lines)
            for m, what in ((NOW_START, "the 'What to do now' box"), (WAVES_START, "the waves block"), (LOG_END, "the log")):
                if m not in text:
                    self.warnings.append(f"No {m} marker, so {what} can't be kept current.")

    def _check_skills(self):
        try:
            spec = importlib.util.spec_from_file_location("skills", Path(__file__).with_name("skills.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # sessions run where the file lives, where this one started, or in the project this skill belongs to
            roots = {self.path.parent.resolve(), Path.cwd().resolve(), Path(__file__).resolve().parents[3]}
            have = set().union(*(mod.installed_names(mod.inventory(r)) for r in roots))
        except Exception as e:  # the survey script is optional for the check
            self.warnings.append(f"Couldn't list installed skills ({e}); skill names not checked.")
            return
        missing = {}
        for pid, sec in self.sections.items():
            m = re.search(r"\*\*Skills, in order of use\b[^*\n]*\*\*(.*(?:\n>.*)*)", sec)
            if not m:
                continue
            for name in re.findall(r"`/?([a-z0-9][a-z0-9:-]{2,})`", m.group(1)):
                base = name.split(":")[-1]
                if name.lower() in have or base.lower() in have or base in BUILTIN_COMMANDS or base in EFFORT_WORDS:
                    continue
                missing.setdefault(name, []).append(pid)
        for name, pids in missing.items():
            self.warnings.append(f"Skill `{name}` (named by {', '.join(pids)}) isn't installed here. Install it or rename it.")

    # -- state --
    def state(self, pid):
        it = self.items[pid]
        if it["done"]:
            return "done", []
        if it["started"]:
            return "running", []
        waiting = [n for n in it["needs"] if not self.items[n]["done"]]
        if waiting:
            return "waiting", waiting
        if it["you"]:
            return "yours", []
        busy = [q for q in self.prompts() if q != pid and self.items[q]["started"] and not self.items[q]["done"]
                and self.relation(pid, q)[0] == "shared"]
        busy += [f"{o['file']} {o['id']}" for o in self.others()
                 if o["started"] and self.overlap(it["writes"], o["writes"])]
        if busy:
            return "blocked", busy
        return "ready", []

    def others(self):
        """Unfinished prompts in the other PROMPTS files of this folder (other rounds) and what they write."""
        if not hasattr(self, "_others"):
            self._others = []
            for f in sorted(self.path.parent.glob("PROMPTS*.md")):
                if f.resolve() == self.path.resolve():
                    continue
                try:
                    sp = Plan(f)
                except (SystemExit, Exception):
                    continue
                for q in sp.prompts():
                    o = sp.items[q]
                    if not o["done"] and o["writes"]:
                        self._others.append(dict(file=f.stem, id=q, writes=o["writes"], started=o["started"]))
        return self._others

    def foreign_overlaps(self, only_open=True):
        """[(other prompt, [this file's prompts it overlaps], paths)] for other rounds' unfinished prompts."""
        out = []
        for o in self.others():
            mine, paths = [], set()
            for p in self.prompts():
                if only_open and self.items[p]["done"]:
                    continue
                hits = self.overlap(self.items[p]["writes"], o["writes"])
                if hits:
                    mine.append(p)
                    paths.update(hits)
            if mine:
                out.append((o, mine, sorted(paths)))
        return out

    def state_text(self, pid):
        s, why = self.state(pid)
        it = self.items[pid]
        return {
            "done": f"✓ done{(' ' + it['done_at']) if it['done_at'] else ''}",
            "running": "… running",
            "waiting": "⏳ waits on " + ", ".join(why),
            "yours": "👤 yours to do",
            "blocked": "⏸ after " + ", ".join(why) + " finishes (same files)",
            "ready": "▶ ready: paste now",
        }[s]

    def unblocks(self, pid):
        return [q for q in self.order if pid in self.items[q]["needs"]]

    def now_box(self):
        ready, yours, running, waiting, blocked = [], [], [], [], []
        for p in self.order:
            s, why = self.state(p)
            {"ready": ready, "yours": yours, "running": running}.get(s, []).append(p)
            if s == "waiting":
                waiting.append((p, why))
            if s == "blocked":
                blocked.append((p, why))
        ps = self.prompts()
        jobs = [p for p in self.order if self.items[p]["you"]]
        done_p = sum(self.items[p]["done"] for p in ps)
        done_j = sum(self.items[p]["done"] for p in jobs)
        title = lambda p: re.sub(r"\*\*", "", self.items[p]["title"]).strip()
        out = ["## ▶ What to do now", ""]
        all_done = done_p == len(ps) and bool(ps)
        if all_done:
            out += [f"**All {len(ps)} prompts are done.** Read the last prompt's handoff for the results and what's left for you.", ""]
            # the person's own last steps (send the email, sign in somewhere) still show until they're ticked
            if yours:
                out.append("**Still yours to do** (tell any session \"<ID> done\" when finished):")
                out += [f"- **{p}** {re.sub(r'^(You|Your part):?\s*', '', title(p), flags=re.I)}" for p in yours]
                out.append("")
        else:
            if ready:
                pairs = [(a, b) for a, b, _ in self.exclusive_pairs() if a in ready and b in ready]
                lead = "**Paste now**, each in its own new session"
                lead += ", all at the same time:" if len(ready) > 1 else ":"
                out.append(lead)
                for p in ready:
                    out.append(f"- **{p}** {title(p)}")
                for a, b in pairs:
                    out.append(f"- *{a} and {b} write the same files: paste one, the other after it's done.*")
            else:
                out.append("**Nothing new to paste right now.**" + (" Wait for the running sessions." if running else ""))
            out.append("")
            if yours:
                out.append("**Your actions** (tell any session \"<ID> done\" when finished):")
                for p in yours:
                    un = self.unblocks(p)
                    out.append(f"- **{p}** {re.sub(r'^(You|Your part):?\s*', '', title(p), flags=re.I)}"
                               + (f" → unblocks {', '.join(un)}" if un else ""))
                out.append("")
            if running:
                out.append("**Running:** " + " · ".join(f"{p}{(' (since ' + self.items[p]['started_at'] + ')') if self.items[p]['started_at'] else ''}" for p in running))
            if blocked:
                out.append("**Ready after a running session:** " + " · ".join(f"{p} after {', '.join(w)}" for p, w in blocked))
            if waiting:
                out.append("**Waiting:** " + " · ".join(f"{p} ← {', '.join(w)}" for p, w in waiting))
            fo = self.foreign_overlaps()
            if fo:
                out.append("**Other rounds still open on the same files:** " + " · ".join(
                    f"{o['file']} {o['id']}{' (running)' if o['started'] else ''} ↔ {', '.join(mine)} ({', '.join(paths)})"
                    for o, mine, paths in fo))
            out.append(f"**Done:** {done_p} of {len(ps)} prompts" + (f" · {done_j} of {len(jobs)} of your actions" if jobs else ""))
            out.append("")
        out.append(f"_Refreshed {time.strftime('%Y-%m-%d %H:%M')}. Sessions update this box themselves; "
                   f"to refresh it by hand: `python -P {self.script_ref()} now {self.path.name} --write`_")
        return out

    def script_ref(self):
        try:
            ref = os.path.relpath(Path(__file__).resolve(), self.path.resolve().parent).replace("\\", "/")
        except ValueError:
            ref = str(Path(__file__).resolve()).replace("\\", "/")
        if ref.count("../") > 3:
            ref = str(Path(__file__).resolve()).replace("\\", "/")
        return f'"{ref}"' if " " in ref else ref

    def waves_block(self):
        lv = self.levels()
        maxlv = max(lv.values(), default=0)
        out = ["```text"]
        for L in range(maxlv + 1):
            ps = [p for p in self.order if lv[p] == L and not self.items[p]["you"]]
            js = [p for p in self.order if lv[p] == L and self.items[p]["you"]]
            if L == 0:
                head = "Wave 1, start now, all at once:"
                body = "  ".join(ps) + (("     you: " + ", ".join(js)) if js else "")
            else:
                head = f"Wave {L + 1}, each as soon as its needs are done:" if L == 1 else f"Wave {L + 1}:"
                parts = [f"{p} ← {', '.join(self.items[p]['needs'])}" for p in ps]
                parts += [f"you: {p} ← {', '.join(self.items[p]['needs'])}" for p in js]
                body = "   ·   ".join(parts)
            out.append(f"{head}\n    {body}")
        ex = self.exclusive_pairs()
        if ex:
            out.append("One at a time, either order (they write the same files):")
            for a, b, hits in ex:
                out.append(f"    {a} / {b}   ({', '.join(hits)})")
        chain = self.longest_chain()
        if len(chain) > 1:
            out.append("Longest chain (it sets the finish date): " + " → ".join(chain))
        out.append("```")
        return out

    # -- writing --
    def replace_block(self, start, end, body):
        text = "\n".join(self.lines)
        i, j = text.find(start), text.find(end)
        if i < 0 or j < 0 or j < i:
            return False
        nl = self.nl
        new = start + nl + nl.join(body) + nl + end
        text = text[:i] + new + text[j + len(end):]
        self.lines = text.split("\n")
        return True

    def set_cell(self, ln, k, value):
        cells = split_cells(self.lines[ln])
        while len(cells) <= k:
            cells.append("")
        cells[k] = value
        cr = "\r" if self.lines[ln].endswith("\r") else ""
        self.lines[ln] = "| " + " | ".join(cells) + " |" + cr

    def refresh_states(self):
        if not self.tracker or self.tcols.get("state") is None:
            return
        for p in self.order:
            it = self.items[p]
            if "trow" in it:
                self.set_cell(it["trow"], self.tcols["state"], self.state_text(p))

    def save(self):
        text = "\n".join(self.lines)
        if self.nl == "\r\n":
            text = re.sub(r"(?<!\r)\n", "\r\n", text)
        self.path.write_bytes(text.encode("utf-8"))


# ---------- a lock, so two sessions finishing together don't clobber each other ----------

class Lock:
    def __init__(self, path):
        self.lock = Path(str(path) + ".lock")

    def __enter__(self):
        for _ in range(100):
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.lock.stat().st_mtime > 60:
                        self.lock.unlink()
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(0.2)
        sys.exit(f"{self.lock} is held by another session; try again in a minute.")

    def __exit__(self, *a):
        try:
            self.lock.unlink()
        except FileNotFoundError:
            pass


# ---------- commands ----------

def cmd_check(a):
    with Lock(a.file):
        plan = Plan(a.file)
        plan.check()
        ps = plan.prompts()
        jobs = [p for p in plan.order if plan.items[p]["you"]]
        print(f"{plan.path.name}: {len(ps)} prompts, {len(jobs)} of your actions, "
              f"{sum(len(t['rows']) for t in plan.decisions)} decisions\n")
        if not plan.cycle():
            print("\n".join(plan.waves_block()[1:-1]))
            print("\nCan run at the same time:")
            for p in ps:
                print(f"  {p}: {', '.join(plan.together(p)) or 'nothing'}")
        for n in plan.notes:
            print("NOTE  " + n)
        for w in plan.warnings:
            print("WARN  " + w)
        for e in plan.errors:
            print("ERROR " + e)
        print(f"\n{'OK' if not plan.errors else 'FIX'}: {len(plan.errors)} errors, {len(plan.warnings)} warnings")
        if a.fill and not plan.cycle():
            if plan.legacy:
                sys.exit("--fill needs the new format (a 'Needs' column).")
            # rows first: replacing a block above the table shifts its line numbers
            c = plan.cols["together"]
            if c is not None:
                for p in ps:
                    t = plan.together(p)
                    plan.set_cell(plan.items[p]["line"], c, ", ".join(t) if t else "nothing (alone)")
            if not plan.replace_block(WAVES_START, WAVES_END, plan.waves_block()):
                print("No waves markers; waves block not written.")
            plan.save()
            print("Filled the waves block and the 'Runs at the same time as' column.")
        sys.exit(1 if plan.errors else 0)


def _refresh_and_print(plan, write=True):
    box = plan.now_box()
    if write:
        plan.refresh_states()  # rows first: the box above them changes the line numbers
        if not plan.replace_block(NOW_START, NOW_END, box):
            print(f"(No {NOW_START} marker in the file; box printed only.)\n")
        plan.save()
    print("\n".join(box))


def cmd_now(a):
    with Lock(a.file):
        plan = Plan(a.file)
        _refresh_and_print(plan, write=a.write)


def _tick(a, key):
    with Lock(a.file):
        plan = Plan(a.file)
        pid = a.id.upper()
        if pid not in plan.items:
            sys.exit(f"{pid} isn't on the board. IDs: {', '.join(plan.order)}")
        it = plan.items[pid]
        if not plan.tracker or "trow" not in it:
            sys.exit(f"{pid} has no tracker row.")
        c = plan.tcols[key]
        if c is None:
            if key == "started":
                print("(The tracker has no Started column; nothing to tick.)")
                _refresh_and_print(plan)
                return
            sys.exit("The tracker has no Done column.")
        if key == "started":
            missing = [n for n in it["needs"] if not plan.items[n]["done"]]
            busy = plan.state(pid)
            if missing:
                print(f"WARNING: {pid} needs {', '.join(missing)}, not done yet. Stop unless the person said to run it anyway.\n")
            elif busy[0] == "blocked":
                print(f"WARNING: {', '.join(busy[1])} is running and writes the same files as {pid}. "
                      "Stop unless the person said to run it anyway.\n")
        stamp = "[x] " + time.strftime("%m-%d %H:%M")
        plan.set_cell(it["trow"], c, stamp)
        it[key] = True
        it[key + "_at"] = stamp[4:]
        if key == "done":
            it["started"] = True
            if plan.tcols["started"] is not None and not re.search(r"\[[xX]\]", split_cells(plan.lines[it["trow"]])[plan.tcols["started"]] if plan.tcols["started"] < len(split_cells(plan.lines[it["trow"]])) else ""):
                if not it["you"]:
                    plan.set_cell(it["trow"], plan.tcols["started"], "[x]")
        _refresh_and_print(plan)


def cmd_log(a):
    with Lock(a.file):
        plan = Plan(a.file)
        text = "\n".join(plan.lines)
        i = text.find(LOG_END)
        if i < 0:
            sys.exit(f"No {LOG_END} marker; add the log section from the template.")
        row = f"| {time.strftime('%Y-%m-%d %H:%M')} | {a.id.upper()} | {' '.join(a.text).replace('|', '/')} |"
        text = text[:i] + row + plan.nl + text[i:]
        plan.lines = text.split("\n")
        plan.save()
        print("Logged: " + row)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("check"); s.add_argument("file"); s.add_argument("--fill", action="store_true"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("now"); s.add_argument("file"); s.add_argument("--write", action="store_true"); s.set_defaults(fn=cmd_now)
    s = sub.add_parser("start"); s.add_argument("file"); s.add_argument("id"); s.set_defaults(fn=lambda a: _tick(a, "started"))
    s = sub.add_parser("done"); s.add_argument("file"); s.add_argument("id"); s.set_defaults(fn=lambda a: _tick(a, "done"))
    s = sub.add_parser("log"); s.add_argument("file"); s.add_argument("id"); s.add_argument("text", nargs="+"); s.set_defaults(fn=cmd_log)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
