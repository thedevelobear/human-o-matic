# 0095. An addition the target kit can't play is skipped, and the reports count what was added and skipped

- **Status:** Proposed
- **Date:** 2026-11-13

- A rimshot or a choke is written by its canonical name, `snare.rimshot` or `crash.1.choke` for the piece of the note it follows, through the target kit, which the placement carries. When the kit lacks that articulation, or decides it by a controller value, the addition is skipped as `missing`. It is never a decision request, never a substitute from another family or a fallback within one, and never changes a hit's family ([ADR 0021](0021-conversion-falls-back-within-a-family.md)).
- Each creative section has a `CreativeReport`: `added`, its notes by kind, `ghost`, `cymbal`, `fill`, `flam` and `choke`, and `rimshot` for its notes written as rimshots, and `skipped`, by `missing`, `unplayed` and `crowded` ([ADR 0094](0094-an-added-note-changes-no-other-section.md)), then by kind. Kinds and reasons with none are left out.
- `render`'s and `export`'s summary, from the CLI and the MCP server, counts the notes added in `notes.added`, with `written` including them, and the creative sections' reports added together in `creative`, null when none is creative. Each section's row has its own `creative`, null when it is off.
- `says` and `set_section_controls`' `expected` ([ADR 0083](0083-expected-results-are-the-section-rendered-and-measured-by-role.md)) end, for a creative section, with what it added and skipped and why, in words: "creative adds 22 ghost notes and 8 fill notes; skips 2 backbeats as rimshots: the kit has no articulation for them".

**Why:** The user asked for added notes, not a question about them, so a kit that can't play one leaves it out and says so. Counts and words read off the render tell the user what changed in the file they hear, and no reply lists a note ([ADR 0084](0084-the-tools-take-ids-and-paths-and-reply-with-compact-json.md)).

**Consequences:** The summaries of [ADR 0054](0054-human-o-matic-render-writes-a-new-midi-file-by-a-plan-and-prints-json.md) and [ADR 0075](0075-render-s-summary-counts-how-the-notes-were-placed-in-the-target-kit.md) gain `notes.added` and `creative`, and the expected words of ADR 0083 gain the creative ones.
