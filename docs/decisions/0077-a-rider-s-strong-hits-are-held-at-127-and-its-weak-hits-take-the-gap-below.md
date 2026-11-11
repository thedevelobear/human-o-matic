# 0077. A rider's strong hits are held at 127, and its weak hits take the gap below them

- **Status:** Proposed
- **Date:** 2026-11-11

- A rider hit that takes the gap, an alternating or a weak one, is centered half the gap above or below its role's center, as before, unless that puts the strong center above 127, the ceiling draws are reflected below ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)). Then the strong center is 127 and the weak center the whole gap below it, so all of a rider's centers move down together and the gap stays whole. A lone rider hit keeps its center.
- It is the backend's rule (`render/backends/parametric.py`), before the noise, the song's energy drift and the guards. The rider's velocity anchors, the gap of 4 to 14, the flip rate, the draw order and the timing are unchanged. The ceiling is `MAX_VELOCITY` in `render/guards.py`, which the reflection uses too.
- At the defaults it binds from energy 0.84 up, where the fitted rider center plus half the gap of 9 reaches 127. Below that nothing changes, so the control tests at the default energy read the same.

| Energy | 0.5 | 0.8 | 0.9 | 0.95 | 1.0 |
|---|---:|---:|---:|---:|---:|
| A quarter-note ride's gap, strong less weak, before | 9.1 | 7.5 | 4.6 | 2.5 | 0.3 |
| The same, held at 127 | 9.1 | 7.5 | 6.5 | 6.5 | 6.5 |
| Its share of moves that change direction, before | 0.85 | 0.83 | 0.79 | 0.76 | 0.74 |
| The same, held at 127 | 0.85 | 0.83 | 0.81 | 0.81 | 0.81 |

The gap is the mean over 20 takes of 64 bars at the defaults but for energy. Held at 127, it is under the gap of 9 because the strong hits' own noise and the song's energy drift are reflected below 127.

**Why:** The fitted rider center at energy 1.0, 126.78, is far above Appendix A's 114, so half the gap above it took the strong hits past 127, and reflecting them put them under the weak ones: the alternation vanished at full power, the setting a breakdown asks for. Holding the strong hits at the ceiling keeps them the loudest, and moving the weak ones down keeps the gap, with no other note or value changed.

**Consequences:** [ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)'s rider row, strong hits half the gap above the center and weak ones half below, is amended by this ADR near 127. At full energy, a rider's weak hits are about the gap quieter than before, so the mean of normal-typed notes at energy 1.0 falls by about 1.4.
