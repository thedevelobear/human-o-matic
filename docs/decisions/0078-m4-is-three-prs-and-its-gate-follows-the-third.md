# 0078. M4 is three PRs, the MCP server, the skill and the blind test, and its gate follows the third

- **Status:** Proposed
- **Date:** 2026-11-12

- M4 lands in three PRs, in this order, each a branch from `main` after the one before it has merged ([ADR 0003](0003-branches-off-main-merged-without-squashing.md)):
  1. `feat/mcp`: `session.py`, `analyze/facts.py`, `mcp_server.py` and the plan's MCP tools, with the `mcp` dependency the plan gives M4 ([ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md)).
  2. `feat/skill`: `skills/human-o-matic/SKILL.md`, `references/vocabulary.md`, and the check of about 30 answers against expected control ranges, run through a real agent session.
  3. `feat/blind-test`: `tools/make_ab.py` and the blind test's five variants.
- M4's gate, the blind listening test the owner judges, follows the third PR. The plan's progress table says which of the three is under way.

**Why:** The skill is written and checked against tools that exist, and the blind test's guided variant is rendered through the skill's questions, so each PR needs the one before it. Each is smaller to review than all of M4.

**Consequences:** Until the skill merges, an agent has only the server's instructions and the tools' descriptions to go on, not the question policy.
