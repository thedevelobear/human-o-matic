# 0011. M1 ships a General MIDI map and maps for ten drum libraries

- **Status:** Accepted. Its list of libraries is amended by [ADR 0055](0055-m3-adds-maps-for-four-drum-libraries.md)
- **Date:** 2026-11-08

- M1 ships a General MIDI map, built from the General MIDI Level 1 percussion key map, and maps for ten libraries: IOF Drummer (`iof-drummer`), EZdrummer 3 (`ezdrummer-3`), Superior Drummer 3 (`superior-drummer-3`), Addictive Drums 2 (`addictive-drums-2`), SSD5 (`ssd5`), GGD Modern & Massive (`ggd-modern-and-massive`), NI Abbey Road (`ni-abbey-road`), Logic Pro Drums (`logic-pro-drums`), GarageBand Drums (`garageband-drums`) and Sleep Token II (`sleep-token-ii`).
- `iof-drummer` has two kits, `default` and `old`, its previous layout an octave lower. Every other library has one. A second layout for `ggd-modern-and-massive`, which reads note 46 differently, waits until that note is checked in the instrument.
- EZdrummer 3 and Superior Drummer 3 have the same notes, and still ship as two libraries.
- A source is data for a map, never its model ([ADR 0008](0008-library-neutral-drum-maps.md)). Where a library's mapping names its notes, as Sleep Token II's does, those names give its articulations. Where a source gives a library's notes but not what each one plays, as for the other nine, each name is inferred at low confidence ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)).

**Why:** These are the libraries whose note mappings are at hand, and a user chooses a map by the library they have. General MIDI is a published standard, so it needs nothing else.

**Consequences:** A conversion that relies on an inferred name says so in its report until the name is checked. The maps are written in the project's own format ([ADR 0007](0007-local-only-files-live-in-private.md)).
