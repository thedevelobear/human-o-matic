# 0114. The worker API takes the file's bytes and its display name beside `open_session`, and answers an error as `{"error": why}`

- **Status:** Accepted
- **Date:** 2026-11-14

- `web/worker.py`'s `handle(request, data)` takes `{"call": name, "args": {...}}` as JSON text, with the chosen file's bytes as `data` beside an `open_session`, and returns compact JSON text, or a `download`'s MIDI bytes. Each tool's arguments are the MCP server's, checked against the same signature by pydantic's `validate_call`; `open_session` takes `name`, the file's display name, in place of `midi_path`, which it refuses.
- An argument, a file or a request it can't use is `{"error": why}`, in plain words, with each song file's path replaced by its display name, and any message that would still name a file of the worker's replaced by "the engine couldn't read its own files; start over". A crash in the engine is the page's to report, without its text.
- The browser's limits count a file's MIDI messages as its events, two for each note and one for each other event, and its bars to the end of its longest track. A refused file is never written. An `open_session` that keeps no session, a tempo or drum track request, removes its file.
- `download` gives the decision requests as `{"decisions": [...]}` while any is open, as `render` does, and `reset` answers `{"reset": true}`.

**Why:** The bytes come from the page's file picker, so no path from the page reaches the worker's file system, and a display name makes the errors readable without one. One error form lets the page show any refusal the same way. Counting messages makes the event limit what a file holds, whatever its notes.

**Consequences:** The page sends the file again to open it again with `bpm` or `track`, or with other kits.
