# 0130. A remap keeps every note's tick, length and velocity, and changes only its pitch and channel

- **Status:** Proposed
- **Date:** 2026-11-16

- A remap reads the drum track's notes ([ADR 0017](0017-the-drums-are-one-whole-track.md)) with the source kit and places each in the target kit by conversion's fallback order ([ADR 0021](0021-conversion-falls-back-within-a-family.md)), through the function a render places notes with, `maps.convert.place`. A note takes the target binding's note, and that binding's channel, or else the kit's, or else its own ([ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).
- Each note keeps its tick, its length, its velocity and its release velocity exactly. The file is written at its own PPQ, not at the working PPQ of [ADR 0014](0014-work-at-a-whole-multiple-of-the-source-ppq.md), so each tick is the same number. Every other track, and every event of the drum track, stays as read.
- A velocity outside its target binding's velocity range is kept, not moved into it, and the report counts those notes for each articulation. This differs from a `skip` section, whose velocities move into the target's range ([ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).
- What the fallback order can't settle is asked as conversion asks it: notes the source kit doesn't map are one `unmapped_notes` request, and a family the target lacks, a missing choke or a controller-bound articulation is a `conversion` request, answered by `unmapped` and `substitutions`, or `drop`. Notes that meet on one target pitch and channel at one tick keep their ticks and are reported as collisions ([ADR 0021](0021-conversion-falls-back-within-a-family.md)).
- A remap needs no tempo, hit types, grids, sections, style or seed, and asks for none. Besides conversion's requests, it can ask only which track holds the drums (`drum_track`).

**Why:** The user's part is finished, and only the kit that plays it changes, so a moved velocity or tick would change a performance the user didn't ask to change. Writing at the file's own PPQ keeps each tick the same number, not only the same time.

**Consequences:** A remap is the one path whose output keeps the input's velocities and timing, so the plan's rule that they are discarded is a re-performance's. No built-in map gives a binding a velocity range yet, so the count of velocities outside one is 0 until a map does.
