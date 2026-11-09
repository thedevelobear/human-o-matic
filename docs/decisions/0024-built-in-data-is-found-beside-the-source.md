# 0024. Built-in data is found in `data/` beside the source, by one function

- **Status:** Proposed
- **Date:** 2026-11-08

- The vocabulary and the maps are read from `data/` at the repository root, beside `src/`, as the plan lays it out. `human_o_matic.resources.data_dir` finds it from the package's own path, and everything that reads built-in data goes through it. No setting or environment variable points it elsewhere.

**Why:** The app runs from the repository (`uv run --directory`), where the path always holds, and one function keeps a later packaging change to one place. With nothing to point it elsewhere, no map from outside the repository is loaded ([ADR 0010](0010-built-in-maps-only.md)).

**Consequences:** A built wheel doesn't contain `data/`, so an installed package can't find its maps. Shipping the data in a wheel needs a new decision.
