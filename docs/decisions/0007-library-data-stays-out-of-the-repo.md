# 0007. Library data stays out of the repo

- **Status:** Accepted
- **Date:** 2026-11-08

- Library MIDI and vendor map files are used for learning only. They are read in place, never copied into the repo, and never redistributed. `.gitignore` excludes `*.mid`, `*.midi`, `*.map` and `*.drm`.
- A test builds the MIDI it needs in code, in `tmp_path`. A test that reads the library's files is marked `library`, skips when they are missing, and is left out of CI (`-m "not library"`).
- Calibration commits aggregate statistics only. The maps in `data/maps/` are written in the project's own format from the vendor files, not copied from them.

**Why:** The repo is public, and the library MIDI is used for learning only, not redistributed. Keeping it out of the repo keeps that true, because anything committed and pushed is published.

**Consequences:** CI can't run the tests that depend on real performances, so they run on the owner's machine and in qa's local pass. Anything derived from the library and committed, such as calibrated styles, must be aggregate statistics that don't reproduce a performance.
