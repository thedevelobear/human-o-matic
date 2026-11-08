# 0032. `bpm` is the only tempo a user gives, and there is no `tempo_map` argument

- **Status:** Proposed
- **Date:** 2026-11-08

- No call takes a `tempo_map`. The file's own tempo events are read, a given `bpm` is a constant tempo that replaces them, and a file with no tempo and no `bpm` is a `tempo` decision request, as [ADR 0016](0016-tempo-and-time-signatures.md) sets out.
- A song whose tempo changes but whose file has no tempo events can't be given those changes. A changing tempo given by the user is a new decision, made when a real file needs it.

**Why:** A file's own tempo changes are read from it, and `bpm` covers a file with a missing or wrong tempo at one tempo. An argument for a changing tempo, and a format to type it in, would be designed before any file needs them.

**Consequences:** `open_session` takes `bpm` and no `tempo_map`.
