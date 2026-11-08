# 0008. Drum maps are library-neutral: library, kit and articulation

- **Status:** Proposed
- **Date:** 2026-11-08

- A map describes a library, its kits, and each kit's articulations. Each articulation has a canonical name, its MIDI note or notes, its velocity behavior, its CC behavior, its channel, and a source and confidence.
- Canonical names in `family.articulation` form, such as `snare.center`, `hat.closed.tip` and `crash.1.choke`, are the pivot between libraries. Converting reads notes into canonical names with the source kit's map, and writes them back out with the target kit's map.
- No library is special in the code. Library names appear only as map data.

**Why:** The app is meant for most modern drum libraries, not a chosen few. The same note means different things in different libraries, and a flat note-to-name map loses what they add beyond General MIDI, such as rimshots, sidesticks, chokes, half-open hats, positional articulations, alternate snares and tom variants.

**Consequences:** Supporting a library is adding map data, not code. Every map shares one vocabulary of canonical names, so a new kind of articulation is added to the vocabulary before a map uses it.
