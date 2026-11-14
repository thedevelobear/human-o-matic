# 0115. The site downloads Pyodide's core release, its numpy, and PyPI's wheels at `uv.lock`'s versions, pinned in `tools/build_site.toml`

- **Status:** Accepted
- **Date:** 2026-11-14

- `tools/build_site.toml` is the committed list of what the build downloads, each by an exact version, its URL and its SHA-256:
  - Pyodide 314.0.7's core release, `pyodide-core-314.0.7.tar.bz2`, from Pyodide's GitHub release, whose SHA-256 GitHub publishes as the asset's digest. The build takes the runtime's five files from it: `pyodide.mjs`, `pyodide.asm.mjs`, `pyodide.asm.wasm`, `python_stdlib.zip` and `pyodide-lock.json`.
  - Pyodide's numpy 2.4.6, from Pyodide's CDN, whose SHA-256 the release's `pyodide-lock.json` gives. It sits beside that lock file, where Pyodide loads it by name and checks it again.
  - From PyPI, at `uv.lock`'s versions, with PyPI's SHA-256s: pydantic-core 2.50.4's WebAssembly wheel, pydantic 2.14.3, annotated-types 0.8.0, typing-extensions 4.16.0, typing-inspection 0.4.5, mido 1.3.3, and packaging 26.3, which mido imports.
- The build downloads them into `build/site-downloads/`, gitignored, refuses and removes any file whose SHA-256 differs, and serves them from the site's own origin. A test holds the PyPI wheels to `uv.lock`'s versions.

**Why:** The core release is one file with a published digest, where the runtime's files one by one would be hashes of our own. PyPI's wheels match what the native engine is tested with, but numpy, which has no WebAssembly wheel on PyPI, so Pyodide's is the one, as ADR 0100 measured.

**Consequences:** CI downloads about 12.0 MB for the build, the release's 6.8 MB and the wheels' 5.2 MB, where ADR 0112 counted about 18.6 MB for the runtime's files one by one. A first visit sends about 11.7 MB, packaging's 0.13 MB more than the plan's sum. Upgrading a wheel in `uv.lock` means its pin too, which the test says.
