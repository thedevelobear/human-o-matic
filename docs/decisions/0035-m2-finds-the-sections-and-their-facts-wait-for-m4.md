# 0035. M2 finds the sections, and their facts and ASCII pattern wait for M4

- **Status:** Proposed
- **Date:** 2026-11-09

- M2 builds `analyze/sections.py`: the bar features, the self-similarity matrix, the novelty peaks and the repeat groups, with SMF markers winning when a file has them. The measurement of [ADR 0034](0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md) turns the markers off.
- Which SMF events count as markers, how a marker snaps to a bar, and the parameter of the detector's API that turns markers off, since the CLI has no flag for it, are in [ADR 0039](0039-smf-markers-start-sections-at-the-nearest-bar-line.md).
- `human-o-matic analyze` also prints the sections, each with its bars and its repeat group. How they fit the output and exit codes of [ADR 0033](0033-analyze-takes-flags-and-an-answers-file-and-prints-json.md) is decided when this is built, in its own ADR if it changes 0033.
- `analyze/facts.py`, each section's facts and its compact ASCII pattern, is built in M4 with the MCP tools that return them, such as `get_sections`.

**Why:** M2's gate is how accurate the boundaries are, and the facts have no consumer until the MCP layer exists.

**Consequences:** M2's sections carry no facts, so M4 builds them on the sections as M2 leaves them.
