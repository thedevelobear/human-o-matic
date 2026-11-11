# 0077. A rider's strong hits are held under 127 by a spread of their noise, and its weak hits take the gap below them

- **Status:** Proposed
- **Date:** 2026-11-11

- A rider hit that takes the gap, an alternating or a weak one, is centered half the gap above or below its role's center, as before, unless that puts the strong center within a margin of 127, the ceiling draws are reflected below ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)). The margin is the section's compiled rider noise, the style's `rider_noise_sd` scaled by 0.5 plus `dynamic_range` ([ADR 0076](0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)). Then the strong center is 127 less the margin and the weak center the whole gap below it: `top = min(center + gap / 2, 127 - margin)`, strong at `top` and weak at `top - gap`. A lone rider hit keeps its center.
- It is the backend's rule (`render/backends/parametric.py`), before the noise, the song's energy drift and the guards, whose reflection at 127 is unchanged. The ceiling is `MAX_VELOCITY` in `render/guards.py`, which the reflection uses too. The rider's velocity anchors, the gap of 4 to 14, the flip rate, the draw order and the timing are unchanged.
- The centers are continuous in the energy: they rise as before up to where the rule binds, and stay level above it. It binds from energy 0.75 at the defaults, from about 0.61 at `dynamic_range` 1, 0.82 at 0.25 and 0.89 at 0, so the control tests at the default energy read the same below their top value.

A quarter-note ride's gap, strong less weak, before and with the rule, as the mean over 20 takes of 64 bars at the defaults but for energy and `dynamic_range`:

| `dynamic_range` | Energy 0.5 | 0.8 | 0.9 | 0.95 | 1.0 |
|---|---:|---:|---:|---:|---:|
| 0, before | 4.1 | 4.0 | 3.0 | 1.8 | 0.3 |
| 0, held | 4.1 | 4.0 | 3.2 | 3.2 | 3.2 |
| 0.25, before | 6.6 | 6.0 | 4.0 | 2.3 | 0.3 |
| 0.25, held | 6.6 | 6.0 | 5.8 | 5.8 | 5.8 |
| 0.5, before | 9.1 | 7.5 | 4.6 | 2.5 | 0.3 |
| 0.5, held | 9.1 | 8.3 | 8.3 | 8.3 | 8.3 |
| 1, before | 13.9 | 9.1 | 5.1 | 2.7 | 0.3 |
| 1, held | 13.9 | 13.2 | 13.2 | 13.2 | 13.2 |

At the defaults the ride changes direction on 0.85, 0.83, 0.79, 0.76 and 0.74 of its moves before, and on 0.85 and then 0.84 from 0.8 up with the rule, its strong hits about 123.9 and its weak 115.6 at full energy. The gap falls short of its nominal value by what the song's energy drift, SD 2, and the noise still reflect, most at `dynamic_range` 0, whose margin is 1.25.

**Why:** The fitted rider center at energy 1.0, 126.78, is far above Appendix A's 114, so half the gap above it took the strong hits past 127, and reflecting them put them under the weak ones: the alternation vanished at full power, the setting a breakdown asks for. Holding the strong center at 127 alone left a gap of 6.5 of 9, since half the strong hits' noise was reflected. A spread of their noise below it keeps most of the gap, and moving the weak hits down with it changes no other note or value.

**Consequences:** [ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)'s rider row, strong hits half the gap above the center and weak ones half below, is amended by this ADR near 127. Above where the rule binds, a rider no longer gets louder with energy, and its weak hits are the gap below a strong center a little under 127, so the mean of normal-typed notes at energy 1.0 in the control tests falls from 122.7 to 120.2.
