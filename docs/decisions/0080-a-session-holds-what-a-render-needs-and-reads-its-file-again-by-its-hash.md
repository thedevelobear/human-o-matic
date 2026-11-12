# 0080. A session holds what a render needs besides its file, and reads the file again, checked by its hash

- **Status:** Proposed
- **Date:** 2026-11-12

- `session.py`'s `Session`, a frozen pydantic model, is the session's JSON file ([ADR 0079](0079-sessions-are-json-files-in-the-user-s-state-directory.md)):
  - `version`, 1, and `id`, 12 lowercase hex digits drawn at random, which only names the file and never feeds a render. An ID of any other form is refused, so none can name a file elsewhere.
  - `midi_path`, the input as an absolute path, and `midi_sha256`, the hash of its bytes when the session was opened.
  - `from_map` and `to_map` as `library/kit`, `instrument`, `drums` or `generic`, and `track` and `bpm` as given.
  - `answers`, in the form `render --answers` takes them: `unmapped`, `grids`, `hit_types` and `substitutions` ([ADR 0054](0054-human-o-matic-render-writes-a-new-midi-file-by-a-plan-and-prints-json.md)).
  - `style`, `seed`, 0 until `set_style` gives another, and the song's `controls` and `note`.
  - `sections`, each `start`, `bars`, `group`, `name`, `controls`, `note` and `take`, covering the drums' bars in order, and `sections_source`, `markers`, `drums` or `edited`.
  - `exports`, each file it was exported to: `output`, `report` and the hash of the MIDI bytes written.
- It holds no note. Every tool that needs the song reads the file again, normalizes it with the answers and places it in `to_map`. A file whose bytes no longer match `midi_sha256` is an error that says to open it in a new session, so the same session JSON and seed always give the same bytes ([ADR 0049](0049-each-section-draws-from-its-own-seeded-stream.md)).
- The sections are found once, when the session is opened, on the score as it then is, requests open, as `analyze` finds them ([ADR 0040](0040-analyze-prints-the-sections-and-its-exit-codes-stay.md)). Answers never move them: only `update_sections` does ([ADR 0081](0081-sections-are-edited-by-split-merge-move-and-rename-all-or-none.md)).
- A section's ID in every tool is its first bar, from 0: what `analyze` prints as `start`, what `render --plan` keys a section by, and what keys its stream.
- Controls are set as a merge patch: a control given replaces the one held, one given as null unsets it, and one left out stays. Answers merge by key, and null removes one.
- Every write, the first included, is whole: the session goes to a temporary file in its directory, which then takes its name, a new session's by a link that fails when the name is taken, and a saved one's by replacing it. Where the file system has no hard links, as FAT and exFAT don't, a new session's name is created exclusively and the bytes are copied in, which still refuses a taken name. A hidden temporary file, `.<id>.*.tmp`, is left behind only if the process is killed between writing it and naming it (`files.py`).

**Why:** Reading the file again keeps notes out of the session and the tools, and the hash keeps "the same session and seed give the same file" true when the file changes on disk. One name for a section across the CLI, the session and the engine leaves nothing to translate. A fixed default seed means a session with every default renders, and renders the same each time.

**Consequences:** Moving or changing the input file ends its sessions. Moving a boundary renames the section after it, and draws it anew, since its stream is keyed by its first bar.
