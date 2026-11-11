# The styles against published measurements

- **Date:** 2026-11-10
- **Compares:** the styles in `data/styles/` and the placeholder, Appendix A with the values [ADR 0051](../decisions/0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md) fills in, as committed on that date.
- **Decided from it:** [ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md). This folder's rules are in [ADR 0072](../decisions/0072-docs-research-holds-published-measurements-compared-with-the-project-s-values.md).

The styles are fitted on performed MIDI ([ADR 0068](../decisions/0068-what-calibration-fits-and-what-stays-modelled.md)), and each fitted value is an aggregate over many grooves. This page compares six values with published measurements of drummers: the ones where the fit and the placeholder differ and the fit runs against Appendix A or [ADR 0052](../decisions/0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)'s tests. The published studies are few and small, and rarely measure what the engine draws, so they check a value's direction and size more than they give one.

## Summary

| Value | Placeholder | Fit | What research gives | Confidence | Kept |
|---|---|---|---|---|---|
| `medium` `feel_ms`, laid back and pushed | 6, 3 ms | 2.21, 2.35 ms | No comparison of one drummer's two sides | None | The fit |
| `loose` `feel_ms`, laid back and pushed | 6, 3 ms | 4.10, 3.32 ms | The same. Backbeats in recorded rock placed late and early, by up to about 1% of a beat | None | The fit |
| `loose`'s riders from 150 BPM | +0.7 ms | -1.31 ms | Jazz ride taps late against the foot's hi-hat, by 8.6 to 27.9 ms | Low, in sign only | The fit |
| `fill_crescendo` | 11 | 0 | No measurement found | None | The placeholder |
| `accent` | 2 + 6 × energy | 33.21 - 11.95 × energy | Accented strokes about twice as fast at every dynamic level | Medium for the ratio, low in MIDI | The placeholder |
| `rider_gap` | 4 to 14 | 0.11 to 0.39 | A clearly audible alternation on a 16th-note hi-hat | Low, very low in MIDI | The placeholder |

## Feel: `medium` and `loose`

`feel_ms` is how far `feel` +1 moves the snare and riders late, and how far -1 moves them early. The fit takes the feel of each band's grooves, the snare and riders' mean offset from the kick ([ADR 0061](../decisions/0061-calibration-measures-the-engine-s-statistics-with-feel-against-the-kick.md)), and sets laid back from its median to its 90th percentile and pushed from its median to its 10th. `medium` pushes further than it lays back, and `loose` lays back 1.23 times as far as it pushes, where Appendix A's 6 and 3 ms make laid back twice pushed.

- **Carter and von Appen (2025)** measured the kick and snare in 79 recordings by five rock drummers, 15 to 17 each. For the 17 recordings of the drummer with the latest backbeats, "beat 1 to 2 averages approximately 6 ms of delay", and the mean delay was 0.9% of a beat on beat 2 and 1.0% on beat 4. Another of the five placed both backbeats early on average, by 0.6% and 0.9%. At 120 BPM, 1% of a beat is 5 ms.
- **What it can't say:** these are habitual placements, with no instruction to push or lay back, so they don't compare one drummer's pushed and laid-back sides, which is what `feel_ms` sets. Hi-hats and rides weren't measured. They show only that recorded rock places backbeats early as well as late, by similar amounts.
- **Confidence:** none for the two sides. The 6 ms backbeat falls inside Appendix A's laid-back range, which says nothing of the pushed side.
- The study that measured instructed laid-back, on-the-beat and pushed playing, Câmara et al. (2020), couldn't be opened (below).
- **Kept:** the fit, for both styles.

## Riders at fast tempos: `loose`

A style's timing has two tempo bands, cut at 150 BPM. `timing.limb_ms.rider` is the riders' mean offset from the other drums: `loose` plays them 0.21 ms late under 150 BPM and 1.31 ms early from 150 BPM, where the placeholder has them 0.7 ms late at every tempo.

- **Hofmann, Wesolowski and Goebl (2017)** recorded three jazz drummers with bassists on an electronic kit, its MIDI shifted to remove the kit's 5 ms delay, at 168 and 208 BPM, both above the cut. On beats 2 and 4, where the foot plays the hi-hat, every drummer's ride came after it, by a mean of 27.9, 13 and 8.6 ms (section 2.2.2.3). Against the bass the ride averaged 2.1 ms late, 5.3 and 1.4 ms for two of the drummers. The third's figure didn't render in the copy read, so it isn't given here. The song had no significant effect on it, so it shows no sign that 208 BPM differs from 168.
- **What it can't say:** it is jazz, with the ride measured against a foot's hi-hat or a bassist, not a rock or metal rider against the kick, and its offsets aren't split by tempo. It gives nothing below 150 BPM.
- **Confidence:** low. It agrees with the placeholder in sign only, and its offsets are far larger than either value.
- **Kept:** the fit.

## Fill crescendo

`fill_crescendo` is the rise over a fill's last 4 quarters at most, times `fill_intensity`. The grooves' fills fit no rise, 0, where Appendix A has 11.

- No published measurement was found of a rise in velocity, level or stroke speed across performed fills. The searches found programming tutorials, which use a ramp as a convention, work on detecting or generating fills, and a timing study that left fills out.
- **Confidence:** none.
- **Kept:** the placeholder, 11. At 0, `fill_intensity` wouldn't move the fill rise, the statistic ADR 0052 tests it on.

## Accent

An accent-typed note is louder than its center by `accent`'s first value plus its second times the energy, scaled by 0.5 plus `groove`. At the default `groove` the placeholder adds 2 at energy 0 and 8 at energy 1, and the fit 33 and 21. The fit's accents shrink as energy rises and push past 127, so their contrast falls as `groove` rises, against ADR 0052's test.

- **Dahl (2011)** summarises Dahl (2004): four players played an ostinato with an accent every fourth stroke, at pp, mf and ff and three tempi, with 288 strokes behind each point. "The increase in striking velocity for the accented stroke is by about a factor of 2 for all the dynamic levels." The stroke before an accent is softer, and the interval after it is lengthened, less so as the level rises.
- **In MIDI**, twice the stick velocity is about 1.41 times the velocity if the sound's amplitude follows the stick, or twice if a velocity is read as stick velocity (see the conversion below). An unaccented 60 then becomes about 85 or 120.
- **What it can't say:** the strokes are on one drum or pad, not a groove on a kit or a cymbal, by four players. It doesn't say whether the ratio holds near the top of the range, where the fitted centers at energy 1.0 sit at 123.6 to 127.
- **Confidence:** medium for the ratio, a grand average over four players, and low for its size in MIDI.
- It agrees with the fit that an accent is large, 20 steps or more, and with the placeholder that the contrast grows with the level, since a constant ratio adds more to a louder note. It doesn't support accents shrinking as energy rises.
- **Kept:** the placeholder, for its direction and ADR 0052's test, though the measurement suggests accents larger than its 8 steps at energy 1.

## Rider gap

`rider_gap` is the gap between a rider's strong and weak alternating hits at `dynamic_range` 0 and 1. Only quarter-note rider hits alternate, the strong ones with the snare ([ADR 0047](../decisions/0047-roles-come-from-canonical-families-and-the-score.md)). The fit's gap, under half a step, can't move by the 2 steps ADR 0052's test asks of `dynamic_range` and `groove`.

- **Räsänen et al. (2015)** measured one recorded track, a one-handed 16th-note hi-hat at 96 BPM with 931 onsets, each onset's amplitude the peak of the signal after an 8 kHz high-pass filter, in arbitrary units. The accents "on the every second 16th note" are "clearly audible", in a pattern of high, low, medium, low and very high, the very high with the snare. The paper gives no ratio or dB.
- **Read off its Fig. 6(b)**, roughly: weak 16ths mostly 0.02 to 0.07, the 8ths between the beats 0.06 to 0.26, beats 1 and 3 0.16 to 0.40, and beats 2 and 4, with the snare, 0.22 to 0.56.
  - The 8ths and beats are 3 to 8 times the weak 16ths, 10 to 18 dB, or 1.7 to 2.8 times in velocity.
  - Beats 2 and 4 against beats 1 and 3, the alternation the engine draws, are about 1.07 and 1.29 times by their medians, 1.03 to 1.14 times in velocity: a gap of about 4 to 14 steps at the fitted rider center of 113 at energy 0.5. The snare's own sound through the filter may account for some or all of it.
- **What it can't say:** one drummer on one track. The filter favours harder strokes, which are brighter, and the snare sounds on beats 2 and 4.
- **Confidence:** low, and very low for the figures in MIDI.
- **Kept:** the placeholder, 4 to 14. Both readings give a gap far larger than the fit's.

## How velocity is converted to MIDI

- **Dannenberg (2006)** measured how synthesizers turn MIDI velocity into peak RMS amplitude. In all but one, velocity was about linear in the square root of the amplitude, a square law. Their dynamic range from velocity 1 to 127 ran from 11 to 89 dB, and the paper suggests 20 to 60 dB as typical. No one conversion holds for every instrument, so every MIDI figure here depends on the sampler's curve.
- This page takes an amplitude ratio R as √R in velocity, leaving out the curve's offset, and as 20 log10 R in dB. A ratio of stick velocities is given both ways: as an amplitude ratio, if the sound follows the stick, and as a velocity ratio.

## Sources that could not be opened

No figure on this page comes from these.
- Câmara, G., Nymoen, K., Lartillot, O., Danielsen, A. (2020). "Timing Is Everything…Or Is It? Effects of Instructed Timing Style, Reference, and Pattern on Drum Kit Sound in Groove-Based Performance." *Music Perception* 38(1), 1–26. [doi:10.1525/mp.2020.38.1.1](https://doi.org/10.1525/mp.2020.38.1.1). By its abstract, 22 drummers played a backbeat laid back, on the beat and pushed: the best match for `feel_ms`.
- Danielsen, A., Waadeland, C., Sundt, H., Witek, M. (2015). "Effects of instructed timing and tempo on snare drum sound in drum kit performance." *Journal of the Acoustical Society of America* 138(4), 2301–2316. [doi:10.1121/1.4930950](https://doi.org/10.1121/1.4930950). By its abstract, most of ten drummers played laid-back snare strokes louder.
- Hellmer, K., Madison, G. (2015). "Quantifying Microtiming Patterning and Variability in Drum Kit Recordings." *Music Perception* 33(2), 147–162. [doi:10.1525/mp.2015.33.2.147](https://doi.org/10.1525/mp.2015.33.2.147). Its abstract gives no offset per limb.
- Dahl, S. (2004). "Playing the accent – comparing striking velocity and timing in an ostinato rhythm performed by four drummers." *Acta Acustica united with Acustica* 90, 762–776. Read only through Dahl (2011).

## Sources

- Carter, D. S., von Appen, R. (2025). "Finding a Fingerprint. Microtiming and Tempo Variability in Five Renowned Rock Drummers." *Revue musicale OICRM* 12(2), 80–106. <https://revuemusicaleoicrm.org/rmo-vol12-n2/microtiming-tempo-variability-rock-drummers/>
- Dahl, S. (2011). "Striking movements: A survey of motion analysis of percussionists." *Acoustical Science and Technology* 32(5), 168–173. [doi:10.1250/ast.32.168](https://doi.org/10.1250/ast.32.168). Pre-print: <https://vbn.aau.dk/ws/files/65339564/Dahl_J_AST_review_submi.pdf>
- Dannenberg, R. B. (2006). "The Interpretation of MIDI Velocity." *Proceedings of the 2006 International Computer Music Conference*, 193–196. <https://www.cs.cmu.edu/~rbd/papers/velocity-icmc2006.pdf>
- Hofmann, A., Wesolowski, B. C., Goebl, W. (2017). "The Tight-interlocked Rhythm Section: Production and Perception of Synchronisation in Jazz Trio Performance." *Journal of New Music Research* 46(4), 329–341. [doi:10.1080/09298215.2017.1355394](https://doi.org/10.1080/09298215.2017.1355394)
- Räsänen, E., Pulkkinen, O., Virtanen, T., Zollner, M., Hennig, H. (2015). "Fluctuations of Hi-Hat Timing and Dynamics in a Virtuoso Drum Track of a Popular Music Recording." *PLOS ONE* 10(6), e0127902. [doi:10.1371/journal.pone.0127902](https://doi.org/10.1371/journal.pone.0127902)
