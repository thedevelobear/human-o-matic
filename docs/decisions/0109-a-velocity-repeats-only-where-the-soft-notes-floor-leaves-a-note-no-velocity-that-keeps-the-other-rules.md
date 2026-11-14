# 0109. A velocity repeats on a pitch or a drum only where the soft notes' floor leaves a note no velocity that keeps the other rules

- **Status:** Proposed
- **Date:** 2026-11-14

- The guards of [ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md) keep a note's velocity unlike its neighbours' on its pitch and its drum, except at a note where these three rules can't all hold:
  1. the soft notes' floor, velocity rule 2: its drum has soft-typed notes in its section, so it goes no lower than 1 below the lowest of the drum's other notes there, which near the top leaves a few velocities, such as 123 to 127;
  2. the boundary class, rule 4, when it is next to a rendered note of another section on its pitch or drum: a velocity of its class modulo 4, one or two of those;
  3. the no-repeat rule, rule 3: unlike the note before it on its pitch and on its drum in its section, and any note played as it came in after it.
- There the note keeps its velocity, its draw held in range, and the guards count it under `unmet`. Its velocity can then equal its neighbour's. A velocity repeats nowhere else but where [ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md) already lets an articulation's own velocity range, too narrow for a rule, win over it, and a render's bytes are as before.
- [ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)'s velocity property holds with this exception: two notes in a row on a pitch or a drum, not both played as they came in, share a velocity only at such a note, rendered, not soft, with a soft note of its drum in its section, and no more such notes than `unmet` counts.

**Why:** Avoiding the repeat would mean nudging a note the rules already placed, or loosening the floor or the class, and that costs more than a repeat this rare at full energy. The class is what keeps each section independent of another's draws ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)), so it stays.

**Consequences:** A repeat can play, rarely, on loud notes of a drum with soft notes in their section, at a section's boundary. The plan's "never the same velocity twice in a row on one drum" has this exception.
