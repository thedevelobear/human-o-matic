# 0058. Tracked tools are scripts in `tools/`, checked as strictly as `src/`, and tested from `tests/`

- **Status:** Proposed
- **Date:** 2026-11-10

- `tools/` holds tracked scripts that aren't part of the app, such as `infer_map.py`. Each runs as `uv run python tools/NAME.py`, and imports the package, and the other tools by module name.
- ruff checks them, and pyright checks them strictly, as it does `src/` (`extraPaths` finds the tools' imports of each other). pytest puts `tools/` on the import path, so tests in `tests/` import the tools as the tools import each other, and build their MIDI in `tmp_path`.
- Code that only makes sense with the files in `private/` stays in `private/tools/` ([ADR 0007](0007-local-only-files-live-in-private.md)).

**Why:** The tools write data that ships, such as the styles in `data/styles/`, so they get the app's checks. Scripts run from the repository need no packaging of their own.

**Consequences:** The line of [ADR 0001](0001-python-312-with-uv-ruff-pyright-and-pytest.md) that pyright is strict on `src/` is amended by this ADR: it is strict on `src/` and `tools/`.
