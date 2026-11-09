# 0015. Unclear input is a decision request, raised as `DecisionRequired`

- **Status:** Accepted
- **Date:** 2026-11-08

- `human_o_matic/decisions.py` holds one shared type, the frozen pydantic model `DecisionRequest`: a `kind`, a plain-language `message`, `answer_with` (the arguments that settle it, such as `bpm` or `track`), `options` (each a `value` to pass back, a `label` and `details`) and `details`. `model_dump(mode="json")` gives its compact JSON.
- A step that cannot go on raises `DecisionRequired`, which carries the request. A step that can go on but wants something confirmed returns its requests with its result.
- The data counts tracks and channels from 0, as the code does. Messages and labels show channels counted from 1, as instruments and DAWs do.
- M1's first kinds are `tempo` and `drum_track`. Later steps add theirs.

**Why:** The plan returns unclear input as a decision request instead of guessing. With one type, the MCP layer turns each one into JSON the same way, and the agent answers any of them by calling again with the named argument.
