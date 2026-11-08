# 0005. Claude Code works through an orchestrator, a developer and QA

- **Status:** Proposed
- **Date:** 2026-11-08

- Three agents live in `.claude/agents/`:
  - `orchestrator` reads each request, asks the owner what only they can decide, sets up the branch, hands the work out, loops QA's findings back, and reports. It writes no code.
  - `developer` does all the work that changes the repo: code, tests, data, the skill, tooling, docs and ADRs.
  - `qa` runs every check (lint, format, types, tests), then reviews the diff against the plan, the ADRs and the milestone's exit criteria. It changes nothing.
- `.claude/settings.json` makes the orchestrator the session agent. The other agents are subagents that can't start agents themselves, and can't ask the owner questions, so they return them and the orchestrator asks.
- Findings go back to the developer for at most three rounds before the owner is asked.
- The orchestrator stops at each milestone gate. Listening decisions, such as the blind test and the model comparison, and the inputs only the owner has, such as the hand-labelled tracks, belong to the owner, because no agent can hear the output.

**Why:** Each kind of work goes to the agent that knows it, the owner keeps every decision, and nothing is reported done before the full checks and a review have run.

**Consequences:** Claude Code can't stop someone from using the other agents directly, so the orchestrator is the entry point by convention and by the setting. The agents' files change with the process they describe, in the same PR. A domain specialist, such as an agent for the performance engine, can be added when the work calls for one.
