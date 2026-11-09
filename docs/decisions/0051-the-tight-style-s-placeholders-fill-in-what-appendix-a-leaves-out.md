# 0051. The `tight` style's placeholders are Appendix A with the values it leaves out filled in

- **Status:** Proposed
- **Date:** 2026-11-09

- Until calibration replaces them, the engine renders with one style, `tight`, built in code in `render/style.py` and marked `placeholder`. No file in `data/styles/` exists yet, so nothing on disk looks calibrated, and `medium` and `loose` arrive with calibration ([ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)). Calibration loads its TOML files into the same `Style` model, extending it where it fits by metric level and tempo band, and checks its values against this table.
- Appendix A's "beats" are quarter notes. `e` is a note's energy, after its section's arc; `g`, `d`, `t`, `f`, `fi` and `gl` are `groove`, `dynamic_range`, `tightness`, `feel`, `fill_intensity` and `ghost_level`.

| What | Placeholder |
|---|---|
| Default controls | energy 0.5, groove 0.5, dynamic_range 0.5, tightness 0.75, feel 0, arc `steady`, fill_intensity 0.5, ghost_level 0.5, skip off |
| Velocity centers at energy 1.0, 0.5, 0.2 | kick 122, 104, 85; double kick 118, 100, 82; snare backbeat 123, 100, 80; other snare 106, 88, 68; rider 114, 95, 72; accent cymbal 122, 105, 85 (Appendix A). Fills and the roles Appendix A doesn't list (toms outside fills, the hat pedal, percussion, sample layers) take the other-snare row |
| Between and beyond the anchors | Straight lines through them. Below 0.2 the 0.2 to 0.5 line goes on, so raising energy from 0 still raises velocity. Above 1.0, which only an arc reaches, the 0.5 to 1.0 line goes on |
| Bands | Velocities reflect below the center less 6 for kick and backbeats and less 8 for accent cymbals (Appendix A's 116, 117 and floor 114 at energy 1.0), and below 1 for the rest |
| Velocity noise | SD 2.5 × (0.5 + d), for every role |
| Double kick | Feet ±3 about the center |
| Rider | Strong hits half the gap above the center, weak ones half the gap below: gap (4 + 10d) × (0.6 + 0.8g). One alternating hit is strong and the next weak, or the other way, 0.775 of the time (Appendix A's 0.75 to 0.80) |
| Accent-typed notes | The center plus (2 + 6e) × (0.5 + g), reflected below 127 |
| Soft-typed notes | Center 25 + 30 × (0.6 gl + 0.2 e + 0.2 g), held from 0 to 1 inside, SD 2.5 |
| Fills | The other-snare center + 6 × (fi - 0.5), plus 6, 5, 2 or 0 on a quarter, 8th, 16th or elsewhere, ±2 by hands in turn, and a crescendo rising to 11 × fi over the fill's last 4 quarters at most |
| Feel | Snare and riders +6 ms × f laid back, and 3 ms × f pushed (-3 ms at -1). Snare notes 4 × f louder when laid back, none when pushed |
| Arc | The energy runs from 0.15 below the section's to 0.15 above for `build`, the other way for `drop`, so the section's mean is its own energy |
| Energy drift | One slow process for the song, SD 2 velocity, time constant 64 quarters |
| Timing drift | Three slow processes for the song at 16, 64 and 256 quarters, SD 2.5 ms together (Appendix A) |
| Shared offset per onset | SD 2.2 × (1.5 - t) ms |
| Limb offsets | Snare +1 ms, riders +0.7 ms, others 0, and each hit's own jitter with SD 3 - 1.2t ms, cut to ±4 ms |
| Overall | About 3.7 ms of spread at tightness 0.75 with the drifts at their full spread, and 3.1 ms measured over a 16-bar groove, where the slow drifts show less of theirs: inside Appendix A's 3 to 4 ms. Capped at ±12 ms ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)) |

- How the roles these rows belong to are found, including three readings of Appendix A, is [ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md).

**Why:** The engine needs a value for everything it draws, and Appendix A gives only some. Each of these is the plainest reading of what the plan says a control mainly drives, chosen so raising any control moves its statistic and the tight style stays within the timing the research measured. Writing them in one table lets calibration check every one it replaces.

**Consequences:** Until calibration merges, every render sounds like these placeholders, which no performed MIDI has checked.
