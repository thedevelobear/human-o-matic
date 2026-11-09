# 0012. M1 adds mido, numpy, pydantic and typer, and other runtime dependencies wait for their milestone

- **Status:** Accepted. Its line on `scipy` is amended by [ADR 0041](0041-m2-adds-no-runtime-dependency.md)
- **Date:** 2026-11-08

- M1's runtime dependencies are `mido` (MIDI I/O), `numpy` (quantizer and hit types), `pydantic` (map validation) and `typer` (the `human-o-matic analyze` CLI).
- `scipy` waits for M2 (sections), `python-rtmidi` and `symusic` for M3 (preview and scanning performed MIDI), and `mcp` for M4 (the server). PyTorch stays in M5.
- Each is added with `uv add` at an exact version ([ADR 0004](0004-exact-dependency-versions.md)), in the milestone whose code first imports it.

**Why:** A dependency added before the code that uses it is unexercised weight, and adding it with that code means every version in `pyproject.toml` is one something runs.
