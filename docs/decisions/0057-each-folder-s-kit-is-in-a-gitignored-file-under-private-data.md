# 0057. The kit that reads each folder of performed MIDI is in a gitignored file under `private/data/`

- **Status:** Proposed
- **Date:** 2026-11-10

- `private/data/midi-folders.toml` says, for each folder of `private/midi/` or a folder inside one, the built-in kit that reads it (`map = "library/kit"`, or `"library"` for a library with one kit) or why it is left out (`exclude = "..."`). Its keys are paths under `private/midi/`, and a file follows the longest key its path starts with.
- The tracked tools read it through `tools/midi_folders.py`, which checks that each entry has a map or a reason and that each map is a built-in kit. Folders are found by listing `private/midi/`, following links, and no tracked file names a folder, a file in one, or what a folder holds ([ADR 0007](0007-local-only-files-live-in-private.md)).
- `tools/infer_map.py --map LIBRARY[/KIT]` reads any folder through any kit, whatever the file says, so a folder can be checked before it is assigned. A folder whose notes no built-in kit reads, or that copies another, is left out with its reason, and calibration leaves it out too.

**Why:** Which folder holds which library is itself something `private/` holds, so it stays there. A file can be reviewed and changed without code, and a key per subfolder can leave out one pack, or read it through another kit, where matching folders to library ids by name could do neither.

**Consequences:** The assignments are local, like the files they describe, so CI never reads them, and the private tests check that each assigned folder reads as recorded.
