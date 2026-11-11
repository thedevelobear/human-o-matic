# 0064. Grooves the grid doesn't fit are left out of the timing fits

- **Status:** Accepted
- **Date:** 2026-11-10

- A groove whose notes the quantizer's grids can't place, such as tuplets or groupings none of its four grids holds ([ADR 0026](0026-a-grid-per-beat-by-timing-error-and-complexity.md)), is left out of the timing fits, since its offsets then measure the grid's misfit rather than the drummer.
- A groove the grid doesn't fit is one with more than a tenth of its notes more than 20 ms from their grid point, the quantizer's own mark of a far onset ([ADR 0029](0029-unclear-beats-are-one-ambiguous-bars-request.md)). `tools/calibrate.py` applies it by default, and `measure --misfit SHARE` measures with another share, showing the bands with those grooves left out and, beside, kept in.
- Such a groove's velocities are still measured.

**Why:** A drummer at the plan's loosest, 12 ms, puts about a tenth of their notes past 20 ms by chance, so a groove with a much larger share is one the grid doesn't fit, and its spread would put a misread groove into `loose`.

**Consequences:** A loose drummer whose grooves put more than a tenth of their notes past 20 ms is left out with the misfits, so `loose` is fitted on the grooves the grid places.
