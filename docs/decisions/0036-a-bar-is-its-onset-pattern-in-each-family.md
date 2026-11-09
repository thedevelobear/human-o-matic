# 0036. A bar is its onset pattern in each drum family, and bars are as alike as the cosine of their patterns

- **Status:** Proposed
- **Date:** 2026-11-09

- The section detector reads the score, never the MIDI notes, so it sees canonical families and no library's notes ([ADR 0008](0008-library-neutral-drum-maps.md)). Graces are left out, as ornaments of their main notes ([ADR 0027](0027-hits-on-one-drum-under-45-ms-apart-are-a-grace-and-its-main.md)).
- A bar is described, for each family in the score, by its onset pattern: the slots of the bar where the family has a hit, at 24 slots to a quarter note, so every point of the four grids ([ADR 0026](0026-a-grid-per-beat-by-timing-error-and-complexity.md)) is a slot of its own. Slots count from the bar's start, and a shorter bar leaves the last ones empty. Each family's pattern in a bar is scaled to length 1.
- Two bars are as alike as the cosine of their patterns put together: the sum over the families both play of their patterns' dot product, divided by the square root of the product of how many families each plays. Two empty bars are alike (1), and an empty bar and one with hits are not (0).
- Density and cymbal type, which the plan lists among the features, are in the patterns: a family's hits are its density, and the cymbal families a bar plays are its cymbal type. There is no fill flag.

**Why:** Scaling each family to length 1 makes every family a bar plays count the same, so 16th hats don't outweigh the kick and snare, and a cymbal coming in or going out is a change. Exact slots tell a triplet feel from a straight one. A fill flag added nothing: a fill bar is already unlike the bars beside it, and the engine's fill rule (Appendix A), runs of snare and tom notes, marked whole tom grooves as fills on the tuned tracks.

**Consequences:** A hit moved by one slot is a different pattern, which is right for a quantized score but makes bars of a busy, varied part less alike than they sound.
