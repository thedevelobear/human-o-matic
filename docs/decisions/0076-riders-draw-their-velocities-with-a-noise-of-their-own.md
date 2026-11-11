# 0076. Riders draw their velocities with a noise of their own, Appendix A's 2.5

- **Status:** Proposed
- **Date:** 2026-11-11

- The `Style` model has `rider_noise_sd`: the spread of a rider hit's velocity about its center at `dynamic_range` 0.5, scaled by 0.5 plus `dynamic_range` as `noise_sd` is. Every rider hit not typed soft draws with it, alternating, weak, lone and accent-typed alike. Soft-typed riders keep `soft_sd`, and every other role keeps `noise_sd`.
- The three styles take Appendix A's rider noise, 2.5, kept from the placeholder in `tools/fit_styles.py`'s `KEPT`, and the other roles keep their fitted 5.12. The fit gives the riders more:

| Rider noise at `dynamic_range` 0.5 | Value |
|---|---|
| Appendix A, the placeholder, and the styles | 2.5 |
| The fit: the riders' spread on one drum, with their strong, weak and metric-level means taken out, less what the energy drift adds, the median over 2,787 grooves | 5.23 |
| The same, alternating quarter-note hits only, over 2,415 grooves | 3.99 |
| The other roles' `noise_sd`, fitted | 5.12 |

- The rider gap, 4 to 14 by `dynamic_range` and scaled by `groove`, and the flip rate, 0.775, stay. The draws keep their order, so a section draws the same numbers and its timing is unchanged. Only riders' velocities change, and other notes' only where a guard ties them to a rider: a note held off the velocity of a rider hit before it on its drum, such as the hat pedal, or a soft note held below the lowest normal note of its drum.

**Why:** A render discards the input's velocities and plays an alternation of its own. At the fitted noise, about half the gap at the defaults, a quarter-note ride changes direction on 0.77 of its moves, and on 0.84 at 2.5, where strict alternation would change on every one. Performances ride with their snare only weakly, with a fitted gap under half a step ([ADR 0071](0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)), so their spread about the strong and weak means is no measure of an alternation's noise. One published hi-hat repeats its accent pattern from bar to bar, far above its hit-to-hit variation ([the rider noise against published measurements](../research/2026-11-11-rider-noise-against-published-measurements.md)).

**Consequences:** [ADR 0068](0068-what-calibration-fits-and-what-stays-modelled.md)'s noise, fitted for every role, and its kept values, and [ADR 0071](0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)'s list of the values the fit keeps, are amended by this ADR. A change to the riders' noise is a new ADR, as for any kept value.
