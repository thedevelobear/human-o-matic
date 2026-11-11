# 0055. M3 adds maps for Counterkit, NI Drum Lab, Krimh Drums and GGD Matt Halpern Signature Pack

- **Status:** Proposed
- **Date:** 2026-11-10

- Four libraries join the built-in maps, each with one kit, `default`: Counterkit (`counterkit`), NI Drum Lab (`ni-drum-lab`), Krimh Drums (`krimh-drums`) and GGD Matt Halpern Signature Pack (`ggd-matt-halpern`). Their ids follow [ADR 0023](0023-built-in-library-ids.md). Krimh Drums Free has the same note mapping as Krimh Drums, so `krimh-drums` serves both.
- Counterkit's and NI Drum Lab's names come from each library's own note mapping, whose note names count C3 as note 60. Each entry is `mapping`, at `high` where the mapping's name gives the canonical name directly and `medium` where it is interpreted ([ADR 0020](0020-map-files-are-toml-checked-when-they-load.md)).
- Krimh Drums' mapping draws its notes on a keyboard without note numbers. Its numbers count keys from the keyboard's third C, read as note 36, where its main kick is, so every entry is `mapping` at `low` until one note is checked in the instrument. A hat with more open degrees than the vocabulary's four takes each at the nearest of them, and the notes that share a name are read, with the first written.
- GGD Matt Halpern Signature Pack has no note mapping at hand, so each name is inferred from where the library puts its notes, `inferred` at `low` ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)). Most of its notes are at General MIDI's places.
- A note a mapping defines is left out of the map, and listed in the map's header, when its name can't be read with confidence: two hat strokes of Counterkit, two snare strokes of NI Drum Lab, and two notes of Krimh Drums. A note the inferred map has too little behind is left out the same way. A note on any of them is a decision request. The notes whose names are clear but which the vocabulary had no name for are named by the names [ADR 0062](0062-the-vocabulary-adds-damped-strokes-wires-off-and-crash-tips.md) adds.
- NI Drum Lab's percussion slots, whose sound depends on the percussion the kit has loaded, are sample layers ([ADR 0019](0019-canonical-names-follow-one-grammar.md)).

**Why:** A user chooses a map by the library they have, and these four had none. A note left out is asked about, where a nearby name would change what it plays without saying so.

**Consequences:** Sixteen kits ship. Converting from or to Krimh Drums or GGD Matt Halpern Signature Pack reports low confidence on every note until its names are checked, and NI Drum Lab's open hat is controller-shaped, so converting it asks. The list of libraries in [ADR 0011](0011-m1-maps-for-general-midi-and-drum-libraries.md) and the list of ids in [ADR 0023](0023-built-in-library-ids.md) are amended by this ADR.
