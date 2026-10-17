# {{Round name}}: {{N}} prompts, {{K}} of them at once

{{Who asked for what, and when, in one or two sentences: the outcome when every prompt is done.}} Split into **{{N}} prompts** because {{the reason for this number in one line, e.g. "four kinds of work that touch different files run together, then one builder, then one check"}}. Paste each into a **new** Claude Code session started in `{{folder the sessions run in}}`, model **{{model}}, effort {{effort}}**. Everything inside a prompt's code block is what you paste. Read its "Your part" box first; most say "nothing".

<!-- orch:now:start -->
(orch.py fills this box)
<!-- orch:now:end -->

**How this file works.** The box above always says what to paste next. Each session updates it when it starts and again when it finishes, so you never have to tick anything. §0 is your part before you start. §1 is the board: what runs when, what runs together, and the rules every session follows. §2 holds every decision with the option in force. §3 is the shared spec the prompts build to. §4 has the prompts. §5 logs what changed along the way.

**Decisions don't wait for you.** Every session takes the recommended option in §2 unless you've written something in that row's "Your call" cell. It records anything new it had to decide in §5 and keeps going. To change a decision, edit its "Your call" cell before the prompts in its "Used by" column start, or tell any session. **What still waits for you:** {{what needs the person's OK under the repo's rules: sending, posting, publishing, buying, signing, new accounts. Name anything this file pre-approves (and that pasting the prompt is the approval), or write "nothing else".}}

---

## 0. Before you start (your part, about {{N}} minutes)

1. **Your actions.** {{Each J-item from the board: what, where, about how long, and which prompt it unblocks. Put every sign-in, approval and file the prompts need here, so no prompt has to stop midway. If there are none: "None: paste wave 1 now."}}
2. **Decisions worth a glance** (each already has a default in §2): {{the two to five with the biggest consequences, one line each: the ID, the question, the recommended option.}}
3. **Skills.** {{Skills installed today from the catalogs: name, where from, "read in full before installing". Then "everything else the prompts name is already installed". Nothing to run.}}
4. **Running a prompt:** start a new session in `{{folder}}` ({{model}}, {{effort}}) and paste the code block. If a session stops to ask you something, it's one of the allowed stops in §1 rule 4: answer it, then paste "continue".

---

## 1. The board

### Waves

<!-- orch:waves:start -->
(orch.py fills this from the table below)
<!-- orch:waves:end -->

### Who runs when

| ID | Prompt | Needs (done first) | Runs at the same time as | Writes (only these) |
|---|---|---|---|---|
| **A1** | {{What A1 makes, in plain words}} | — | (orch.py fills this) | `{{path A1 owns}}`, `{{handoff folder}}/A1-handoff.md` |
| **A2** | {{What A2 makes}} | — | (orch.py fills this) | `{{path A2 owns}}`, `{{handoff folder}}/A2-handoff.md` |
| **J1** | **You:** {{the action, e.g. sign in to HubSpot in Chrome}} | — | — | — |
| **B1** | {{What B1 builds from A1 and A2}} | A1, A2, J1 | (orch.py fills this) | `{{path B1 owns}}`, `{{handoff folder}}/B1-handoff.md` |
| **Q** | The check: every handoff read, the full checks run, fixes, the report card, and the results merged into the project's records | B1 | (orch.py fills this) | `{{shared docs only Q edits}}`, `{{handoff folder}}/Q-handoff.md` |

**Needs** lists the IDs that must be done first: prompts, or your actions (J). **Writes** puts in backticks every file or folder that only this prompt may write while it runs. If two prompts list the same path, the board never runs them at the same time. Systems that several prompts touch in different places, like a CRM or a cloud account, are named in plain words, with the part each prompt changes.

### Tracker

Sessions keep this table current themselves (`orch.py start` and `orch.py done`). Mark your own actions (J) by telling any session "J1 done", or by running the command shown at the bottom of the box at the top.

| ID | State | Started | Done | Notes |
|---|---|---|---|---|
| A1 | | [ ] | [ ] | |
| A2 | | [ ] | [ ] | |
| J1 | | — | [ ] | |
| B1 | | [ ] | [ ] | |
| Q | | [ ] | [ ] | |

### Rules for every session

1. **Read first, every time:** {{the repo's CLAUDE.md (it loads itself)}}, this file's §1, §2, §3 and your own prompt, and the files your prompt lists. Where an earlier round disagrees with this file, this file wins.
2. **Start and finish with the tracker.** Your first command is `python -P {{script path}} start {{FILE}} <your ID>`, and your last is `python -P {{script path}} done {{FILE}} <your ID>`. End your final message with the "What to do now" box that `done` prints, so {{person}} sees what to paste next.
3. **Write only what your row lists.** Your row's "Writes" cell is your fence. Stage only your own paths: `git add <path> …`, never `git add -A`, `git add .`, `git commit -a` or `git stash`. If `git status` shows another session's files, leave them alone. If something outside your fence needs a change, don't make it. Write it in your handoff for the prompt that owns that path, or for Q.
4. **Decisions in force are in §2.** If you hit a choice §2 doesn't settle, take the best option, note it under "Decided" in your handoff (with the alternative and why), log it with `orch.py log`, and keep going. **The allowed stops, and nothing else:** {{e.g. a sign-in or two-step prompt; a payment screen; a download that needs a yes}}. Anything else: finish, hand off, stop.
5. **Updating a decision as you go.** If your work shows a recommendation is wrong for a prompt that hasn't started, re-read this file and edit only that row's "Recommended" cell, as "~~old wording~~ → new wording (<ID>, <date>: why)". Then log it. Never touch a "Your call" cell. If a running or finished prompt already used the decision, don't change it: log the conflict for Q.
6. **Nothing goes out in {{person}}'s name** beyond what §0 approves: no sending, posting, publishing, buying, signing or scheduling.
7. **Long jobs** (builds, renders, test suites, uploads) run in the background. A session never stops early because something is slow.
8. **Handoff:** `{{handoff folder}}/<ID>-handoff.md` covers what you changed (files, commits), what you decided and the alternative, what you found outside your scope, anything {{person}} must do, and what the prompts after you need. Then `orch.py done`, paste the box, and stop.
9. {{The repo's own rules these prompts could break, one line each, copied from its CLAUDE.md: e.g. no personal data in shared files; honest claims; free first; the push rule; legal wording "verify with counsel".}}

---

## 2. Decisions ({{P}}-1 to {{P}}-{{n}})

Each row's **Recommended** option is in force unless **Your call** says otherwise. The prompts read this table; rule 5 says how a session updates a row.

| # | Question | Recommended (in force) | Alternatives considered | Used by | Your call |
|---|---|---|---|---|---|
| {{P}}-1 | **{{The question in a few words}}** | **{{The option, concrete enough to act on}}.** {{Why, in one or two sentences.}} | {{Option}} (rejected: {{why}}) · {{Option}} (rejected: {{why}}) | A1, B1 | |

---

## 3. {{The shared spec}}

{{The contract that lets prompts run in parallel instead of in a line: the IDs, names, fields, file formats, word slots or interfaces both sides build to. Delete this section if no two prompts share anything.}}

---

## 4. The prompts

### A1: {{short name}} ({{model}}, {{effort}})

> **Your part:** nothing.
>
> **Skills, in order of use:** `{{skill}}` ({{when, what for}}) → `{{skill}}` ({{when}}) → `{{skill}}` ({{when}})

```
You're {{doing what}} for {{project}} ({{round}}, prompt A1 of {{N}}; {{FILE}}). Your job is {{scope}} only: {{deliverables}}. You write only {{paths}}; {{adjacent things}} belong to {{other IDs}}. {{Other IDs}} may run beside you, so stage only your own files. The decisions are in {{FILE}} §2: take the recommended option wherever "Your call" is empty, and don't wait for {{person}}.

First: python -P {{script path}} start {{FILE}} A1

Read first: {{specific files and the sections that matter}}.

Skills, in this order: 1. {{skill}}, {{when and what for}}. 2. {{skill}}, {{when}}. 3. {{skill}}, {{when}}.

1. {{Step with a concrete result: file, section, IDs, acceptance.}}
2. {{…}}
3. Checks: {{commands that must pass, or what to verify and how}}.
4. Handoff: {{handoff folder}}/A1-handoff.md with what you changed, what you decided and the alternative, anything outside your scope, what {{person}} must do, and what {{next IDs}} need from you. Commit your own files only. Then run python -P {{script path}} done {{FILE}} A1, end your message with the box it prints, and stop.
```

{{…one section per prompt, in board order…}}

---

## 5. Log

What changed along the way: decisions updated, new decisions, conflicts for Q. Sessions add rows with `orch.py log`; you can add one by hand.

| When | Who | What changed |
|---|---|---|
<!-- orch:log:end -->
