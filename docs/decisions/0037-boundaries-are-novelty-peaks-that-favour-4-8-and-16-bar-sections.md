# 0037. Boundaries are novelty peaks chosen to favour 4, 8 and 16 bar sections, and a long silence is a section of its own

- **Status:** Accepted
- **Date:** 2026-11-09

- The novelty at bar `b` at a scale of `L` bars is the mean likeness ([ADR 0036](0036-a-bar-is-its-onset-pattern-in-each-family.md)) within the `L` bars before `b` and within the `L` bars from `b`, each bar with itself included, less the mean likeness between the two. It is averaged over the scales of 2, 4 and 8 bars that fit in the song on both sides, and is 0 where none fits: the first two bars and the last. It needs the likeness of bars at most 15 apart, so it is found 256 bars at a time with the 8 bars either side, and the memory it takes grows with the song's length, not its square.
- A candidate is a peak: a bar with hits whose novelty is above 0, at least the bar before's and more than the bar after's. An empty bar is never one, so a silence shorter than 4 bars ends the section before it, and the drums coming back start the next.
- A stretch of 4 or more empty bars is a section of its own, and its two boundaries are always kept. A stop, a bar just before it whose hits all fall in its first half, starts it. A lead-in, a bar just after it whose hits all fall in its second half, ends it.
- The boundaries are the candidates that score best together: each is worth its novelty less 0.2, and each section that isn't 4, 8 or 16 bars long costs 0.2. A section is at least 2 bars, except between two kept boundaries. An exact dynamic program finds the best choice, the first of equals in bar order, so the same score always gives the same boundaries.

| Parameter | Value | Why |
|---|---|---|
| Scales | 2, 4 and 8 bars | Half a phrase, a phrase and two, within the plan's 2 to 8 |
| Phrase lengths | 4, 8 and 16 bars | The plan's preferred lengths |
| Boundary cost | 0.2 | A boundary needs the bars across it a fifth less alike than the bars on each side |
| Length cost | 0.2 | A section of another length needs a boundary as clear again |
| Shortest section | 2 bars | The smallest scale |
| Shortest silent section | 4 bars | The shortest phrase |

**Why:** A peak of the novelty is where the drums change and then hold, which is what a section boundary sounds like in the drums. Most sections are whole phrases, so a small cost for other lengths settles a boundary that could sit a bar either way, without forbidding sections of other lengths. A silence of a phrase or more is a part of the song in its own right, while a bar or two of it is a break at the end of a section. The costs are the middle of a range found on the three tuned tracks: there the mean F1 is 0.93, any boundary cost from 0.15 to 0.3 with a length cost from 0.1 to 0.4 gives 0.87 to 0.94, and with no length cost the best is 0.87, at a boundary cost of 0.31.

**Consequences:** The boundaries are only as good as the drums' changes. A section the band starts while the drums barely change is missed, and a change of cymbal halfway through an 8-bar section is often taken for two sections of 4. A boundary can land on the fill before a section rather than on its first bar. The costs hold on the tracks labelled after the tuned ones: measured on 2026-11-09, the mean F1 over those 7 tracks is 0.815, above the exit's 0.70 ([ADR 0034](0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md)). The labels can still be corrected, so that figure is the one of that date.
