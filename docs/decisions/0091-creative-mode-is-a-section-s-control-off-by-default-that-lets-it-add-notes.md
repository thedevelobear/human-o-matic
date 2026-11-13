# 0091. Creative mode is a section's control, off by default, that lets it add notes

- **Status:** Proposed
- **Date:** 2026-11-13

- `creative` is a boolean control of `ControlVector`, `ControlInput` and `Controls` (`controls.py`), false in every style's defaults and in the placeholder's. A session or plan from before it reads as unset, so it renders as before.
- It is set per section with `set_section_controls`, or for the whole song without `section_ids`, under each section's own, and repeats take it with their group's controls. `set_style` has no switch for it.
- A section whose controls set `creative`, and not `skip`, adds notes at render time: ghost notes, cymbals, a fill, flams, rimshots and chokes ([ADR 0092](0092-a-creative-section-adds-by-rules-read-from-its-own-score.md)). `skip` wins, so a skipped section adds nothing. The added notes are never written into the score, which stays the frozen canonical hits of [ADR 0031](0031-the-score-is-frozen-canonical-hits-with-their-source-notes.md), nor into the session, which holds no note ([ADR 0080](0080-a-session-holds-what-a-render-needs-and-reads-its-file-again-by-its-hash.md)).
- The instrument seam gains `additions(view, rng)`, what a creative section adds, which `render()` calls. `drums` proposes the additions in `instruments/additions.py`, and `generic`, which knows no drums, adds nothing.
- The plan's "Version 1 never adds notes" and its property "note count is unchanged apart from notes the user chose to drop" hold for every section that isn't creative. A render writes the score's notes, less those left out, and the notes the creative sections add, which its report counts.

**Why:** Added notes are the plan's M6, asked for now. An opt-in per section leaves every render without it byte for byte as before, and the M4 blind test's variants unaffected, while a song-wide request is still one call without `section_ids`.

**Consequences:** [ADR 0046](0046-controls-are-layered-pydantic-models-with-a-json-round-trip.md)'s nine controls are ten, and [ADR 0045](0045-the-engine-is-render-modules-behind-a-small-instrument-seam.md)'s seam has a third method.
