# 0038. A section joins the repeat group it plays most like, from 0.8, and groups are named A, B, C in song order

- **Status:** Accepted
- **Date:** 2026-11-09

- Two sections are as alike as the mean likeness ([ADR 0036](0036-a-bar-is-its-onset-pattern-in-each-family.md)) of their bars compared in order, the first with the first and so on, over the shorter one's length.
- In song order, a section joins the group whose sections it is most alike on average, the first of equals, when that is at least 0.8. Otherwise it starts a group of its own.
- Groups are named A to Z, then AA, AB and on, in the order they first appear. Silent sections made only of empty bars fall into one group, since empty bars are alike. One that starts with a stop or ends with a lead-in ([ADR 0037](0037-boundaries-are-novelty-peaks-that-favour-4-8-and-16-bar-sections.md)) can be kept out of it, since a bar with hits is unlike an empty one.

**Why:** Comparing bars in order means a repeat has to play the same bars in the same order, not just the same mix. The labels give where sections start but not which ones repeat, so 0.8 comes from the likeness alone: no two of the sections the tuned tracks' labels start score between 0.772 and 0.875, and 0.8 sits in that gap. Letters are how the plan's product flow names them.

**Consequences:** Repeat groups aren't scored, since the labels carry boundaries only ([ADR 0034](0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md)). A wrong boundary shifts the bars a section is compared on, so it can split a repeat from its group.
