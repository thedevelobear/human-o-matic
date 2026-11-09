# Agent instructions

human-o-matic is an MCP server that re-performs a drum MIDI file section by section, steered by the user's answers to questions the connected agent asks. Use `human-o-matic` for the repo, distribution, CLI and skill, and `human_o_matic` for the Python package. The work is planned milestone by milestone in the [plan](docs/plans/2026-11-08-human-o-matic.md).

## Before you start
1. Read [`docs/README.md`](docs/README.md), then the active plan, and the milestone you are on.
2. Check [`docs/decisions/`](docs/decisions/) for anything your change touches. Don't silently re-decide something recorded there. If a decision needs to change, propose a new ADR.

## Starting a branch
Every change is a branch made from `main`, merged into it through a PR ([ADR 0003](docs/decisions/0003-branches-off-main-merged-without-squashing.md)).
1. Run `git fetch`. If your work already has a branch, continue on it. Otherwise create one from `main` without tracking it, named after the change's main commit type and its topic:
   ```sh
   git switch --no-track -c feat/topic origin/main
   ```
   Without `--no-track`, git makes `main` the branch's upstream. A plain push, including VS Code's Push button, then lands the commits on `main` with no PR. The owner pushes a branch, outside Claude Code, with `git push -u origin feat/topic`. Agents can't push: Claude Code's settings block it ([ADR 0006](docs/decisions/0006-settings-block-pushes-and-publishing.md)).
2. Bring the docs up to date with what has merged, in the first commit of the new branch. Set any ADR left as "Proposed" by a merged PR to "Accepted" (unless the owner changed it), and mark a milestone the plan lists as "In review" as "Merged".
3. When the work is done, stop and report to the owner. Open a PR only when the owner asks, once the branch is pushed.

## Work milestone by milestone
The plan's milestones, M0 to M6, are done in order, each in one or more PRs.
1. Find the first milestone in the plan's progress table that isn't merged, and start or continue its branch as above.
2. Before writing code, ask the owner what the plan leaves open for this milestone. Record each answer as an ADR.
3. **Stop at each gate.** Check the milestone's exit criteria and report them. The next milestone starts only when the owner says so. No agent can hear the output, so every listening decision, such as the M4 blind test and the M5 comparison, belongs to the owner.
4. Some inputs only the owner can supply: the hand-labelled drum tracks for M2, the listening tests, and the call on M6's priority. Ask for them, and don't work around them.
5. When the milestone's PR is done, set its status to "In review".

## While you work
- Record decisions and plan changes in `docs/`, in the same PR as the code: a new ADR for each decision, and an update to the plan's progress table and to any section the work changes. Nothing that matters should live only in chat or in PR comments.
- ADRs and docs state what was decided and why, briefly. They don't say who decided or asked, retell how a decision was reached, or name the PR something happened in. Only the plan's progress table links PRs.
- In Claude Code, sessions start with the `orchestrator` agent (`.claude/settings.json`). It sends the work to the `developer` agent and has the `qa` agent run every check and review the result at the end ([ADR 0005](docs/decisions/0005-orchestrated-agents.md)). The agents are in `.claude/agents/`. Keep them true when the process changes.
- If something is unclear, or the plan contradicts itself, ask the owner before deciding.
- PRs are merged without squashing. Commits are small, focused steps, and only the branch's tip has to pass the checks ([ADR 0003](docs/decisions/0003-branches-off-main-merged-without-squashing.md)).
- Dependencies use exact versions, and `uv add` writes them that way ([ADR 0004](docs/decisions/0004-exact-dependency-versions.md)).

## Rules from the plan
- No DAW bridge, web UI or built-in LLM in this version.
- Never pass note arrays through MCP tools: pass IDs and file paths, and return compact JSON.
- Don't train a model before M4 exists.
- Never commit anything in `private/`, copy anything out of it into the repo, or redistribute it ([ADR 0007](docs/decisions/0007-local-only-files-live-in-private.md)).
- Maps are built in: this version loads no user-supplied map file ([ADR 0010](docs/decisions/0010-built-in-maps-only.md)).
- No library is special in the code. Libraries differ only in their map data ([ADR 0008](docs/decisions/0008-library-neutral-drum-maps.md)).
- Timing never exceeds performed magnitudes by default.
- No piano or guitar logic yet.

## Code
- Python 3.12, a `src/` layout, and pyright in strict mode on `src/` ([ADR 0001](docs/decisions/0001-python-312-with-uv-ruff-pyright-and-pytest.md)).
- Rendering is deterministic. Draw randomness only from a `numpy.random.Generator` built from a `SeedSequence`, one stream per section, and never from `random` or numpy's global state. The same session and seed must give the same file.
- Tests are `pytest`, with `hypothesis` for the plan's property tests. A test builds the MIDI it needs in code, in `tmp_path`. A test that needs the local-only files in `private/` is marked `@pytest.mark.private` and skips when they are missing.

## Commands
`uv` is installed in `~/.local/bin`, and the Python version comes from `.python-version`.

| Command | What it does |
|---|---|
| `uv sync` | Install dependencies into `.venv`. |
| `uv run ruff check` | Lint, including import order. |
| `uv run ruff format` | Write formatting. Add `--check` to only check. |
| `uv run pyright` | Type-check `src/` strictly and `tests/` in standard mode. |
| `uv run pytest` | All tests. The private ones skip when `private/` is missing. |
| `uv run pytest -m "not private"` | The tests CI runs. |
| `HYPOTHESIS_PROFILE=ci uv run pytest` | The property tests with CI's example count. |
| `uv run python tools/infer_map.py` | Pitch statistics for each folder of performed MIDI in `private/midi/`, read through its kit ([ADR 0057](docs/decisions/0057-each-folder-s-kit-is-in-a-gitignored-file-under-private-data.md)). `--map LIBRARY[/KIT]` reads through another. |
