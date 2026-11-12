# 0072. `docs/research/` holds published measurements compared with the project's values

- **Status:** Accepted
- **Date:** 2026-11-10

- `docs/research/` holds research pages, named `YYYY-MM-DD-topic.md` and indexed in `docs/README.md` beside the plans and decisions. A page compares the project's values with published measurements.
- A page cites each source in full, by authors, year, title, venue and DOI or URL, and says what it gives, how sure it is and what it can't say. It lists the sources that couldn't be opened, with no figures taken from them, and says how it converts units, such as a level into a MIDI velocity.
- A page holds published figures and aggregate values only, and nothing from `private/` ([ADR 0007](0007-local-only-files-live-in-private.md)).
- A page is as of its date. A wrong figure is corrected, and a later look at the same values is a new page. What a page leads to is decided in an ADR.

**Why:** The evidence behind a value outlives the plan and is larger than a decision, so it gets a place of its own that an ADR can point at.

**Consequences:** [ADR 0002](0002-docs-as-decision-record.md)'s layout, `plans/` and `decisions/`, is amended by this ADR.
