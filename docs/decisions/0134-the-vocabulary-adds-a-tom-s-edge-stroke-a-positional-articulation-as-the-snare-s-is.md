# 0134. The vocabulary adds a tom's edge stroke, a positional articulation as the snare's is

- **Status:** Proposed
- **Date:** 2026-11-16

- `data/vocabulary.toml` adds `edge` to the tom family's articulations, so `tom.N.edge` names a tom struck toward its edge, as `snare.edge` names the snare's.
- It is an articulation, not a variant of `hit`, as [ADR 0019](0019-canonical-names-follow-one-grammar.md) has no `edge` variant. On a kit without it, conversion takes the piece's default, `tom.N.hit`, and reports it as a `default` step, after re-spreading the toms by register where the kits have different numbers of them ([ADR 0021](0021-conversion-falls-back-within-a-family.md)).

**Why:** Logic Pro's Drum Kit Designer mapping gives each of its three toms an edge stroke on a note of its own, which would otherwise be left out of the map and asked about. On a kit without it, the hit on the same tom is the nearest sound, and the family doesn't change.
