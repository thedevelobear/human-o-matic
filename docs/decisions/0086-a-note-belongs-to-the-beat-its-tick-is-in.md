# 0086. A note belongs to the beat its tick is in, and each beat's grid is chosen from the onsets that end up in it

- **Status:** Accepted
- **Date:** 2026-11-12

- `grid.snap` scores each onset in the beat it was played in ([ADR 0026](0026-a-grid-per-beat-by-timing-error-and-complexity.md)). An onset put on that beat's end, the next beat's start, then belongs to the next beat, and both beats are scored again. That moves no point: the start is a point of every grid, and without the onset the grid that placed it stays the best of the beat it left.
- `quantize` lists beats to the end of the bar after the last hit's, so a hit played just before that bar has a beat to belong to.
- So a note's beat holds its tick. A backbeat played early is a backbeat ([ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md)), and a downbeat played early renders with its own section ([ADR 0049](0049-each-section-draws-from-its-own-seeded-stream.md)).

**Why:** A note played just before a beat, or put on it at a tempo whose milliseconds don't round-trip, was filed under the beat before, though its tick was right: about a tenth of the performed MIDI's notes, which kept two in five of its on-beat snares from being backbeats.

**Consequences:** [ADR 0026](0026-a-grid-per-beat-by-timing-error-and-complexity.md)'s choice of a beat's onsets is amended by this ADR. The styles in `data/styles/` were fitted again on it, and the plan gives their values and the gate's numbers. [ADR 0071](0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md), [ADR 0076](0076-riders-draw-their-velocities-with-a-noise-of-their-own.md), [ADR 0077](0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md) and the research pages keep the first fit's figures, as of their dates.
