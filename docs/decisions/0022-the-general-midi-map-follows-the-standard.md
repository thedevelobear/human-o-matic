# 0022. The General MIDI map follows the GM Level 1 percussion key map

- **Status:** Proposed
- **Date:** 2026-11-08

- `data/maps/gm.toml` (library `gm`, kit `default`, channel 10) maps notes 35 to 81 of the General MIDI Level 1 percussion key map, one articulation per note, each labelled with the standard's name for it. The standard is its only source.
- Note 40, "Electric Snare", is `snare.2.center`, a second snare, as the standard says, not a rimshot. Note 35, "Acoustic Bass Drum", is `kick.2.hit`, at medium confidence, since reading it as a second kick is an interpretation. Its six toms are `tom.1` (50, "High Tom") to `tom.6` (41, "Low Floor Tom").
- A test checks that every note from 35 to 81 has exactly one articulation, and that no other note has one.

**Why:** The General MIDI map should say what General MIDI says, and libraries that put a rimshot on 40 say so in their own maps.
