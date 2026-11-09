# 0047. Roles come from canonical families and the score, never from a pitch

- **Status:** Proposed
- **Date:** 2026-11-09

- `instruments/drums.py` gives each score note a part: its role, which picks the style's velocity row ([ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)), and its limb, which picks the timing offset. It reads families, canonical names, ticks, beats and hit types, and never a pitch or a library ([ADR 0008](0008-library-neutral-drum-maps.md)). Lengths are quarter notes, which is what Appendix A calls beats. Graces take their main note's part. In turn:
  - **Fill:** a run of snare and tom hits at most half a quarter apart, of 3 or more, with a tom or a gap of at most 0.26 quarters (Appendix A), whose last hit is less than 2 bars after its first. Each note has its metric level, a hand by turns from the first, and how far it is into the crescendo over the run's last 4 quarters at most.
  - **Double kick:** a run of 4 or more kick hits at most a 16th apart (Appendix A). The feet alternate from the right, unless a name has `left` or `right`.
  - **Snare backbeat:** a snare hit not typed soft and in no fill, on the start of a beat of the time signature other than the bar's first. Other snare hits are `snare`.
  - **Accent cymbal:** a crash, china, splash or stack hit that is alone, or that starts a run and is on the start of a beat. A run is one cymbal's hits at most a half note apart.
  - **Rider:** hat hits other than the pedal, ride hits, and the crash-family hits that aren't accent cymbals. In a run of one rider's hits at most a half note apart, the hits on a quarter note alternate strong and weak, and the rest are weak. The strong ones are those whose quarter note in the bar has the parity on which more of the run's quarter-note hits land with a snare hit, the even one on a tie. A rider hit alone is at its center.
  - **Other:** everything else, such as toms outside fills, the hat pedal, percussion and sample layers.
- The limb is `snare` for every snare-family note, `rider` for riders, and `other` for the rest.
- Three of these read Appendix A where it can be read two ways: an accent cymbal is a lone hit anywhere or the first of a run on a beat; in 8th and 16th runs only the quarter-note hits alternate; and fills are capped at 2 bars, since Appendix A's rule would otherwise call a long snare roll or a tom groove a fill.
- A rider's strong and weak hits are drawn per section: each alternating hit takes the label the vote gives it, swapped with the chance that makes the flip rate of [ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md) between neighbours, `(1 - sqrt(2 × 0.775 - 1)) / 2`, about 0.13. So most strong hits still land with the snare.

**Why:** Canonical families and the grid are the same for every library, so one rule set serves them all. The half-note run length lets a crash ridden in half notes ride, while a crash on each downbeat stays an accent. Swapping labels one hit at a time keeps the strong hits on the snare, where a chain of flips would wander off it after its first miss.

**Consequences:** A tom groove under 2 bars is still taken for a fill, as [ADR 0036](0036-a-bar-is-its-onset-pattern-in-each-family.md) notes. A name read at low confidence ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)) gives the role its family implies, right or wrong.
