# 0052. Each control is tested against the statistic it mainly drives, and the plan's properties have exact definitions

- **Status:** Proposed
- **Date:** 2026-11-09

- `render/measure.py` measures a render's notes, leaving out notes played as they came in. Each control is tested against the statistic the plan's control table says it mainly drives:

| Control | Statistic | Direction as it rises |
|---|---|---|
| `energy` | Mean velocity of normal-typed notes | Up |
| `groove` | Accent contrast (accent-typed less normal-typed, per drum); mean velocity of soft notes; rider gap | Up |
| `dynamic_range` | Rider gap (strong less weak alternating hits); mean spread of normal-typed velocities per drum | Up |
| `tightness` | Spread of offsets from the grid, graces left out | Down |
| `feel` | Mean offset of the snare and riders, and the snare's mean velocity from 0 up | Up, the pushed side smaller |
| `arc` | Velocity trend: the rise from first to last note on the best straight line | `drop` < `steady` < `build` |
| `fill_intensity` | Mean velocity of fill notes; fill rise (the second half of the crescendo less the first) | Up |
| `ghost_level` | Mean velocity of soft notes | Up |

- The engine's tests set one control at a time to 0, 0.25, 0.5, 0.75 and 1 (`feel` from -1 to +1), the others at their defaults, on one groove built in code with every role, its accents on the kick and snare and none on a rider, and average the statistic over six seeds. Each must move strictly the right way. The same seeds draw at every value, so only the control changes. A velocity statistic must also rise by at least 2 steps from one end of its control to the other, since with the same seeds a draw's noise, which `dynamic_range` scales, moves a difference of means by a fraction of a step. `skip` is tested as the property that a section played as it came in comes out unchanged. This is the engine's part of the M3 exit, on the placeholders; the gate after the preview PR checks it again on the calibrated styles ([ADR 0043](0043-m3-is-three-prs-and-its-gate-follows-the-third.md)).
- The plan's property tests, with `hypothesis`, on grooves built in code, read as follows. Their controls are drawn at their ends often, where the guards bind, and examples pin the corners a random draw rarely reaches: 16ths at 600 BPM played loose, across boundaries too; soft notes whose center meets the others'; and loud notes at a boundary.
  - **Same session and seed:** the same song, plan and seed give the same bytes. **One section again:** with new controls for one section, `skip` left as it was, every other section's notes are equal.
  - **Note count:** every score note comes out once, apart from the articulations a substitution drops.
  - **Input numbers:** two inputs that normalize to the same score, the same ticks, articulations and hit types, but with other velocities and with timing up to 6 ms apart, render to the same bytes. Graces and controller-bound notes are left out, since a grace's gap and a controller window come from the input by design.
  - **Same pitch:** notes keep their order, keep 0.6 of their grid gap less a tick, and a rendered note ends by the next one's start, at tempos up to 600 BPM, where a 16th is 25 ms, with notes up to 2 bars long and the song's tightness at 0 and feel at -1 or +1. **The cap:** every offset is within 12 ms plus two ticks of rounding, under random tempo maps of up to 120 changes, with the same loose controls.
  - **Velocities:** 1 to 127, and never the same twice in a row on one pitch or on one drum, unless both notes were played as they came in, on dense grooves of four drums. **Soft below normal:** per section and drum, every soft note is below every other note.
  - **Rider flip rate:** over 256 bars of 8th hats, the share of neighbouring alternating hits in one section whose drawn strong and weak labels differ is 0.70 to 0.85. **Unison spread:** at the defaults, the hits of one grid point are within 10 ms of each other.
  - **Graces:** a grace's gap before its main note stays within a tick. **Skip:** a section played as it came in keeps its source notes exactly, in the kit they were read with.

**Why:** Measuring what each control is meant to move is the exit's own words. Fixed seeds across values separate the control's effect from the draw's. The flip rate is measured on the labels the sampler draws, since a velocity alone can't tell a weak hit from a strong one with low noise.
