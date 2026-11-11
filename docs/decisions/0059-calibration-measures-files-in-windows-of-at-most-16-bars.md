# 0059. Calibration measures each file in windows of at most 16 bars, around what the file leaves open

- **Status:** Accepted
- **Date:** 2026-11-10

- `tools/calibrate.py measure` reads every file of a folder that `private/data/midi-folders.toml` assigns a kit ([ADR 0057](0057-each-folder-s-kit-is-in-a-gitignored-file-under-private-data.md)) through that kit with `normalize()`, as the app reads a song.
- A groove is a file of up to 16 bars, from its first bar with notes to its last. A longer file is cut into the fewest equal windows of at most 16 bars. Its timing is measured only when it has at least 32 notes, graces left out.
- What a file leaves open is measured around, never answered by a guess that changes the numbers:
  - Notes the kit doesn't map are left out of every statistic, and counted.
  - An ambiguous beat keeps the quantizer's best guess ([ADR 0029](0029-unclear-beats-are-one-ambiguous-bars-request.md)), and the files with one are counted.
  - A file without a tempo is normalized at 120 BPM for its velocities alone, and its timing is left out, since its milliseconds would be made up ([ADR 0016](0016-tempo-and-time-signatures.md)).
  - A file that can't be read, or whose drum track is unclear, isn't measured, and is counted with why.
- `measure --excluded` measures the timing of the folders the assignments leave out, apart from everything else, through a kit made in code in which every pitch is a drum of its own, since an offset from the grid needs no name. Nothing else uses those folders.
- It prints, for all the assigned folders pooled and then for each, the counts, the distribution of timing spread of the grooves with performed timing, and the bands a few sets of cuts would make. It writes nothing, since its numbers name folders ([ADR 0007](0007-local-only-files-live-in-private.md)).

**Why:** The engine's own spread at the defaults is measured over 16 bars ([ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)), and slow drift shows more over a longer stretch, so windows of that length keep a groove's spread comparable with it, and keep one long song from counting as one groove. Measuring around an open question, rather than answering it, keeps every number one the file gave.

**Consequences:** A whole measuring run, the left-out folders included, takes about 13 seconds. The fitting that follows reads the same grooves.
