# 0030. Hit types come from clear groups in each family's velocities, and anything else is normal and asked about

- **Status:** Proposed
- **Date:** 2026-11-08

- `normalize/hit_types.py` types the notes of each drum family on their own. Their velocities are split into at most three groups by optimal one-dimensional k-means, an exact dynamic program over the distinct velocities, with numpy only. Three groups are tried, then two.
- A split is accepted when every group has at least 2 notes and neighbouring groups' means are at least 10 velocities and at least 5 pooled standard deviations apart.
- The groups are named from the main level. Normal is the largest group whose mean is above 0.6 of the loudest group's, the louder of two that tie. A quieter group is soft when its mean is at most 0.6 of normal's, and normal otherwise. A louder group is an accent.
- Without an accepted split every note is normal, at low confidence: `flat` when no two velocities are 10 apart, as with one velocity or one note, and `one_group` when they spread with no clear groups. Clear groups are `clusters`, at high confidence.
- One `hit_types` request is returned with the score ([ADR 0015](0015-unclear-input-is-a-decision-request.md)), to confirm the types: for each family, how it was typed, its confidence, and the count and velocity range of each type. The answer is `hit_types`, per family a `soft_below` and an `accent_from` velocity, either of which may be left out. It gives that family's types at high confidence, and a family answered is not asked about again.
- After this step the input velocities are not used again, except through the score's source notes in a `skip` section ([ADR 0031](0031-the-score-is-frozen-canonical-hits-with-their-source-notes.md)).

**Why:** Only a coarse type survives from the input, since its velocity numbers are rebuilt, so a type is read only where the input shows it clearly, and the user confirms it. Splitting one smooth spread gives about 2.7 standard deviations for a normal spread and 3.5 for a uniform one, so 5, with two notes in each group, keeps a few dozen notes from splitting by chance. 10 velocities keeps small random variation in programmed input from counting as levels. Naming from the main level means a few soft kicks don't make the many loud ones accents, and 0.6 separates ghost notes, well under their backbeats, from accents, which sit nearer the main level.

**Consequences:** Flat input is always asked about, and so is any family whose velocities spread without clear groups. An answer can only give types by velocity, so soft notes in flat input, which have no velocity of their own, can't yet be named one by one. That needs an answer by position, with the MCP layer in M4.
