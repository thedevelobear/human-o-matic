# 0071. The fit is the default, research fills what a performance can't give, and a value they disagree on waits for both numbers

- **Status:** Proposed
- **Date:** 2026-11-10

How published research and the performed MIDI combine in a style:
- A style's value is the fit from the performed MIDI by default ([ADR 0068](0068-what-calibration-fits-and-what-stays-modelled.md)).
- Published measurements of drummers supply what a performance can't give, and check what it does. Each comparison is cited in a page in `docs/research/`, with its confidence and what it can't say ([ADR 0072](0072-docs-research-holds-published-measurements-compared-with-the-project-s-values.md)).
- Where the fit and research disagree, or the fit runs against Appendix A or [ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)'s tests, a value doesn't change until the owner has seen both numbers.

Six values, compared in [the styles against published measurements](../research/2026-11-10-styles-against-published-measurements.md):

| Value | Placeholder | Fit | Kept | Why |
|---|---|---|---|---|
| `medium` `feel_ms`, laid back and pushed | 6, 3 ms | 2.21, 2.35 ms | The fit | No measurement opened compares one drummer's pushed and laid-back sides |
| `loose` `feel_ms`, laid back and pushed | 6, 3 ms | 4.10, 3.32 ms | The fit | The same |
| `loose`'s `timing.limb_ms.rider` from 150 BPM | +0.7 ms | -1.31 ms | The fit | The one study, of jazz rides against a foot's hi-hat, has them late by far more than either value, with no split by tempo |
| `fill_crescendo` | 11 | 0 | The placeholder | No measurement was found, and at 0 `fill_intensity` wouldn't move the fill rise |
| `accent` | 2, 6 | 33.21, -11.95 | The placeholder | The fit pushes accents past 127, so their contrast falls as `groove` rises, and the one measurement has the contrast grow with the level, as the placeholder's does |
| `rider_gap` | 4, 14 | 0.11, 0.39 | The placeholder | The fit, under half a step, can't move 2 steps with `dynamic_range` and `groove`, and the one measurement has a clearly audible alternation |

Three premises, from Appendix A and the check ADR 0068 describes, no longer hold a fitted value back:
- **The pushed side of `feel` is smaller:** `medium` pushes 2.35 ms and lays back 2.21.
- **Laid back is about twice pushed:** `loose` lays back 4.10 ms, 1.23 times its pushed 3.32.
- **A rider is never early:** `loose`'s riders from 150 BPM play 1.31 ms before the other drums.

`tools/calibrate.py fit` still prints where a fit runs against them, and `fit --check` passes. The rest of the check stands, with the snare late in every style and tempo band.

**Why:** Performed MIDI measures the engine's own statistics, so its fit leads. The published studies are few, small and rarely in the engine's terms, so they fill gaps and check. Where the two clash, the choice is one of listening, which no agent can make.

**Consequences:**
- [ADR 0068](0068-what-calibration-fits-and-what-stays-modelled.md)'s fitting of the rider gap, accent and fill crescendo, and the three premises of its check, are amended by this ADR. The three values keep the placeholder's, in `tools/fit_styles.py`'s `KEPT`.
- [ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)'s `feel` row is amended by this ADR: the test holds each style's laid-back side to its pushed side in the style's own ratio, not to a smaller pushed side, so `medium`'s `feel` at -1 moves the snare and riders further than at +1.
- A kept value changes with a measurement or a fit that passes the tests, in a new ADR. The measured accents are larger than the placeholder's 8 steps at energy 1, which the listening tests can weigh.
