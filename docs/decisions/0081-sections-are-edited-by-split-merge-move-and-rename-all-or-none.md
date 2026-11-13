# 0081. Sections are edited by split, merge, move and rename, applied in turn, all or none

- **Status:** Accepted
- **Date:** 2026-11-12

- `update_sections` takes a list of ops, each with its bars counted from 0:
  - `{"op": "split", "at": bar}` starts a section at a bar inside one. Both halves keep its group, name, controls, words and take.
  - `{"op": "merge", "start": bar}` joins the section that starts there to the one before it, which keeps its own group, name, controls, words and take.
  - `{"op": "move", "start": bar, "to": bar}` moves the boundary at `start` to a bar after the start of the section before it and before the end of its own. Each side keeps what it had.
  - `{"op": "rename", "start": bar, "name": ..., "group": ...}` gives a section a name, a repeat group, or both. A group is a non-empty name.
- The ops are applied in turn. The first that can't be applied fails the call, saying `ops[i] (op): why`, and nothing changes.
- After an edit the session's `sections_source` is `edited`. Repeat groups are never worked out again: a section's group changes only by `rename`.

**Why:** Split, merge, move and rename are the plan's edits. Keeping what a section had means fixing its bars never loses the user's answers, and applying all or none never leaves a half-edited table.

**Consequences:** A split section's halves share their controls until one is set apart.
