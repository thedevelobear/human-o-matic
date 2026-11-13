# 0093. Added notes draw from a stream of their own, through their section's parameters

- **Status:** Accepted
- **Date:** 2026-11-13

- A creative section's additions draw from a stream keyed `(2, start, take)`, beside the section's own `(1, start, take)` ([ADR 0049](0049-each-section-draws-from-its-own-seeded-stream.md)). It first picks what to add, the ghost notes' pattern, then draws the admitted notes, in play order, with the parametric backend and the section's own compiled parameters, after the section's own draw. With creative mode off it is never drawn, and no other stream moves when it is.
- An added note on an onset the section already plays takes that onset's shared offset, so the hits of one onset stay together. The song's drifts reach an added note at its tick, read linearly between the score's ticks, so the drifts are drawn at the score's ticks as before.
- An added note's MIDI order is after every other note's, so the order of no other note moves. A rendered note added by a section has a position past the score's notes, its grid point in `tick` and its kind in `added`. A note written as a rimshot keeps its own position and draw.

**Why:** A stream of their own keeps every other draw, the section's own included, as it was. The same backend and parameters make an added note play as the section's notes of its role do, with no model of its own.

**Consequences:** [ADR 0049](0049-each-section-draws-from-its-own-seeded-stream.md)'s streams gain a third key. Another take of a section picks other ghost notes.
