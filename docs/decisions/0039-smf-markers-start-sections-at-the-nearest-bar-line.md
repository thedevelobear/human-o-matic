# 0039. An SMF marker starts a section at the nearest bar line, and markers win when one starts a section

- **Status:** Proposed
- **Date:** 2026-11-09

- A marker is a meta event of type 6 (Marker), on any track, as tempo and time signatures are read from every track ([ADR 0016](0016-tempo-and-time-signatures.md)). Other events, such as cue points (type 7) and text, are not markers.
- A marker snaps to the nearest bar line, and from halfway through a bar to the next one. A marker that snaps to bar 0, or to a bar at or past the song's bar count, starts nothing, and markers that snap to one bar are one.
- When at least one marker starts a section, the sections start at bar 0 and at the markers' bars, and the drums don't move them. Otherwise the drums set them ([ADR 0037](0037-boundaries-are-novelty-peaks-that-favour-4-8-and-16-bar-sections.md)). The repeat groups come from the drums either way ([ADR 0038](0038-a-section-joins-the-repeat-group-it-plays-most-like.md)).
- `find_sections(song, score, markers=False)` leaves the markers out, as the measurement against hand labels does ([ADR 0034](0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md)). `human-o-matic analyze` has no flag for it. A marker's text isn't used yet.

**Why:** The marker is the SMF event meant for naming a place in a song, which is what DAWs write a song's parts as, and a part someone marked is better ground than a guess. A marker a little before or after a bar line still means that bar. A file whose only marker is at the start says nothing about its sections, so the drums decide.

**Consequences:** A file marked only in places, such as one marker at the chorus, gets only those sections, and the agent's review with the user is what adds the rest.
