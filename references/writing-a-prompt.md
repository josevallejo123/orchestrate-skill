# Writing a prompt

Every prompt is pasted into a brand-new session that has never seen this conversation. It has the repo, the PROMPTS file and the text you give it, nothing else. So a prompt succeeds when a capable stranger could do the job from it alone, and knows exactly where their job ends.

## The section, outside the code block

```markdown
### B2: build the intake page (Opus 5.5, Max)

> **Your part:** nothing. (Or the one thing the user does, when, and how long it takes. If pasting is itself an approval, say exactly what it approves.)
>
> **Skills, in order of use:** `signup-flow-cro` (the step order, before any code) → `form-cro` (each step's fields and errors) → `frontend-design` → `accessibility-auditor` (over the built page) → `code-review` (high, over the diff)
```

- The heading is `### <ID>: <short name> (<model>, <effort>)`. `orch.py` finds prompts by `### <ID>:`.
- **Your part** is what the user does for this prompt. Most say "nothing". Long-running prompts say "start this one first".
- **Skills, in order of use** uses backticked names exactly as the skills list shows them (`hubspot-sales:hubspot`, `cloudflare:wrangler`), each with when or what for in parentheses. Put arguments outside the backticks: `code-review` (high). Tools that aren't skills (Claude in Chrome, a connector, WebSearch) are written plainly, without backticks. `orch.py check` warns about any backticked name that isn't installed.

## The code block: the skeleton

```
You're <doing what> for <project> (<round>, prompt <ID> of <N>; <FILE>). Your job is <scope> only: <deliverables>. You write only <paths>; <adjacent things> belong to <IDs>. <IDs> may run beside you, so stage only your own files. The decisions are in <FILE> §2: take the recommended option wherever "Your call" is empty, and don't wait for <person>.

First: python -P <script path> start <FILE> <ID>

Read first: <file> (<the sections that matter>); <file>; <file> <section>.

Skills, in this order: 1. <skill>, <when and what for>. 2. <skill>, <when>. 3. <skill>, <when>.

1. <A step with a concrete result.>
2. …
N-1. Checks: <the commands that must pass, or what to verify and how>.
N. Handoff: <handoff folder>/<ID>-handoff.md with what you changed (files, commits), what you decided and the alternative, anything outside your scope, what <person> must do, and what <next IDs> need from you. Commit your own files only. Then run python -P <script path> done <FILE> <ID>, end your message with the box it prints, and stop.
```

## What makes the difference

- **The first paragraph is the contract.** It names the scope, the fence (what it writes, and who owns the neighbours) and the parallel siblings. Rounds 4 to 6 opened every prompt this way, and it's why their sessions didn't collide.
- **Read first is specific.** "BUILD-PLAN_1.md 'Locked' and 'Rules for every agent'", not "read the docs". Name the sections. Name the decisions by ID instead of restating them; §2 stays the single source.
- **Steps produce things.** Each step names its output (a file, a section key, a record, a commit) and the bar it must clear. "Write content/COPY-INTAKE.md with these sections…" beats "write the intake copy".
- **Say the why when a mistake would be costly.** One clause is enough: "never embed the scheduler: it sets cookies and the privacy policy says the site sets none".
- **Name the allowed stops** for this prompt, if it has any beyond rule 4, and the fallback for each foreseeable blocker ("if the plan allows only one meetings link, use the existing link with the 24-hour notice, note it, and keep going"). Fallbacks are how the round 4 prompts finished without stopping.
- **Checks are commands** when the repo has them (`node tools/copy-check.mjs --deck`). Otherwise give an explicit verification: what to open and what must be true.
- **Pre-approvals are explicit.** If pasting the prompt approves an action the house rules normally hold (creating accounts, accepting terms, pushing), the first paragraph lists exactly those actions, as PROMPTS_5's M1 and PROMPTS_6's C1 do. Anything not listed still waits.
- **Long work runs in the background**, and the prompt says so where it applies (renders, test matrices, uploads).
- **The last step is always the handoff, then `orch.py done`, then the box, then stop.** The box at the end of each session is how the user learns what to paste next without opening the file.

## The integrator's prompt (Q)

Q's prompt adds: read every handoff in `<handoff folder>/`; run the whole check suite (and production checks if anything shipped); fix inside the round's scope, one writer at a time; write `REPORT-CARD.md` (each prompt graded, what's left, the next ten things, the user's to-dos); update the shared records the house way (for example: write a note for the project's inbox and merge it into its records; carry each §2 decision into the decision log as PROPOSED, and the user's "Your call" entries as ACCEPTED in their words; log the changelog and run-log rows); add the round to the folder's `CLAUDE.md` file list if it keeps one. Q's "Writes" cell owns those shared files.

## Length

A prompt is as long as it needs to be to stand alone: usually 150 to 600 words in the block. Spend the words on files, fences, steps and checks, not on exhortation. If a prompt passes about 900 words, it's probably two prompts, or it's restating §2 or §3, which it should cite instead.
