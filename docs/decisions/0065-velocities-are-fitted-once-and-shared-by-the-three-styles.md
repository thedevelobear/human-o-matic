# 0065. Velocities are fitted once and shared by the three styles, which differ in timing only

- **Status:** Proposed
- **Date:** 2026-11-10

- One velocity fit serves `tight`, `medium` and `loose`. It is fitted on every groove of every assigned folder whose velocities aren't flat, whatever its timing: performed, held to the grid ([ADR 0060](0060-a-groove-held-to-the-grid-is-left-out-of-timing.md)), without a tempo, or with too few notes for a timing spread.
- A groove's velocities are flat when every drum with 4 or more normal-typed notes in it has at most two velocities, as a programmed part has, and can't be told when no drum has 4. Both are left out.
- The three styles differ in their timing, fitted on their own band's grooves.

**Why:** Velocities are recorded apart from timing, and a quantized groove's velocities can still be played: those held to the grid vary as much as those with performed timing. One fit on all of them draws on many more grooves and packs than any band, and the plan already steers dynamics per section with the controls rather than by style.

**Consequences:** [ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)'s fitting of each style on its own band is amended by this ADR for velocities. A style's name now says only how tight it plays.
