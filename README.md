# orchestrate

A Claude Code skill that turns a big task into one central **PROMPTS file**: the "brain" for running a multi-prompt job across parallel Claude Code sessions.

The file tells you, at a glance:
- what to paste now,
- what runs at the same time and what waits on what,
- which decisions are already in force (each with a recommended default you can overrule),
- which skills each prompt uses, in order.

A small script (`scripts/orch.py`) writes a live "What to do now" box and ticks the tracker as sessions finish. `scripts/skills.py` surveys the installed skills and public catalogs and vets anything it installs.

## Install

Copy the `orchestrate` folder into a project's `.claude/skills/` (or into `~/.claude/skills/` for all projects). Scripts run with `python -P` and need no packages.

## Use

- `/orchestrate` with a brief: creates a new PROMPTS file.
- On an existing file: "what's next?", "A1 is done", "update the plan" keeps it current.

See `assets/PROMPTS_TEMPLATE.md` for the file format and `evals/` for example briefs.

## License

MIT. See `LICENSE`.
