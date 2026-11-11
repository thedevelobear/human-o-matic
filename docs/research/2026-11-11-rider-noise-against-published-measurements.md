# The rider noise against published measurements

- **Date:** 2026-11-11
- **Compares:** the riders' velocity noise, `rider_noise_sd`, and the alternation it blurs, the rider gap and flip rate, in `data/styles/` and the placeholder as committed on that date.
- **Decided from it:** [ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md). This folder's rules are in [ADR 0072](../decisions/0072-docs-research-holds-published-measurements-compared-with-the-project-s-values.md).

A rider's quarter-note hits alternate strong and weak, the strong ones with the snare, by a gap of 4 to 14 from `dynamic_range`, and the labels swap so neighbours differ 0.775 of the time ([ADR 0047](../decisions/0047-roles-come-from-canonical-families-and-the-score.md)). Each hit then takes noise. The fit gives riders more noise than Appendix A, and the two published studies found say something of how clear the alternation is, and nothing of the noise's size in MIDI.

## Summary

| Value | Placeholder | Fit | What research gives | Confidence | Kept |
|---|---|---|---|---|---|
| `rider_noise_sd` | 2.5 | 5.23 with the strong, weak and metric means taken out; 3.99 on alternating quarter-note hits only | One hi-hat's accent pattern repeats bar to bar with a mean correlation of 0.88; no spread per hit | Low, in direction only | The placeholder |
| The alternation's side and strength | Strong with the snare, gap 4 to 14 | Gap under half a step ([ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)) | Three jazz drummers accent the ride on 2 and 4, on 1 and 3, or on neither | Low | Unchanged |

## Rider noise

`rider_noise_sd` is the spread of a rider hit's velocity about its center at `dynamic_range` 0.5. The fit measures, on each drum of each groove, the spread of the riders' normal-typed hits about the means of their strong, weak and metric-level classes, and takes the median over the grooves, less what the engine's energy drift adds within one: 5.23 over 2,787 grooves, and 3.99 over 2,415 on the alternating quarter-note hits alone. The other roles' fitted noise is 5.12. Appendix A gives the riders 2.5.

- **Räsänen et al. (2015)** measured one recorded hi-hat, a one-handed 16th-note part at 96 BPM with 931 onsets, each onset's amplitude the peak of the signal's envelope after a high-pass filter, in arbitrary units. Over the first ten bars of the intro, the amplitude patterns of the bars correlate with each other with a mean coefficient of 0.88, and 0.93 and 0.92 over the odd and the even bars alone, against 0.48 for the intervals: "each repetitive phrase of the song, consisting of two bars and 32 hi-hat hits, has a specific amplitude pattern". The accents on every second 16th note are "clearly audible", in the pattern "high—low—medium—low—very high", the very high with the snare. Over the whole track the amplitudes are long-range correlated, with a DFA exponent of 0.63, so some of their variation is slow.
- **What it can't say:** it gives no spread of a hit about its place in the pattern, and no means per place, so its figures can't be turned into a noise in MIDI steps. Its pattern includes the 16ths against the 8ths and beats, a larger contrast than the quarter-note alternation alone. It is one drummer on one track, through a filter that favours harder, brighter strokes, with the snare sounding on the accented beats.
- **Confidence:** low, and in direction only. A pattern that repeats this closely puts the hit-to-hit variation well below the pattern's contrast, which agrees with a noise small against the gap, as 2.5 is against the default gap of 9, more than with 5.23. The long-range correlation is what the engine's energy drift models apart from the noise.
- **Kept:** the placeholder, 2.5.

## The alternation's side

- **Hofmann, Wesolowski and Goebl (2017)** recorded three jazz drummers on an electronic kit, its MIDI giving the drum notes, in trios at 168 and 208 BPM. "Among the velocities of the ride cymbal taps falling on the quarter beat notes", they "observed individual patterns for all three drummers" (section 2.2.2.2, Fig. 4a): one emphasised beats 2 and 4, one beats 1 and 3, and one played all four beats evenly. Note velocities were "performer-dependent but also influenced by the tempo" (section 4).
- **What it can't say:** the text gives no velocities, spreads or gaps, and this page reads none off Fig. 4a. It is jazz ride on quarter notes, three drummers, with no snare to vote by.
- **Confidence:** low. It shows that a ride's alternation, where there is one, is a drummer's own, on either side or none. That agrees with an alternation that isn't strict and with ADR 0071's fitted gap near none over many performances, and doesn't size the noise.
- **Kept:** the rider gap, 4 to 14, the strong side with the snare, and the flip rate, 0.775, unchanged.

## Units

No figure on this page is converted to MIDI: Räsänen et al. give amplitudes in arbitrary units and no spread per hit, and Hofmann et al. give no velocity in the text. The conversion the [styles page](2026-11-10-styles-against-published-measurements.md#how-velocity-is-converted-to-midi) uses would apply to an amplitude ratio, and none is given here.

## Sources that could not be opened

No figure on this page comes from these.
- Parsons, W., Cholakis, E. (1995). "It don't mean a thang if it ain't dang, dang-a dang!" *Downbeat*, 61, as Hofmann et al. cite it, with no volume. Read only through Hofmann et al. (2017), as finding the backbeats of a jazz ride dynamically emphasised over beats 1 and 3.

## Sources

- Hofmann, A., Wesolowski, B. C., Goebl, W. (2017). "The Tight-interlocked Rhythm Section: Production and Perception of Synchronisation in Jazz Trio Performance." *Journal of New Music Research* 46(4), 329–341. [doi:10.1080/09298215.2017.1355394](https://doi.org/10.1080/09298215.2017.1355394). Open copy: <https://pmc.ncbi.nlm.nih.gov/articles/PMC5706983>
- Räsänen, E., Pulkkinen, O., Virtanen, T., Zollner, M., Hennig, H. (2015). "Fluctuations of Hi-Hat Timing and Dynamics in a Virtuoso Drum Track of a Popular Music Recording." *PLOS ONE* 10(6), e0127902. [doi:10.1371/journal.pone.0127902](https://doi.org/10.1371/journal.pone.0127902)
