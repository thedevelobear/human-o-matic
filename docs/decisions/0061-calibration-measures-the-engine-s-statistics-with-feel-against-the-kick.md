# 0061. Calibration measures the engine's statistics, with feel taken against the kick

- **Status:** Proposed
- **Date:** 2026-11-10

Each groove gets the plan's four attributes, measured as `render/measure.py` measures a render ([ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)):

| Attribute | Statistic |
|---|---|
| Energy | The mean velocity of its normal-typed notes |
| Dynamic range | The mean, over drums with two or more, of the spread of their normal-typed notes' velocities |
| Tightness | Timing spread: the standard deviation of its notes' offsets from the grid, graces left out, in ms |
| Feel | The mean offset of its snare and rider hits less the mean offset of its kicks, in ms |

- Hit types and roles come from `normalize()` and the drums instrument, as for a render ([ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md)).
- The rider gap, which needs strong and weak hits, isn't measured, since a performance doesn't label them.

**Why:** Calibrating on the statistics the engine is tested on means a style's numbers and a render's measure the same thing. Feel is taken against the kick because a whole performance can sit early or late against its file's grid, which the tempo map sets, and only the hands against the feet are the drummer's.

**Consequences:** Feel here differs from the engine's `feel_offset`, which a render measures against the grid, so the fit has to set the snare and riders' offsets from it, relative to the kick.
