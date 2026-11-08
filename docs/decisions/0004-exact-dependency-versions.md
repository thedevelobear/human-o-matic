# 0004. Dependencies use exact versions

- **Status:** Proposed
- **Date:** 2026-11-08

Every direct dependency in `pyproject.toml`, runtime and dev, uses an exact version (`==`). `[tool.uv] add-bounds = "exact"` makes `uv add` write them that way. `uv.lock` is committed, and CI installs with `uv sync --locked`, which fails when the two disagree.

**Why:** `pyproject.toml` then states what runs, and upgrading a direct dependency is always a deliberate change. The lockfile alone moves a range whenever it is regenerated.

**Consequences:** Transitive dependencies are pinned only by the lockfile. The build backend is a range in `[build-system]`, because `uv build` resolves it outside the lockfile.
