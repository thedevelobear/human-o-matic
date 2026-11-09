# 0018. mido is typed by a local stub in `typings/`

- **Status:** Accepted
- **Date:** 2026-11-08

- `typings/mido/__init__.pyi` declares only the part of mido the code uses, and pyright reads it through `stubPath`. Strict mode stays on for all of `src/`, with no ignore comments.
- Only `midi/io.py` imports mido in the package. It reads and writes raw message bytes, so the stub declares no per-message attributes such as `note` or `tempo`. A new use of mido extends the stub first.

**Why:** mido ships no types, and strict mode rejects an untyped import. A stub is smaller than a wrapper of casts, and keeps the types checked where mido is called.

**Consequences:** The stub must match mido's behavior, so upgrading mido means checking it.
