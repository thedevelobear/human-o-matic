# 0001. Python 3.12 with uv, ruff, pyright and pytest

- **Status:** Accepted. Its line that pyright is strict on `src/` is amended by [ADR 0058](0058-tools-are-scripts-checked-like-src.md)
- **Date:** 2026-11-08

- The project is Python 3.12 or later, pinned to 3.12 in `.python-version`. The package is `human_o_matic`, in a `src/` layout built with `uv_build`, and `uv.lock` is committed.
- `uv` manages the environment and the lockfile, `ruff` lints (with import order and numpy's rules) and formats, `pyright` checks types (strict on `src/`, standard on `tests/`), and `pytest` with `hypothesis` runs the tests.

**Why:** The work needs an official MCP SDK, numpy and scipy for analysis, mature MIDI libraries, and PyTorch for the model experiment, and all of them are native to Python. Training and inference share one language, and `uv` takes care of the Python environment.

**Consequences:** Runtime dependencies are added by the milestone that needs them. Strict typing may need a small typed wrapper around an untyped library such as `mido`.
