# 0068. What calibration fits, by energy, metric level and tempo, and what stays modelled or placeholder

- **Status:** Accepted. Its fitting of the rider gap, accent and fill crescendo, and three premises of its check, are amended by [ADR 0071](0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md), and its noise for every role and its kept values by [ADR 0076](0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)
- **Date:** 2026-11-10

`tools/fit_styles.py` fits the styles on the grooves `tools/calibrate.py` measures, with the engine's own roles (`render/parts.py`, [ADR 0047](0047-roles-come-from-canonical-families-and-the-score.md)) and statistics (`render/measure.py`).

- **Velocities**, shared by the three styles ([ADR 0065](0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md)), on every groove whose velocities aren't flat:
  - A groove's energy is its rank in velocity level among them, from 0 to 1. A role's center at energy 0.2, 0.5 and 1.0 is the median of its mean normal-typed velocity over the grooves ranked within 0.1 of it. A role with fewer than 10 there takes the kick's center plus its median offset from the kick, or the placeholder's center without one.
  - What a note adds by its metric level, a quarter, an 8th, a 16th or elsewhere, is fitted per role as `metric_velocity`, except for riders, whose strong and weak hits alternate, and fills, which have `fill_metric`.
  - The noise is the median spread on one drum in one role, less what the energy drift adds within a groove. The soft center runs from the 10th to the 90th percentile of the grooves' soft means. The fill accents are the median per metric level. The rider gap at the defaults is the median gap of alternating strong and weak hits, the accent a line in energy through the grooves' accent contrast, and the fill crescendo their median rise.
- **Timing**, per band of [ADR 0067](0067-the-bands-are-cut-at-3-and-6-ms.md), on its performed grooves the grid fits, and per tempo band, under 150 BPM and from 150 BPM:
  - A groove's offsets are taken apart as the engine draws them: each limb's mean less the `other` limb's, the spread an onset's hits share, and each hit's own about it. The spread the engine's slow drift adds within 16 bars is taken out of the shared part.
  - A style draws its band's medians at the default `tightness`, 0.75, and the control's shape about them is the placeholder's: the shared spread scaled by 1.5 less `tightness`, each hit's spread from its loose to its tight end in the placeholder's ratio, and the clip in its ratio to that spread.
  - `feel` +1 moves the snare and riders from the band's median feel to its 90th percentile, and -1 to its 10th.
  - A tempo band with fewer than 20 grooves, or fewer than 2 packs, takes the style's timing over every tempo. The style gains `tempo_cuts` and a `timing` per tempo band, and `compile` takes the tempo at the section's first bar.
- **Kept, the placeholder's values exactly:** the controls' defaults and the shapes of their effects (`rider_groove`, `soft_mix`, `fill_shift`, `arc_span`), the feet and hands (`feet`, `fill_hand`), the rider's flip rate, `snare_loudness`, the song's drifts, and the velocity bands, a floor the plan sets.
- **Check:** `tools/calibrate.py fit` prints what runs against Appendix A's directions and the plan's limits: velocity rising with energy, kick and backbeats at energy 1.0 at 118 or more, a rider's strong hits louder, fill accents falling from the quarter to the 16th, a rising crescendo, the snare and riders late, and the pushed side of `feel` smaller.

**Why:** Each fitted value is a statistic the grooves give directly, conditioned on what the plan names, energy, metric level and tempo. Each kept value is one a performance can't give: it plays a control at one setting, doesn't tell feet or hands apart, has no rider labels, and is too short to show the song's drifts.

**Consequences:** A style's timing rests on its band's packs, and the shared velocities on every assigned folder.
