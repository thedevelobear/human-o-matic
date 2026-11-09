# 0050. The guards hold every backend's draws, and never make a section depend on another's

- **Status:** Proposed
- **Date:** 2026-11-09

- `render/guards.py` runs after the song's drifts, on every backend's draws. **Timing**, in turn:
  1. Each offset is cut to ±12 ms (Appendix A), and a grace takes its main note's offset, so a main note and its graces move as one.
  2. Across a section boundary, two notes in a row on one pitch each keep to their side: the earlier at most 0.2 of their grid gap late, the later at most 0.2 early, so they keep 0.6 of it whatever the other section draws.
  3. Each note goes to its nearest tick, and to tick 0 when it would be before it, which is counted.
  4. In time order, a note after another of its pitch in its own section, or after a note played as it came in, keeps 0.6 of their grid gap (Appendix A) and at least a tick, by moving later with its main note and graces. A note before one played as it came in keeps the gap by moving earlier, with its main note and graces. When a note can't keep both gaps, the one from the note before wins.
  5. A note held to its controller events stays within them ([ADR 0053](0053-a-controller-bound-note-keeps-its-controller-value.md)), which wins over both gaps: a note inside its window keeps its place, and one outside moves to its nearer edge.
  6. Each note keeps its source length, at least a tick, and ends by the time the next note of its pitch starts, or by the earliest that note could start when it is in another section.
- **Velocity**, in turn:
  1. A draw above 127 is reflected below it, and one below its role's band above it ([ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)), then rounded.
  2. It moves into its articulation's velocity range ([ADR 0009](0009-m1-resolves-notes-channels-and-velocity-ranges.md)).
  3. Per section and drum that has soft-typed notes, they are held at least 2 below the lowest other note, and the others no lower than 1 below it, so soft notes stay below them. A drum with no soft notes in the section has no such floor.
  4. In play order, a note takes neither the velocity of the note before it on its **pitch** nor that of the note before it on its **drum** (family and piece) when that note is in its section or played as it came in, nor that of a note after it played as it came in. The plan says both "per pitch" and "on one drum", and both are held. The nudge is to the nearest velocity that fits, +1 before -1, so -1 at 127.
  5. A note next to a note of another rendered section, on its pitch or its drum, takes a velocity of a class instead of avoiding the other's value: modulo 4, the bit worth 2 is its place among its pitch's notes modulo 2, and the bit worth 1 its place among its drum's. Neighbours across a boundary always differ in one bit, so they never match whatever the other section draws, and no note moves by more than a few steps.
- A velocity range too narrow for a rule wins over the rule, since a velocity outside it plays another articulation. A range of one value repeats it. Every guard counts the notes it moved: `gap` the notes moved later or earlier for their gap, and `controller` those their window moved. `unmet` counts what a guard couldn't hold, a range too narrow for a rule or two gaps that can't both be kept, and such a note is also counted under the guard that moved it.
- Notes played as they came in keep their ticks, lengths and velocities, and the guards work around them.
- **Section independence:** nothing a section's draws decide reaches another section, so rendering one section with new controls leaves every other section's notes as they were. Turning `skip` on or off for a section is the one exception: the notes next to it then avoid its fixed notes instead of keeping to their class and their side of the gap.

**Why:** Guards after the backend hold the plan's limits for the parametric engine and a trained model alike. A rule that compared a note with the draws of the section before it would change that note whenever the earlier section is rendered again, so across a boundary each side keeps a rule of its own, from the score alone.

**Consequences:** A note at a boundary can sit up to 2 velocity steps from its draw, and a note can move up to a fifth of its grid gap less than its draw asked.
