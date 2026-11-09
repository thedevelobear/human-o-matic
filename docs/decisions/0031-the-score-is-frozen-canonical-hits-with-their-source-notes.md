# 0031. The score is frozen canonical hits on a grid that keep their source notes

- **Status:** Proposed
- **Date:** 2026-11-08

- `normalize.pipeline.normalize(song, kit, ...)` reads the drum track ([ADR 0017](0017-the-drums-are-one-whole-track.md)) through a built-in kit, quantizes it ([ADR 0026](0026-a-grid-per-beat-by-timing-error-and-complexity.md) to [ADR 0028](0028-limbs-within-20-ms-share-a-grid-point.md)) and types its hits ([ADR 0030](0030-hit-types-cluster-each-familys-velocities.md)). A missing tempo or an unclear drum track raises, as before ([ADR 0016](0016-tempo-and-time-signatures.md)). The `unmapped_notes`, `ambiguous_bars` and `hit_types` requests are returned with the score, in that order, and each is answered by calling again with the argument it names.
- `Score` and `ScoreNote` are frozen dataclasses, as `MidiSong` is. A note has its source `Note` and that note's position in `MidiSong.notes`; its canonical articulation, family and piece; its quantized tick; its offset, the performed start minus the quantized start in milliseconds; its beat and that beat's grid; for a grace, the source position of its main; and its hit type and that type's confidence.
- A note a controller value decides among several articulations keeps them all, joined by `|` as conversion keys them ([ADR 0021](0021-conversion-falls-back-within-a-family.md)), with the family and piece of the first, until controllers are followed in M3 ([ADR 0009](0009-m1-resolves-notes-channels-and-velocity-ranges.md)).
- Notes are ordered by tick, then by source position, and notes of one pitch and channel never move before an earlier one. The score also holds its beats with their grids, scores and alternatives, each family's hit types, the tempo and time signature maps for bar and beat positions, the track and the kit.
- Drum notes the kit doesn't map are left out of the score and wait, as `pending`, for one `unmapped_notes` request in conversion's shape: each pitch with its channels, count and first positions. The answer is `unmapped`, from a pitch to an articulation of the kit or `drop`, or another `from_map`, and dropped notes are listed. Notes read through a `low` confidence articulation are counted per articulation in the result ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)).
- The same song, kit and answers always give the same score.

**Why:** Canonical names make every later stage library-neutral. Keeping each source note means a `skip` section can be written back exactly as it came in, while the rest uses only the tick and hit type. A frozen score keeps a later stage from changing what normalizing decided. What reaches the agent is the requests and counts, never the notes.

**Consequences:** The score isn't serialized, so what needs it again rebuilds it from the file and the answers. Until a pending note is answered, the score is incomplete, and `Normalized.complete` says so.
