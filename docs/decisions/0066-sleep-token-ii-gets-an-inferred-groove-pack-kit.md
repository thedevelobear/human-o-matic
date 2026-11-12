# 0066. Sleep Token II gets a second kit, `groove-pack`, inferred, for the layout its groove files play

- **Status:** Accepted
- **Date:** 2026-11-10

- `sleep-token-ii` ships a second kit, `groove-pack` ("Groove Pack layout"), for the note layout the library's own groove files play, which differs from its default mapping. The library's mapping at hand names only the default layout, so each of the kit's 15 names is inferred from where the library puts its notes, `inferred` at `low` ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)): a kick, a snare's center and rimshot strokes, four toms, a closed hat with its tip stroke and an open hat, a ride's bow and bell, and three crashes.
- A note of the layout played too little, or too unlike any drum, to name is left out, so a note on it is asked about.
- The kit sets no output channel, so a written note keeps its own.
- With two kits, the library is chosen as `sleep-token-ii/default` or `sleep-token-ii/groove-pack` ([ADR 0023](0023-built-in-library-ids.md)).

**Why:** A user's groove from the library's own files reads through this kit rather than as unmapped notes, and calibration reads that layout's velocities ([ADR 0065](0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md)).

**Consequences:** `sleep-token-ii` alone no longer names a kit. The line of [ADR 0011](0011-m1-maps-for-general-midi-and-drum-libraries.md) that every library but `iof-drummer` has one kit, and the line of [ADR 0023](0023-built-in-library-ids.md) naming `iof-drummer` as the library with several kits, are amended by this ADR. Converting from or to the kit reports low confidence on every note until its names are checked.
