# 0016. Tempo and time signatures come from every track, and a missing tempo is asked for

- **Status:** Proposed
- **Date:** 2026-11-08

- Tempo and time signature events are read from every track, so a conductor track, or a tempo on another track from the notes, works in formats 0 and 1. At one tick the last event wins, in track order and then file order, as a sequencer plays them.
- A file with no tempo event, and no `bpm` given, is a `tempo` decision request. 120 BPM is never assumed. A given `bpm` is a constant tempo that replaces the file's own. Before a file's first tempo event, that first tempo holds.
- A file with no time signature at tick 0 is in 4/4 until its first one, as the MIDI file specification defines, and the time signature map says so (`assumed`). A signature that repeats the one in force changes nothing, wherever it sits. A different one starts a bar at its tick, which ends the bar before it early.
- Conversions precompute the time at each tempo change and find the segment by binary search with `numpy.searchsorted`, so maps of thousands of changes stay fast. Bars and beats count from 0, and a beat is the signature's denominator note. Malformed events (tempo 0, numerator 0, denominator over 64) are left out of the maps and kept in the file.

**Why:** A wrong tempo silently skews every millisecond the engine computes, while a missing time signature only shifts bar numbers, which the user sees when confirming sections. A tempo the user gives is more likely right than the file's, as when an export carries a placeholder.

**Consequences:** `bpm` is the only tempo a user gives, and there is no `tempo_map` argument ([ADR 0032](0032-bpm-is-the-only-tempo-a-user-gives.md)).
