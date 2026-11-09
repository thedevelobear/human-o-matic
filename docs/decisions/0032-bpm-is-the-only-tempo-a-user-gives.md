# 0032. `bpm` is the only tempo a user gives, and there is no `tempo_map` argument

- **Status:** Accepted
- **Date:** 2026-11-08

- No call takes a `tempo_map`. The file's own tempo events are read, a given `bpm` is a constant tempo that replaces them, and a file with no tempo and no `bpm` is a `tempo` decision request, as [ADR 0016](0016-tempo-and-time-signatures.md) sets out.
- A `bpm` a user gives is one a MIDI tempo event can hold, 1 to 16,777,215 microseconds per quarter note: from 3.577 BPM, rounded up, to 60,000,000 BPM (`MIN_BPM` and `MAX_BPM` in `midi/tempo.py`). The CLI enforces it, and any other `--bpm` is a usage error ([ADR 0033](0033-analyze-takes-flags-and-an-answers-file-and-prints-json.md)). `tempo_map` and `TempoMap.constant` don't check it.
- A song whose tempo changes but whose file has no tempo events can't be given those changes. A changing tempo given by the user is a new decision, made when a real file needs it.

**Why:** A file's own tempo changes are read from it, and `bpm` covers a file with a missing or wrong tempo at one tempo. An argument for a changing tempo, and a format to type it in, would be designed before any file needs them. A tempo outside the range could never be written to the file the song becomes.

**Consequences:** `open_session`, in M4, takes `bpm` in the same range, and no `tempo_map`.
