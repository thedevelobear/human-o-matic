# 0007. Local-only files live in `private/`, which is never committed

- **Status:** Accepted
- **Date:** 2026-11-08

- Files that stay on one machine live in `private/` at the repository root, which `.gitignore` excludes. Nothing in it is committed, copied out of it into the repository, or redistributed. `.gitignore` also excludes `*.mid` and `*.midi` everywhere.
- A test builds the MIDI it needs in code, in `tmp_path`. A test that needs files in `private/` is marked `private`, skips when they are missing, and is left out of CI (`-m "not private"`).
- What the repository keeps that is derived from those files is written in the project's own format, such as a map in `data/maps/`, or is aggregate statistics that don't reproduce a performance.

**Why:** The repo is public, so anything committed and pushed is published. One ignored folder keeps that boundary in a single place that is easy to check.

**Consequences:** CI can't run the private tests, so they run on the owner's machine and in qa's local pass.
