# 0060. A groove held to the grid is left out of the timing statistics

- **Status:** Proposed
- **Date:** 2026-11-10

- A groove is held to the grid when more than a fifth of its notes, graces left out, sit at one offset from their grid point, counted in ticks: exactly on it, or all shifted alike. Its timing spread and feel aren't measured, and it is counted apart.
- Its velocities are still measured, so a later decision can use them for the velocity fits.
- `measure --on-grid SHARE` measures with another share, to see how much the choice moves.

**Why:** Quantized notes, or quantized notes shifted together, would pass for a very tight drummer. A performance recorded at 480 PPQ or finer puts a fifth of its notes on one tick only when they spread by under about 2 ticks, under 2 ms at most tempos, so a groove past that was quantized in whole or in part. Over the assigned folders, timing spread falls steadily as that share rises, as partial quantization would make it, while a folder of plainly played grooves has almost all of its grooves below a fifth. Counting the most common offset, rather than only notes on the grid, also catches a quantized part moved as a whole.

**Consequences:** Files coarser than 480 PPQ land on one tick more often by chance, so the test would leave out a performance among them. None with a tempo is measured now. Editing that leaves notes off the grid, such as quantizing at partial strength or adding small random offsets, can't be told from playing, so the tightest grooves that remain may still be edited.
