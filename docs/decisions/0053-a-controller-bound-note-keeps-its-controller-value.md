# 0053. A controller-bound note keeps its controller value, and following and writing controllers wait for a map that gives them

- **Status:** Proposed
- **Date:** 2026-11-09

- A note whose articulation a controller value decides or shapes keeps the value set for it. Its note-on never moves across an event of its controllers on its channel in the drum track: it stays from the last such event before its source note to the first one after it, by tick and by order at a tick, and keeps its order among the track's messages so it stays on its side of either event (`render/controllers.py`, [ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).
- Its controllers are those its bindings name. When one names none, as for a `shape` binding whose source doesn't say which controller, every controller on its channel holds it.
- The guard wins over the same-pitch gap ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)), and counts the notes it moved.
- This is all M3 does with controllers. Following `select` values to settle which articulation a note is, and writing controller values when converting to another kit, wait until a map's sources give the controller and its values. Until then the score keeps such a note's articulations joined by `|` ([ADR 0031](0031-the-score-is-frozen-canonical-hits-with-their-source-notes.md)), and converting it to another kit stays a `conversion` request with the reason `cc` ([ADR 0021](0021-conversion-falls-back-within-a-family.md)).
- This amends [ADR 0009](0009-m1-resolves-notes-channels-and-velocity-ranges.md)'s line that controller-driven articulations are resolved in M3, and the lines of ADRs 0021 and 0031 that wait for M3.

**Why:** Moving a note across the controller event meant for it, such as a hat pedal value sent just before the hit, changes the sound with no warning, so the engine needs this guard. Following and writing controllers needs the controller number and its values, and no built-in map has them: the only controller-bound articulations, `hat.variable` and `hat.variable.tip` in one library, are `shape` bindings that name no controller, and no map has a `select` binding. Code for them would run only on maps built for its tests.

**Consequences:** A song whose hats a controller drives renders in its own kit, with every hat kept on its side of the controller events, but asks before converting to another kit. A map whose sources give a controller and its values needs a new decision to follow and write it.
