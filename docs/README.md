# docs

What happened in this repo and why, for people and coding agents. Start here, then read the active plan.

## Layout and rules
The layout and its rules are set in [ADR 0002](decisions/0002-docs-as-decision-record.md), and `research/` in [ADR 0072](decisions/0072-docs-research-holds-published-measurements-compared-with-the-project-s-values.md).

- `plans/` holds plans for multi-PR work, named `YYYY-MM-DD-topic.md`. A plan is a living document: each PR updates its progress table and any section the PR changes. A plan that is replaced wholesale stays unchanged, apart from a status line pointing at its successor.
- `decisions/` holds architecture decision records (ADRs), one decision per file, named `NNNN-topic.md`. An ADR is never edited after merge, except its status line. A changed decision gets a new ADR, and the old one is marked `Superseded by NNNN`, or `Accepted. Its <part> is amended by NNNN` when the new ADR changes only part of it ([ADR 0042](decisions/0042-a-partly-changed-adr-is-marked-amended.md)).
- `research/` holds pages that compare the project's values with published measurements, named `YYYY-MM-DD-topic.md`. A page cites each source in full, with what it gives, how sure it is and what it can't say, lists the sources it couldn't open, with no figures from them, and holds published figures and aggregate values only ([ADR 0007](decisions/0007-local-only-files-live-in-private.md)). A page is as of its date: a wrong figure is corrected, and a later look is a new page.

A PR that makes or changes a decision adds the ADR and updates the active plan in the same PR.

### ADR template
ADRs are short. They state what was decided and why, not who decided it, how, or in which PR.

```md
# NNNN. Title stating the decision

- **Status:** Proposed | Accepted | Accepted. Its <part> is amended by [ADR NNNN](NNNN-topic.md) | Superseded by [NNNN](NNNN-topic.md)
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

### Research
| Page | Compares |
|---|---|
| [2026-11-10-styles-against-published-measurements](research/2026-11-10-styles-against-published-measurements.md) | Six values of the styles, where the fit and Appendix A's placeholder differ, with published measurements of drummers |
| [2026-11-11-rider-noise-against-published-measurements](research/2026-11-11-rider-noise-against-published-measurements.md) | The riders' velocity noise and their alternation, where the fit and Appendix A differ, with published measurements of a hi-hat and of ride cymbals |

### Decisions
| # | Decision | Status |
|---|---|---|
| [0001](decisions/0001-python-312-with-uv-ruff-pyright-and-pytest.md) | Python 3.12 with uv, ruff, pyright and pytest | Accepted. Its line that pyright is strict on `src/` is amended by [ADR 0058](decisions/0058-tools-are-scripts-checked-like-src.md) |
| [0002](decisions/0002-docs-as-decision-record.md) | docs/ is the decision record | Accepted. Its rule for a changed decision is amended by [ADR 0042](decisions/0042-a-partly-changed-adr-is-marked-amended.md), and its layout by [ADR 0072](decisions/0072-docs-research-holds-published-measurements-compared-with-the-project-s-values.md) |
| [0003](decisions/0003-branches-off-main-merged-without-squashing.md) | Work branches off `main` and merges without squashing | Accepted |
| [0004](decisions/0004-exact-dependency-versions.md) | Dependencies use exact versions | Accepted |
| [0005](decisions/0005-orchestrated-agents.md) | Claude Code works through an orchestrator, a developer and QA | Accepted |
| [0006](decisions/0006-settings-block-pushes-and-publishing.md) | Claude Code's settings block pushes and publishing | Accepted |
| [0007](decisions/0007-local-only-files-live-in-private.md) | Local-only files live in `private/`, which is never committed | Accepted |
| [0008](decisions/0008-library-neutral-drum-maps.md) | Drum maps are library-neutral: library, kit and articulation | Accepted |
| [0009](decisions/0009-m1-resolves-notes-channels-and-velocity-ranges.md) | M1 resolves notes, channels and velocity ranges, and CC-driven articulations wait for M3 | Accepted. Its line that controllers are resolved in M3 is amended by [ADR 0053](decisions/0053-a-controller-bound-note-keeps-its-controller-value.md) |
| [0010](decisions/0010-built-in-maps-only.md) | Maps are built in, and this version loads no user-supplied map file | Accepted |
| [0011](decisions/0011-m1-maps-for-general-midi-and-drum-libraries.md) | M1 ships a General MIDI map and maps for ten drum libraries | Accepted. Its list of libraries is amended by [ADR 0055](decisions/0055-m3-adds-maps-for-four-drum-libraries.md), and its line that every library but one has one kit by [ADR 0066](decisions/0066-sleep-token-ii-gets-an-inferred-groove-pack-kit.md) |
| [0012](decisions/0012-runtime-dependencies-arrive-with-their-milestone.md) | M1 adds mido, numpy, pydantic and typer, and other runtime dependencies wait for their milestone | Accepted. Its line on `scipy` is amended by [ADR 0041](decisions/0041-m2-adds-no-runtime-dependency.md), its line on `symusic` by [ADR 0056](decisions/0056-the-calibration-tools-add-no-dependency.md), and its line on `python-rtmidi` by [ADR 0074](decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md) |
| [0013](decisions/0013-midi-is-read-into-notes-and-raw-events.md) | MIDI files are read into paired notes and raw events at absolute ticks | Accepted |
| [0014](decisions/0014-work-at-a-whole-multiple-of-the-source-ppq.md) | Songs are worked on and written at the smallest multiple of their PPQ that is at least 960 | Accepted |
| [0015](decisions/0015-unclear-input-is-a-decision-request.md) | Unclear input is a decision request, raised as `DecisionRequired` | Accepted |
| [0016](decisions/0016-tempo-and-time-signatures.md) | Tempo and time signatures come from every track, and a missing tempo is asked for | Accepted |
| [0017](decisions/0017-the-drums-are-one-whole-track.md) | The drums are one whole track, chosen by rules in turn | Accepted |
| [0018](decisions/0018-mido-is-typed-by-a-local-stub.md) | mido is typed by a local stub in `typings/` | Accepted |
| [0019](decisions/0019-canonical-names-follow-one-grammar.md) | Canonical articulation names follow one grammar, kept in a vocabulary file | Accepted. Its list of variant kinds is amended by [ADR 0062](decisions/0062-the-vocabulary-adds-damped-strokes-wires-off-and-crash-tips.md) |
| [0020](decisions/0020-map-files-are-toml-checked-when-they-load.md) | A map file is one library in TOML, and an ambiguous map fails to load | Accepted |
| [0021](decisions/0021-conversion-falls-back-within-a-family.md) | Conversion falls back within a family, and asks instead of changing family | Accepted. Its wait for controllers in M3 is amended by [ADR 0053](decisions/0053-a-controller-bound-note-keeps-its-controller-value.md) |
| [0022](decisions/0022-the-general-midi-map-follows-the-standard.md) | The General MIDI map follows the GM Level 1 percussion key map | Accepted |
| [0023](decisions/0023-built-in-library-ids.md) | Built-in libraries have short kebab-case ids | Accepted. Its list of ids is amended by [ADR 0055](decisions/0055-m3-adds-maps-for-four-drum-libraries.md), and its library with several kits by [ADR 0066](decisions/0066-sleep-token-ii-gets-an-inferred-groove-pack-kit.md) |
| [0024](decisions/0024-built-in-data-is-found-beside-the-source.md) | Built-in data is found in `data/` beside the source, by one function | Accepted |
| [0025](decisions/0025-proposed-names-ship-at-low-confidence.md) | A proposed name ships at low confidence, and only a check raises it | Accepted |
| [0026](decisions/0026-a-grid-per-beat-by-timing-error-and-complexity.md) | Each beat takes one of four grids, by its timing error in milliseconds plus a complexity penalty | Accepted. Its choice of a beat's onsets is amended by [ADR 0086](decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md) |
| [0027](decisions/0027-hits-on-one-drum-under-45-ms-apart-are-a-grace-and-its-main.md) | Two hits on one drum from 5 ms to under 45 ms apart are a grace and its main, unless the gap is a grid step | Accepted |
| [0028](decisions/0028-limbs-within-20-ms-share-a-grid-point.md) | Hits on different drums within 20 ms, or half a 32nd at a fast tempo, share one grid point | Accepted |
| [0029](decisions/0029-unclear-beats-are-one-ambiguous-bars-request.md) | A beat whose grid is unclear keeps its best guess, and all of them are one `ambiguous_bars` request | Accepted |
| [0030](decisions/0030-hit-types-cluster-each-familys-velocities.md) | Hit types come from clear groups in each family's velocities, and anything else is normal and asked about | Accepted |
| [0031](decisions/0031-the-score-is-frozen-canonical-hits-with-their-source-notes.md) | The score is frozen canonical hits on a grid that keep their source notes | Accepted. Its wait for controllers in M3 is amended by [ADR 0053](decisions/0053-a-controller-bound-note-keeps-its-controller-value.md) |
| [0032](decisions/0032-bpm-is-the-only-tempo-a-user-gives.md) | `bpm` is the only tempo a user gives, and there is no `tempo_map` argument | Accepted |
| [0033](decisions/0033-analyze-takes-flags-and-an-answers-file-and-prints-json.md) | `human-o-matic analyze` takes flags and an answers file, and prints a summary and the requests as JSON | Accepted. Its printed line is amended by [ADR 0040](decisions/0040-analyze-prints-the-sections-and-its-exit-codes-stay.md) |
| [0034](decisions/0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md) | The M2 exit is scored on hand-labelled section starts in `private/labels/` | Accepted |
| [0035](decisions/0035-m2-finds-the-sections-and-their-facts-wait-for-m4.md) | M2 finds the sections, and their facts and ASCII pattern wait for M4 | Accepted |
| [0036](decisions/0036-a-bar-is-its-onset-pattern-in-each-family.md) | A bar is its onset pattern in each drum family, and bars are as alike as the cosine of their patterns | Accepted |
| [0037](decisions/0037-boundaries-are-novelty-peaks-that-favour-4-8-and-16-bar-sections.md) | Boundaries are novelty peaks chosen to favour 4, 8 and 16 bar sections, and a long silence is a section of its own | Accepted |
| [0038](decisions/0038-a-section-joins-the-repeat-group-it-plays-most-like.md) | A section joins the repeat group it plays most like, from 0.8, and groups are named A, B, C in song order | Accepted |
| [0039](decisions/0039-smf-markers-start-sections-at-the-nearest-bar-line.md) | An SMF marker starts a section at the nearest bar line, and markers win when one starts a section | Accepted |
| [0040](decisions/0040-analyze-prints-the-sections-and-its-exit-codes-stay.md) | `human-o-matic analyze` prints the sections beside the summary, and its exit codes stay | Accepted |
| [0041](decisions/0041-m2-adds-no-runtime-dependency.md) | M2 adds no runtime dependency, and `scipy` waits for code that imports it | Accepted |
| [0042](decisions/0042-a-partly-changed-adr-is-marked-amended.md) | An accepted ADR that a later one changes in part is marked amended | Accepted |
| [0043](decisions/0043-m3-is-three-prs-and-its-gate-follows-the-third.md) | M3 is three PRs, the engine, calibration and preview, and its gate follows the third | Accepted. Its third PR is amended by [ADR 0074](decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md) |
| [0044](decisions/0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md) | M3 ships the styles `tight`, `medium` and `loose` only, pooled by tightness band, with no named or numbered drummers | Accepted. What counts as one source is amended by [ADR 0063](decisions/0063-a-pack-is-a-source.md), and the fitting of each style's velocities on its own band by [ADR 0065](decisions/0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md) |
| [0045](decisions/0045-the-engine-is-render-modules-behind-a-small-instrument-seam.md) | The engine is a set of render modules behind a small instrument seam | Accepted. Its line on `preview.py` is amended by [ADR 0074](decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md) |
| [0046](decisions/0046-controls-are-layered-pydantic-models-with-a-json-round-trip.md) | The controls are layered pydantic models with a JSON round trip | Accepted. Its `tight`-only style is amended by [ADR 0070](decisions/0070-the-engine-reads-the-styles-from-data-styles.md) |
| [0047](decisions/0047-roles-come-from-canonical-families-and-the-score.md) | Roles come from canonical families and the score, never from a pitch | Accepted |
| [0048](decisions/0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md) | A render writes the score through the target kit into the drum track, and nothing else changes | Accepted |
| [0049](decisions/0049-each-section-draws-from-its-own-seeded-stream.md) | Each section draws from its own seeded stream, and the song's drifts from streams of their own | Accepted |
| [0050](decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md) | The guards hold every backend's draws, and never make a section depend on another's | Accepted. Its same-pitch gap is amended by [ADR 0073](decisions/0073-the-gap-is-counted-in-milliseconds-through-the-tempo-map.md) |
| [0051](decisions/0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md) | The `tight` style's placeholders are Appendix A with the values it leaves out filled in | Accepted. Its rendering from the placeholders is amended by [ADR 0070](decisions/0070-the-engine-reads-the-styles-from-data-styles.md), its values, where fitted, by [ADR 0068](decisions/0068-what-calibration-fits-and-what-stays-modelled.md), and its rider row near 127 by [ADR 0077](decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md) |
| [0052](decisions/0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md) | Each control is tested against the statistic it mainly drives, and the plan's properties have exact definitions | Accepted. Its `feel` row's smaller pushed side is amended by [ADR 0071](decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md), its same-pitch and cap properties by [ADR 0073](decisions/0073-the-gap-is-counted-in-milliseconds-through-the-tempo-map.md), and its gate after the preview PR by [ADR 0074](decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md) |
| [0053](decisions/0053-a-controller-bound-note-keeps-its-controller-value.md) | A controller-bound note keeps its controller value, and following and writing controllers wait for a map that gives them | Accepted |
| [0054](decisions/0054-human-o-matic-render-writes-a-new-midi-file-by-a-plan-and-prints-json.md) | `human-o-matic render` writes a new MIDI file by a plan, and prints its summary and each section's statistics as JSON | Accepted. Its `--style` taking only `tight` is amended by [ADR 0070](decisions/0070-the-engine-reads-the-styles-from-data-styles.md), and its summary by [ADR 0075](decisions/0075-render-s-summary-counts-how-the-notes-were-placed-in-the-target-kit.md) |
| [0055](decisions/0055-m3-adds-maps-for-four-drum-libraries.md) | M3 adds maps for Counterkit, NI Drum Lab, Krimh Drums and GGD Matt Halpern Signature Pack | Accepted |
| [0056](decisions/0056-the-calibration-tools-add-no-dependency.md) | The calibration tools add no dependency, and `symusic` is not used | Accepted. Its line on `python-rtmidi` is amended by [ADR 0074](decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md) |
| [0057](decisions/0057-each-folder-s-kit-is-in-a-gitignored-file-under-private-data.md) | The kit that reads each folder of performed MIDI is in a gitignored file under `private/data/` | Accepted |
| [0058](decisions/0058-tools-are-scripts-checked-like-src.md) | Tracked tools are scripts in `tools/`, checked as strictly as `src/`, and tested from `tests/` | Accepted |
| [0059](decisions/0059-calibration-measures-files-in-windows-of-at-most-16-bars.md) | Calibration measures each file in windows of at most 16 bars, around what the file leaves open | Accepted |
| [0060](decisions/0060-a-groove-held-to-the-grid-is-left-out-of-timing.md) | A groove held to the grid is left out of the timing statistics | Accepted |
| [0061](decisions/0061-calibration-measures-the-engine-s-statistics-with-feel-against-the-kick.md) | Calibration measures the engine's statistics, with feel taken against the kick | Accepted |
| [0062](decisions/0062-the-vocabulary-adds-damped-strokes-wires-off-and-crash-tips.md) | The vocabulary adds damped strokes, a snare with its wires off, and a crash's tip stroke | Accepted |
| [0063](decisions/0063-a-pack-is-a-source.md) | A pack, a folder's first-level subfolder, is a source | Accepted |
| [0064](decisions/0064-grooves-the-grid-does-not-fit-are-left-out-of-the-timing-fits.md) | Grooves the grid doesn't fit are left out of the timing fits | Accepted |
| [0065](decisions/0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md) | Velocities are fitted once and shared by the three styles, which differ in timing only | Accepted |
| [0066](decisions/0066-sleep-token-ii-gets-an-inferred-groove-pack-kit.md) | Sleep Token II gets a second kit, `groove-pack`, inferred, for the layout its groove files play | Accepted |
| [0067](decisions/0067-the-bands-are-cut-at-3-and-6-ms.md) | The bands are cut at 3 and 6 ms of timing spread | Accepted |
| [0068](decisions/0068-what-calibration-fits-and-what-stays-modelled.md) | What calibration fits, by energy, metric level and tempo, and what stays modelled or placeholder | Accepted. Its fitting of the rider gap, accent and fill crescendo, and three premises of its check, are amended by [ADR 0071](decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md), and its noise for every role and its kept values by [ADR 0076](decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md) |
| [0069](decisions/0069-a-style-is-one-complete-toml-file-written-by-the-fit.md) | A style is one complete TOML file in `data/styles/`, written by the fit | Accepted |
| [0070](decisions/0070-the-engine-reads-the-styles-from-data-styles.md) | The engine reads the three styles from `data/styles/`, and the placeholder stays as the fit's source | Accepted |
| [0071](decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md) | The fit is the default, research fills what a performance can't give, and a value they disagree on waits for both numbers | Accepted. Its list of the values the fit keeps from the placeholder is amended by [ADR 0076](decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md) |
| [0072](decisions/0072-docs-research-holds-published-measurements-compared-with-the-project-s-values.md) | `docs/research/` holds published measurements compared with the project's values | Accepted |
| [0073](decisions/0073-the-gap-is-counted-in-milliseconds-through-the-tempo-map.md) | The gap is counted in milliseconds through the tempo map, so it never takes a note past the cap | Accepted |
| [0074](decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md) | A render is heard from its MIDI file in the DAW, and there is no live preview | Accepted |
| [0075](decisions/0075-render-s-summary-counts-how-the-notes-were-placed-in-the-target-kit.md) | `human-o-matic render`'s summary counts how the notes were placed in the target kit | Accepted |
| [0076](decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md) | Riders draw their velocities with a noise of their own, Appendix A's 2.5 | Accepted |
| [0077](decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md) | A rider's strong hits are held under 127 by a spread of their noise, and its weak hits take the gap below them | Accepted |
| [0078](decisions/0078-m4-is-three-prs-and-its-gate-follows-the-third.md) | M4 is three PRs, the MCP server, the skill and the blind test, and its gate follows the third | Proposed |
| [0079](decisions/0079-sessions-are-json-files-in-the-user-s-state-directory.md) | Sessions are JSON files in the user's state directory, one per session ID | Proposed |
| [0080](decisions/0080-a-session-holds-what-a-render-needs-and-reads-its-file-again-by-its-hash.md) | A session holds what a render needs besides its file, and reads the file again, checked by its hash | Proposed |
| [0081](decisions/0081-sections-are-edited-by-split-merge-move-and-rename-all-or-none.md) | Sections are edited by split, merge, move and rename, applied in turn, all or none | Proposed |
| [0082](decisions/0082-a-section-s-facts-are-counted-and-its-guess-says-only-what-the-score-shows.md) | A section's facts are counted from the score, its pattern is its most typical bar, and its guess says only what the score shows | Proposed |
| [0083](decisions/0083-expected-results-are-the-section-rendered-and-measured-by-role.md) | A section's expected results are the section rendered with its controls and measured by role | Proposed |
| [0084](decisions/0084-the-tools-take-ids-and-paths-and-reply-with-compact-json.md) | The tools take IDs and paths, answer each request by the argument it names, and reply with compact JSON | Proposed |
| [0085](decisions/0085-the-server-is-the-mcp-sdk-s-mcpserver-over-stdio-run-as-human-o-matic-mcp.md) | The server is the official SDK's `MCPServer` over stdio, run as `human-o-matic-mcp` | Proposed |
| [0086](decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md) | A note belongs to the beat its tick is in, and each beat's grid is chosen from the onsets that end up in it | Proposed |
