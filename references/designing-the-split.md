# Designing the split

How to go from a brief to the fewest prompts that finish soonest, with no two sessions stepping on each other. Read before the first draft of the board.

## Contents
1. The method, step by step
2. How many prompts
3. Contracts that remove waiting
4. Single writers
5. The user's part (J-items)
6. The integrator (Q)
7. Two worked shapes (rounds 4 and 6)
8. Smells

## 1. The method

1. **List the deliverables.** Write down every concrete thing that must exist at the end (files, pages, accounts, records, videos, emails drafted), and next to each, what it writes: files and folders, a git working tree, a deploy target, an external system.
2. **List what each deliverable needs to know.** Needing a decision is not a dependency (§2 settles it in advance). Needing a *shape* is not a dependency either (§3 settles it; see section 3). Needing another deliverable's *content* is a real dependency.
3. **Group into work units** that share files, context and tools. Two deliverables that write the same file belong in one prompt unless one clearly follows the other.
4. **Assign IDs** by kind, so the board reads at a glance: letters for the kind of work, numbers within it (W1 words, R0 research, H1 a CRM, V1 video, B1 build, C1 cloud setup, K1 content, X1 data sources, Q the final check). The user's actions are J1, J2… Keep IDs short: the script treats any `A`–`Z` token up to 8 characters with a digit as an ID.
5. **Draw the needs** (real content dependencies only), then compute waves. `orch.py check` does it for you: wave = 1 + the deepest need.
6. **Shorten the longest chain.** The longest chain sets the finish date, and `check` prints it. For each link, ask: is this a real content need, or could a §3 contract or a §2 decision break it? Could the long prompt start earlier, or be split so its first half runs in wave 1?
7. **Check the fences.** Every prompt's "Writes" lists its paths in backticks. Two prompts with no needs between them and an overlapping path can't run together. Either that's right (the board then shows "one at a time, either order"), or make the paths precise (`portal/src/modules/data/` instead of `portal/`) so they can.

## 2. How many prompts

Each prompt costs a fresh session reading the rules, the plan and its sources (often 10 to 20 percent of its run), plus the user's time to paste and watch it. More prompts mean more parallelism, but also more overhead and more handoffs to get right.

- **Merge** a unit that's under about half an hour of agent work into the neighbour that shares the most context with it.
- **Split** a unit that needs two very different tool stacks (browser account work and code, video and copy), more than about a dozen heavy steps, or the user's presence partway through.
- **Typical counts:** 1 for a single coherent job (PROMPTS_5: one measurement prompt that touches the site, then ships); 3 to 7 for most rounds; up to about 12 for a round with several independent streams (PROMPTS_4, PROMPTS_6). Past 12, the brief is probably two rounds: plan the first and leave the second for a later round.
- State the reason in the file's first paragraph: "Split into eleven prompts because…".

## 3. Contracts that remove waiting

The single biggest win. When a builder needs only the *shape* of a writer's output, write the shape into §3 now, and they run side by side:

- **Round 4:** W2 wrote the intake's words, H1 built the CRM form, R0 researched the help text and B2 built the page. §3 fixed every field ID, type and period up front, so W2, R0 and H1 all ran in wave 1. Only B2 waited.
- **Round 6:** §4 of that file fixed the page file format, the front matter and the database rows, so three content writers (K1–K3), the platform (P1) and the compiler (R6) all ran in wave 1.

A contract is worth writing when two or more prompts would otherwise wait on each other only for names, IDs, fields, formats, slots or an interface. Keep it to exactly what both sides need. A session that finds the contract wrong logs it and follows rule 5; it never silently diverges.

## 4. Single writers

Some things only one session at a time may write:
- **A git working tree,** especially one where a push deploys (the kit's `site/`: "never two of B1, B2, B3 or Q at once"). Give every prompt that writes it the same backticked path. The board then serializes them, either with needs or as "one at a time".
- **Shared records** (the decision log, business context, a plan or status file, the kit's `BUILD-PLAN_1.md`): only the integrator edits them. Everyone else writes a handoff.
- **The PROMPTS file itself:** every session edits it, but only its own tracker row (through `orch.py`, which locks the file) and, under rule 5, single decision cells. That's safe by design and isn't listed in Writes.
- **External systems** where two sessions would edit the same object (one CRM form, one DNS zone) are single writers too: backtick a name for it, e.g. `HubSpot: contact form`. Where they edit different parts of one system, name the parts in plain words.

## 5. The user's part (J-items)

Anything only the user can do (sign in, approve an account's terms, add a card, supply a file, make a call, decide something that truly can't default) becomes:
- a §0 item, front-loaded, with how long it takes;
- a **J-item** on the board, if a prompt needs it done first. The prompt lists the J-ID in "Needs", and the box shows "→ unblocks H1".

Prefer a J-item before a prompt over a stop inside it. Sessions stop only for the allowed stops listed in rule 4 (a sign-in prompt mid-run, a payment screen, a download that needs a yes). When a prompt's paste is itself the approval (an account created, terms accepted), say so in its "Your part" box and its first paragraph, exactly as rounds 5 and 6 did.

## 6. The integrator (Q)

With three or more prompts, end with Q. It reads every handoff, runs the full checks (on production too, if anything shipped), fixes what it can inside the round's scope, writes the report card (`<handoff folder>/REPORT-CARD.md`: grades, what's left, the next ten things), and alone updates the shared records. In a project with a decision log, that means merging the results into it, with every §2 decision carried in as PROPOSED (the user's "Your call" entries as ACCEPTED, in their words). With one or two prompts, the last prompt does this itself.

## 7. Two worked shapes

**Round 4 (PROMPTS_4, the website, eleven prompts):** writers, research, CRM and video ran in wave 1, then builders chained on `site/`, then the check:

```
Wave 1:  W1  W2  R0  H1  V1          (words, intake words, research, HubSpot, video v2)
Wave 2:  B1 ← W1   ·   V2 ← V1   ·   V3 ← V1
Wave 3:  B2 ← B1, W2, R0, H1
Wave 4:  B3 ← B2, V1, V2, V3
Wave 5:  Q ← B3
```
`orch.py check` on that board finds one overlap the prose missed: V2 and V3 both write `inputs/audio/`. The fix is to write `inputs/audio/onboarding/` and `inputs/audio/weekly/`.

**Round 6 (PROMPTS_6, the team portal, twelve prompts):** the platform, cloud setup, three content writers, data sources and the refresh skill all ran in wave 1, because §3 and §4 fixed the access model and the content format. P1 left P2 and P3 their own folders, migrations and tests, so those two ran side by side:

```
Wave 1:  P1  C1  K1  K2  K3  X1  R6
Wave 2:  P2 ← P1   ·   P3 ← P1   ·   S1 ← C1
Wave 3:  I1 ← everything in waves 1 and 2 except S1
Wave 4:  Q6 ← I1
```
`check` finds that S1 (`tools/`) overlaps R6 and X1 (`tools/…`), so S1 can't run beside them as the prose said. Precise paths fix that.

## 8. Smells

- A prompt whose "Writes" says "various" or lists nothing: it has no fence.
- A wave 2 that's longer than wave 1 when the brief has independent streams: look for contracts.
- A prompt that stops halfway for the user: move that step to a J-item before it.
- Three prompts that each "update the docs": give the docs to Q.
- A decision the user is asked about in chat instead of in §2.
- A prompt named after a topic ("marketing") rather than a result ("the five outreach emails, drafted").
