# 0026. Each beat takes one of four grids, by its timing error in milliseconds plus a complexity penalty

- **Status:** Proposed
- **Date:** 2026-11-08

- `normalize/grid.py` chooses a grid for every beat that has notes. A beat is the time signature's denominator note ([ADR 0016](0016-tempo-and-time-signatures.md)). A beat with no notes has no grid.
- The candidates are the 16th, the 8th triplet, the 16th triplet and the 32nd: 4, 3, 6 and 8 steps per quarter note. One applies to a beat when it divides the beat into whole steps: all four in a quarter or longer, the 16th, 16th triplet and 32nd in an eighth, and the 16th and 32nd in a sixteenth. A beat shorter than a 32nd takes the 32nd, with the beat's ends as its points. A grid's points run from the beat's start to its end, the next beat's start, and stop where a bar cut short by a signature change ends.
- Each applicable grid scores the sum, over the beat's onsets ([ADR 0028](0028-limbs-within-20-ms-share-a-grid-point.md)), of each onset's distance in milliseconds to the grid's nearest point at the local tempo, plus the grid's penalty: 0 for the 16th, 6 ms for the 8th triplet, and 10 ms for the 16th triplet and the 32nd. The lowest score wins, and a tie goes to the simpler grid, in that order. A beat of quarters and 8ths takes the 16th.
- Each onset goes to its nearest point on the chosen grid. An answer can set a beat's grid ([ADR 0029](0029-unclear-beats-are-one-ambiguous-bars-request.md)).
- With jitter from a normal spread of 4 ms, capped at 12 ms, grooves built in code that mix all four grids come back to at least 99.5% of their grid positions from 60 to 240 BPM and across tempo changes. With a spread of 6 ms, at least 99% comes back up to 160 BPM, and about 97% at 240 BPM.

**Why:** A grid per bar can't hold a triplet fill or a 32nd double kick inside a bar of 16ths, while a beat is short enough to hold one grid. Scoring in milliseconds at the local tempo measures what a listener hears at any tempo, including tempo changes. The penalty means a finer grid has to explain the timing clearly better before it is chosen, so jitter alone doesn't turn 16ths into 32nds.

**Consequences:** A beat that mixes 32nds and 16th triplets is put on one of them. At fast tempos a 32nd point and a 16th triplet point are close (10.4 ms apart at 240 BPM), so with a loose spread a lone note between them can be misread. Such beats are often reported as ambiguous.
