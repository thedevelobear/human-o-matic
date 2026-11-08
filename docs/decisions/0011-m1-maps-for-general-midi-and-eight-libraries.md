# 0011. M1 ships a General MIDI map and maps for eight drum libraries

- **Status:** Proposed
- **Date:** 2026-11-08

- M1 ships a General MIDI map, built from the General MIDI Level 1 percussion key map, and maps for IOF Drummer (`iof-drummer`), EZdrummer 3 (`ezdrummer-3`), Superior Drummer 3 (`superior-drummer-3`), Addictive Drums 2 (`addictive-drums-2`), SSD5 (`ssd5`), GGD Modern & Massive (`ggd-modern-and-massive`), NI Abbey Road (`ni-abbey-road`) and Sleep Token II (`sleep-token-ii`).
- A source is data for a map, never its model ([ADR 0008](0008-library-neutral-drum-maps.md)). Where a library's mapping names its notes, those names give its articulations. Where a source gives a library's notes but not what each one plays, each name is inferred and stored with low confidence, and raised to high once it is checked in the instrument.

**Why:** These are the libraries whose note mappings are at hand. General MIDI is a published standard, so it needs nothing else.

**Consequences:** A conversion that relies on an inferred name says so in its report until the name is checked. The maps are written in the project's own format ([ADR 0007](0007-local-only-files-live-in-private.md)).
