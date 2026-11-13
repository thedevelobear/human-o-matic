# 0075. `human-o-matic render`'s summary counts how the notes were placed in the target kit

- **Status:** Accepted. Its summary is amended by [ADR 0095](0095-an-addition-the-kit-can-t-play-is-skipped-and-the-reports-count-what-was-added.md)
- **Date:** 2026-11-11

- `human-o-matic render`'s summary gains `conversion`: conversion's own report ([ADR 0021](0021-conversion-falls-back-within-a-family.md)) of how the score's notes were placed in the target kit ([ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)), as counts and names, never notes.
  - `changed`: each source articulation written as another, or left out by a substitution, with its `target`, its `notes` and its inexact `steps` (`piece`, `variant`, `default`, or `picked`), in the order the articulations first appear.
  - `collisions`: per target pitch and channel, the score's grid points where notes from different source pitches land on it, as `convert` reports them: how many points (`count`) and `notes`, the `sources`, and the first 8 `positions` as `[bar, beat]` from 0. The guards keep such notes a tick or more apart ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)), so each is a doubled hit.
  - `low_confidence`: the notes `read` through each `low` confidence articulation of the source kit, and `written` through each of the target's ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)).
- Rendering to the kit the file was read with, `changed` and `collisions` hold only what a substitution picks. The exit codes, the file written and the sections' statistics stay as they were, and nothing is printed while a request is open.

**Why:** A tom moved down the kit, a dropped variant or two drums on one pitch is heard in the DAW, and `convert` already reports them. Counted in the summary, they say where to listen, and stay small whatever the song's length.

**Consequences:** The summary of [ADR 0054](0054-human-o-matic-render-writes-a-new-midi-file-by-a-plan-and-prints-json.md) is amended by this ADR. The drum track's controllers still reach the target kit as read ([ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).
