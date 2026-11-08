# docs

What happened in this repo and why, for people and coding agents. Start here, then read the active plan.

## Layout and rules
The layout and its rules are set in [ADR 0002](decisions/0002-docs-as-decision-record.md).

- `plans/` holds plans for multi-PR work, named `YYYY-MM-DD-topic.md`. A plan is a living document: each PR updates its progress table and any section the PR changes. A plan that is replaced wholesale stays unchanged, apart from a status line pointing at its successor.
- `decisions/` holds architecture decision records (ADRs), one decision per file, named `NNNN-topic.md`. An ADR is never edited after merge, except its status line. A changed decision gets a new ADR, and the old one is marked `Superseded by NNNN`.

A PR that makes or changes a decision adds the ADR and updates the active plan in the same PR.

### ADR template
ADRs are short. They state what was decided and why, not who decided it, how, or in which PR.

```md
# NNNN. Title stating the decision

- **Status:** Proposed | Accepted | Superseded by [NNNN](NNNN-topic.md)
- **Date:** YYYY-MM-DD

What was decided, specifically enough to check the code against.

**Why:** The reason, in a sentence or two.

**Consequences:** What gets harder, or has to happen next. Left out when obvious.
```

## Index

### Plans
| Plan | Status |
|---|---|
| [2026-11-08-human-o-matic](plans/2026-11-08-human-o-matic.md) | Active. The app, milestone by milestone. |

### Decisions
| # | Decision | Status |
|---|---|---|
| [0001](decisions/0001-python-312-with-uv-ruff-pyright-and-pytest.md) | Python 3.12 with uv, ruff, pyright and pytest | Accepted |
| [0002](decisions/0002-docs-as-decision-record.md) | docs/ is the decision record | Accepted |
| [0003](decisions/0003-branches-off-main-merged-without-squashing.md) | Work branches off `main` and merges without squashing | Accepted |
| [0004](decisions/0004-exact-dependency-versions.md) | Dependencies use exact versions | Accepted |
| [0005](decisions/0005-orchestrated-agents.md) | Claude Code works through an orchestrator, a developer and QA | Accepted |
| [0006](decisions/0006-settings-block-pushes-and-publishing.md) | Claude Code's settings block pushes and publishing | Accepted |
| [0007](decisions/0007-library-data-stays-out-of-the-repo.md) | Library data stays out of the repo | Accepted |
