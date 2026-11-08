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
| [0007](decisions/0007-local-only-files-live-in-private.md) | Local-only files live in `private/`, which is never committed | Accepted |
| [0008](decisions/0008-library-neutral-drum-maps.md) | Drum maps are library-neutral: library, kit and articulation | Proposed |
| [0009](decisions/0009-m1-resolves-notes-channels-and-velocity-ranges.md) | M1 resolves notes, channels and velocity ranges, and CC-driven articulations wait for M3 | Proposed |
| [0010](decisions/0010-built-in-maps-only.md) | Maps are built in, and this version loads no user-supplied map file | Proposed |
| [0011](decisions/0011-m1-maps-for-general-midi-and-drum-libraries.md) | M1 ships a General MIDI map and maps for ten drum libraries | Proposed |
| [0012](decisions/0012-runtime-dependencies-arrive-with-their-milestone.md) | M1 adds mido, numpy, pydantic and typer, and other runtime dependencies wait for their milestone | Proposed |
| [0013](decisions/0013-midi-is-read-into-notes-and-raw-events.md) | MIDI files are read into paired notes and raw events at absolute ticks | Proposed |
| [0014](decisions/0014-work-at-a-whole-multiple-of-the-source-ppq.md) | Songs are worked on and written at the smallest multiple of their PPQ that is at least 960 | Proposed |
| [0015](decisions/0015-unclear-input-is-a-decision-request.md) | Unclear input is a decision request, raised as `DecisionRequired` | Proposed |
| [0016](decisions/0016-tempo-and-time-signatures.md) | Tempo and time signatures come from every track, and a missing tempo is asked for | Proposed |
| [0017](decisions/0017-the-drums-are-one-whole-track.md) | The drums are one whole track, chosen by rules in turn | Proposed |
| [0018](decisions/0018-mido-is-typed-by-a-local-stub.md) | mido is typed by a local stub in `typings/` | Proposed |
| [0019](decisions/0019-canonical-names-follow-one-grammar.md) | Canonical articulation names follow one grammar, kept in a vocabulary file | Proposed |
| [0020](decisions/0020-map-files-are-toml-checked-when-they-load.md) | A map file is one library in TOML, and an ambiguous map fails to load | Proposed |
| [0021](decisions/0021-conversion-falls-back-within-a-family.md) | Conversion falls back within a family, and asks instead of changing family | Proposed |
| [0022](decisions/0022-the-general-midi-map-follows-the-standard.md) | The General MIDI map follows the GM Level 1 percussion key map | Proposed |
| [0023](decisions/0023-built-in-library-ids.md) | Built-in libraries have short kebab-case ids | Proposed |
| [0024](decisions/0024-built-in-data-is-found-beside-the-source.md) | Built-in data is found in `data/` beside the source, by one function | Proposed |
| [0025](decisions/0025-proposed-names-ship-at-low-confidence.md) | A proposed name ships at low confidence, and only a check raises it | Proposed |
| [0026](decisions/0026-a-grid-per-beat-by-timing-error-and-complexity.md) | Each beat takes one of four grids, by its timing error in milliseconds plus a complexity penalty | Proposed |
