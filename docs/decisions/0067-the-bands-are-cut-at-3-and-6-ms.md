# 0067. The bands are cut at 3 and 6 ms of timing spread

- **Status:** Proposed
- **Date:** 2026-11-10

- A groove whose timing spread is under 3 ms is `tight`, from 3 to under 6 ms `medium`, and 6 ms or more `loose` ([ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)). The spread is the one `tools/calibrate.py` measures over a groove of at most 16 bars ([ADR 0059](0059-calibration-measures-files-in-windows-of-at-most-16-bars.md)), of the performed grooves the grid fits ([ADRs 0060](0060-a-groove-held-to-the-grid-is-left-out-of-timing.md) and [0064](0064-grooves-the-grid-does-not-fit-are-left-out-of-the-timing-fits.md)).
- `tools/fit_styles.py` holds the cuts as `CUTS`.

**Why:** Whole milliseconds near the thirds of the measured spreads give three bands of about the same size, each pooling 9 or 10 packs with none supplying a majority but in `tight` ([ADR 0063](0063-a-pack-is-a-source.md)), and they are easy to say: under 3, 3 to 6, over 6.

**Consequences:** `tight` plays the band's median, near 2 ms over 16 bars, tighter than the placeholder's 3.1 ms ([ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)) and Appendix A's 3 to 4 ms, which fall at the edge of `medium`.
