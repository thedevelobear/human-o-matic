# 0117. M7 is built before M5

- **Status:** Proposed
- **Date:** 2026-11-14

M7, the website, is built now, after M4's gate and before M5, the trained model experiment. M5 stays not started.

**Why:** M5 is an experiment that may be archived, while the site lets musicians without Claude Code try the app and say what they hear.

**Consequences:** `AGENTS.md`'s rule that milestones are done in order has this exception. A trained backend from M5 would need its own path in a browser, since PyTorch is not among Pyodide's packages (ADR 0100).
