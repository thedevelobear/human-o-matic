# 0042. An accepted ADR that a later one changes in part is marked amended

- **Status:** Proposed
- **Date:** 2026-11-09

- When a later ADR changes part of an accepted ADR and leaves the rest standing, the accepted ADR's status line becomes `Accepted. Its <part> is amended by [ADR NNNN](NNNN-topic.md)`, naming the part in a few words. It is a fourth form in the status template, beside `Proposed`, `Accepted` and `Superseded by`. An ADR that replaces a whole decision still marks it `Superseded by`.
- The docs index shows the same status text as the ADR's status line.

**Why:** `Superseded by` would say none of the old ADR holds when most of it does. A merged ADR changes only in its status line, so that line is the one place a reader of the old ADR learns that part of it has changed.
