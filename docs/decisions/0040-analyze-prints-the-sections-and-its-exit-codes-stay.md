# 0040. `human-o-matic analyze` prints the sections beside the summary, and its exit codes stay

- **Status:** Accepted
- **Date:** 2026-11-09

- When there is a score, the line `analyze` prints is `{"summary": {...}, "sections": [...], "decisions": [...]}`, extending [ADR 0033](0033-analyze-takes-flags-and-an-answers-file-and-prints-json.md). Each section is `{"start": bar, "bars": n, "group": "A"}`, in song order, with `start` counted from 0 and `group` its repeat group ([ADR 0038](0038-a-section-joins-the-repeat-group-it-plays-most-like.md)).
- The summary gains `sections`, after `bars`: `{"count": n, "source": "markers"}` when the file's markers set them ([ADR 0039](0039-smf-markers-start-sections-at-the-nearest-bar-line.md)), and `"drums"` when the drums did. The sections' lengths add up to the summary's `bars`.
- The sections are found in the score as it is, with any request open: unmapped notes are left out, and an ambiguous beat keeps its best guess. A `tempo` or `drum_track` request still prints only `{"decisions": [request]}`.
- The exit codes are ADR 0033's, since finding sections asks nothing.

**Why:** A start and a length can't be misread the way an end bar can, inclusive or not. Saying what set the sections tells the agent how far to trust them before it asks the user to check them.

**Consequences:** A script that read the printed line by its keys needs to allow `sections`.
