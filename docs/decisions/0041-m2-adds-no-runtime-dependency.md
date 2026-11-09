# 0041. M2 adds no runtime dependency, and `scipy` waits for code that imports it

- **Status:** Proposed
- **Date:** 2026-11-09

- The section detector, the label reader and the scoring use numpy, pydantic and the standard library's `tomllib`, which M1 already has. M2 adds no runtime dependency.
- `scipy` is added with the first code that imports it, by the rule of [ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md), instead of in M2.

**Why:** The detector's peaks, its dynamic program and its grouping are a few lines of numpy each. scipy would bring a large package and a type stub ([ADR 0018](0018-mido-is-typed-by-a-local-stub.md)) for none of them.
