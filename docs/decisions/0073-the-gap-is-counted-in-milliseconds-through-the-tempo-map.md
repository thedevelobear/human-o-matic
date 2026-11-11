# 0073. The gap is counted in milliseconds through the tempo map, so it never takes a note past the cap

- **Status:** Proposed
- **Date:** 2026-11-10

- The guards' same-pitch gap ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)) is counted in milliseconds through the song's tempo map, as the ±12 ms cap is: a note keeps 0.6 of the milliseconds between its grid point and the note before's, measured between their starts, and at least a tick. The gap to a note played as it came in, before or after, is counted the same way.
- A main note and its graces move by one shift in milliseconds, so they keep one offset when a tempo change falls between them. The shift is counted in the main note's ticks, and each grace goes to its nearest tick.
- Between two notes of one section, the gap never takes a note past the cap: the note before is within it, so keeping 0.6 of the gap leaves the later note at most 12 ms less 0.4 of the gap late. A note still goes to a whole tick, which can leave it a fraction of a tick past the cap. Next to a note played as it came in, the cap still wins over the gap, and `unmet` counts it.
- At one tempo, ticks and milliseconds are in proportion, so a song without a tempo change renders the same bytes as before. A tick worked out through milliseconds that is within a millionth of a whole tick is taken as that tick, so float rounding never moves a note by a tick.
- [ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)'s properties follow: **Same pitch** also draws up to 120 tempo changes, often at 60 or 600 BPM, so a change is often 10 to 1 either way, and measures the gap in milliseconds, less half a tick where each note lands. **Cap** draws hats on every 16th of the four bars its changes fall in half the time, with such changes between them. Examples pin hits a 16th or a 32nd apart at the cap either way, with a change of 10 to 1 either way between them, on a grid point, or before the first is played.

**Why:** Appendix A's timing is in milliseconds, converted with the local tempo, and the cap is the plan's hard limit. Counted in ticks, a tempo change between two notes could make the gap's ticks worth more milliseconds than their grid gap, and take a note far past the cap with nothing counted: hats a 16th apart at 600 BPM, slowing to 60 BPM between them, put the second 19.8 ms late. A unit moved by one shift in ticks did the same to a main note across a tempo change from its grace.

**Consequences:** Across a tempo change, a note's gap in ticks can differ from 0.6 of its grid gap in ticks, and a grace and its main keep one offset in milliseconds, not one shift in ticks.
