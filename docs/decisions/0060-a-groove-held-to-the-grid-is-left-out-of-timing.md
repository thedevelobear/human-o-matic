# 0060. A groove held to the grid is left out of the timing statistics

- **Status:** Proposed
- **Date:** 2026-11-10

- A groove's offsets from their grid points are counted in steps, a step being the smallest gap between them: a tick, or more for a file saved at a finer resolution than it was played at. The groove is held to the grid when either:
  - its notes pile up at one offset: more than a fifth of them there, and more than twice as many as one step either side, on average, as quantizing all or some of its drums leaves them, on the grid or all shifted alike;
  - or its offsets spread by less than 1.5 steps, as quantized notes with a tick or so of jitter do.
- A held groove's timing spread and feel aren't measured, and it is counted apart, split by which of the two held it. Its velocities are still measured ([ADR 0065](0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md)).

**Why:** Quantized notes, whole or in part, would pass for a very tight drummer. A share at one offset alone also catches a tight but smooth spread, which puts a fifth of its notes on one tick by chance when it spreads by under about 2 steps; quantized notes show instead as a spike over the offsets beside them, which a smooth spread doesn't make however narrow it is. A spread under 1.5 steps, about 1 to 2 ms at 480 PPQ, is tighter than any drummer, and is what a tick of random jitter on quantized notes looks like. Counting in the offsets' own steps keeps a file saved at twice its resolution from looking twice as loose to the test.

**Consequences:** Editing that leaves notes off the grid with a wider spread, such as quantizing at partial strength or adding random offsets of a few ticks, can't be told from playing, so the tightest grooves that remain may still be edited. A file coarser than 480 PPQ has wide steps in milliseconds, so the 1.5-step floor holds more of its grooves; none with a tempo is measured now.
