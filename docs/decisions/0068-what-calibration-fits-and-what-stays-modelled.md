# 0068. What calibration fits, by energy, metric level and tempo, and what stays modelled or placeholder

- **Status:** Proposed. Its fitting of the rider gap, accent and fill crescendo, and three premises of its check, are amended by [ADR 0071](0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)
- **Date:** 2026-11-10

`tools/fit_styles.py` fits the styles on the grooves `tools/calibrate.py` measures, with the engine's own roles (`render/parts.py`, [ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md)) and statistics (`render/measure.py`), so a fitted number means what the render means by it.

- **Velocities**, shared by the three styles ([ADR 0065](0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md)), on every groove whose velocities aren't flat:
  - A groove's energy is its rank in velocity level among them, from 0 to 1. A role's center at energy 0.2, 0.5 and 1.0 is the median of its mean normal-typed velocity over the grooves ranked within 0.1 of it; a role with fewer than 10 there takes the kick's center plus its usual offset from the kick.
  - What a note adds by its metric level, on a quarter note, an 8th, a 16th or elsewhere, is fitted per role, except riders, whose strong and weak hits already alternate, and fills, which have `fill_metric`. The style gains `metric_velocity`, and every note's part its metric level.
  - The velocity noise is the median spread on one drum in one role, less what the song's energy drift adds within a groove; the rider gap at the defaults is the median gap of strong and weak alternating hits, spread over `dynamic_range` as the placeholder's is; the accent is a line in energy through the grooves' accent contrast; the soft center runs from the 10th to the 90th percentile of the grooves' soft means; and the fill accents and crescendo are the median per metric level and the median rise.
- **Timing**, per band of [ADR 0067](0067-the-bands-are-cut-at-3-and-6-ms.md), on its performed grooves the grid fits, and per tempo band, under 150 BPM and from 150 BPM:
  - A groove's offsets are taken apart as the engine draws them: each limb's mean less the `other` limb's, the spread an onset's hits share, and each hit's own about it. The spread the engine's own slow drift adds within 16 bars is taken out of the shared part, since the drift stays modelled.
  - A style draws its band's medians at the default `tightness`, 0.75, and the control's shape about them is the placeholder's: the shared spread scaled by 1.5 less `tightness`, each hit's spread from its loose to its tight end in the placeholder's ratio, and the clip in its ratio to that spread.
  - `feel` +1 moves the snare and riders from the band's median feel to its 90th percentile, and -1 to its 10th.
  - A tempo band with fewer than 20 grooves, or fewer than 2 packs, takes the style's timing over every tempo. The style gains `tempo_cuts` and a `timing` per tempo band, and `compile` takes the section's tempo, the tempo at its first bar.
- **Kept, the placeholder's values exactly:** the controls' defaults and the shapes of their effects (`rider_groove`, `soft_mix`, `fill_shift`, `arc_span`), which a performance plays at one setting only; the feet and hands (`feet`, `fill_hand`), which MIDI doesn't tell apart; the rider's flip rate, which needs labels a performance doesn't have; the loudness laid-back playing adds (`snare_loudness`), which needs the control; the song's drifts, which loops are too short to show; and the velocity bands, a floor the plan sets for loud kicks and backbeats.
- Before the styles are used, the fit is checked against Appendix A's directions and the plan's limits: velocity rising with energy, kick and backbeats at energy 1.0 at 118 or more, a rider's strong hits louder, fill accents falling from the quarter to the 16th, a rising crescendo, the snare and riders late, and the pushed side of `feel` smaller. `tools/calibrate.py fit` prints what runs against them.

**Why:** Each fitted value is a statistic the grooves give directly, conditioned on what the plan names, energy, metric level and tempo, and each kept value is one a performance can't give.

**Consequences:** A value is only as good as its grooves: a style's timing rests on its band's packs, and the shared velocities on every assigned folder.
