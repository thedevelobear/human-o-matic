# 0045. The engine is a set of render modules behind a small instrument seam

- **Status:** Accepted. Its line on `preview.py` is amended by [ADR 0074](0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)
- **Date:** 2026-11-09

- The engine's modules, as the plan's architecture lays them out, with some it didn't list:
  - `controls.py`: the controls and plans ([ADR 0046](0046-controls-are-layered-pydantic-models-with-a-json-round-trip.md)).
  - `render/parts.py`: each note's role and limb, and the play order. `render/style.py`: the style ([ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)). `render/compiler.py`: a section's controls and the style into its parameters.
  - `render/backends/parametric.py`: a section's draws. `render/engine.py`: the streams, the song's drifts and `render()` ([ADR 0049](0049-each-section-draws-from-its-own-seeded-stream.md)). `render/guards.py`: the limits on every backend ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)).
  - `render/target.py` and `render/output.py`: where notes are written and the song written back ([ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)). `render/controllers.py`: the controller guard's windows ([ADR 0053](0053-a-controller-bound-note-keeps-its-controller-value.md)). `render/measure.py`: each section's statistics ([ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)).
  - `instruments/base.py`, `instruments/drums.py` ([ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md)) and `instruments/generic.py`.
  - `session.py` waits for M4 with the MCP tools, and `preview.py` for the preview PR ([ADR 0043](0043-m3-is-three-prs-and-its-gate-follows-the-third.md)).
- `Instrument` is a `Protocol` with what `render()` calls and nothing else: each note's `parts`, and `compile`, a section's controls with a style into its parameters. `render()` takes an instrument, `drums` by default.
- Normalizing, hit typing, the agent's facts and a control schema, which the plan also lists for an instrument, stay out of the seam until something calls them: a second real instrument, or M4's facts and its `set_section_controls`.
- `generic` mode gives every note the role `other` and no limb offset, and `feel` moves every note. It has no fills, backbeats, riders or double kick, and `fill_intensity` changes nothing.

**Why:** Each module has one job the guards and the tests can hold it to, and the backend is the one part M5 replaces. The plan says not to design for piano and guitar yet, so the seam has only what two instruments that exist use, and `generic` shows it carries a render with no drum knowledge.
