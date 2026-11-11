# 0052. Each control is tested against the statistic it mainly drives, and the plan's properties have exact definitions

- **Status:** Accepted. Its `feel` row's smaller pushed side is amended by [ADR 0071](0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md), its same-pitch and cap properties by [ADR 0073](0073-the-gap-is-counted-in-milliseconds-through-the-tempo-map.md), and its gate after the preview PR by [ADR 0074](0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)
- **Date:** 2026-11-09

- `render/measure.py` measures a render's notes, leaving out notes played as they came in. Each control is tested against what the plan's control table says it mainly drives:

| Control | Statistic | As it rises |
|---|---|---|
| `energy` | Mean velocity of normal-typed notes | Up |
| `groove` | Accent contrast (accent less normal, per drum); soft notes' mean; rider gap | Up |
| `dynamic_range` | Rider gap (strong less weak alternating hits); spread of normal velocities per drum | Up |
| `tightness` | Spread of offsets, graces left out | Down |
| `feel` | Snare and riders' mean offset; the snare's mean velocity from 0 up | Up, pushed side smaller |
| `arc` | Velocity trend, the rise across the section on the best straight line | `drop` < `steady` < `build` |
| `fill_intensity` | Fill notes' mean; fill rise (the crescendo's second half less its first) | Up |
| `ghost_level` | Soft notes' mean | Up |

- One control at a time takes 0, 0.25, 0.5, 0.75 and 1 (`feel` -1 to +1), the others at their defaults, on one groove with every role and its accents off the riders, averaged over six seeds. Each statistic must move strictly the right way, and a velocity statistic by at least 2 steps end to end. This is the engine's part of the M3 exit; the gate after the preview PR checks it again on the calibrated styles ([ADR 0043](0043-m3-is-three-prs-and-its-gate-follows-the-third.md)).
- The plan's properties, with `hypothesis`, draw controls at their ends often, where the guards bind, and examples pin the corners random draws rarely reach:
  - **Seed:** the same song, plan and seed give the same bytes. **One section again:** new controls for one section, `skip` unchanged, leave the others' notes equal. **Note count:** every score note comes out once, but for substitutions' drops.
  - **Input numbers:** two inputs that normalize to the same ticks, articulations and hit types, with other velocities and timing up to 6 ms apart, give the same bytes. Graces, a main note with a grace on the song's first tick, and controller-bound notes are left out, since their gap and window come from the input by design.
  - **Same pitch:** order, 0.6 of the grid gap less a tick, and a rendered note's end by the next start, up to 600 BPM, with notes up to 2 bars long and the song loose (tightness 0, feel ±1). **Cap:** a rendered note's offset within 12 ms plus two ticks, under up to 120 tempo changes, with graces drawn.
  - **Velocities:** 1 to 127, never repeated on a pitch or a drum unless both notes are kept, on drums of several pitches. **Soft:** below every other note of its drum and section.
  - **Flip rate:** 0.70 to 0.85 between neighbouring alternating rider labels over 256 bars. **Unison:** one grid point's hits within 10 ms at the defaults. **Graces:** the gap they were played at within a tick, and their order, with graces drawn before notes and often a flam on the song's first tick, where a gap over 12 ms leaves the main at the cap. **Skip:** the source notes exactly, in their own kit.

**Why:** Measuring what each control is meant to move is the exit's own words. The same seeds at every value separate the control from the draw, and the least rise keeps the noise `dynamic_range` scales from passing for its effect. The flip rate is measured on the drawn labels, since a velocity alone can't tell weak from strong at low noise.
