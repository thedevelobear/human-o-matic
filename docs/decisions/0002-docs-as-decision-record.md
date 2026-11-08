# 0002. docs/ is the decision record

- **Status:** Proposed
- **Date:** 2026-11-08

`docs/` records what was decided and why, indexed by `docs/README.md`:
- `plans/`: plans for multi-PR work, `YYYY-MM-DD-topic.md`, each with a progress table. Each PR updates the active plan. A replaced plan only gets a status line pointing at its successor.
- `decisions/`: one ADR per decision, `NNNN-topic.md`. After merge only the status line changes. A changed decision gets a new ADR that supersedes the old one.
- An ADR is its title, status and date, then the decision, a **Why:** line, and **Consequences:** when they aren't obvious. It states what was decided and why, not who decided, how, or in which PR.

A PR that makes a decision adds its ADR and updates the plan. `AGENTS.md`, which `CLAUDE.md` imports, points coding agents here.

**Why:** The work is spread over many sessions, run by coding agents, and decisions left in chat or PR comments get lost.

**Consequences:** Every PR carries a docs diff for review. ADR numbers follow merge order.
