# 0100. The site runs the engine in the browser under Pyodide, from static files

- **Status:** Proposed
- **Date:** 2026-11-13

- The page's Web Worker loads Pyodide and runs the same `Tools` over a `SessionStore` in the worker's in-memory file system. The user's file is read there and the download is made there, so the MIDI never leaves the user's machine.
- Pyodide and its packages are pinned by exact version and SHA-256 in a committed list, and served from the site's own origin. As measured: Pyodide 314.0.7 with its numpy 2.4.6, pydantic 2.14.3 with pydantic-core 2.50.4's WebAssembly wheel, and mido 1.3.3.
- The site is the static files the build makes, and feedback goes to a store the site plan names, apart from the engine. No server runs the engine, and any server of the site's own imports neither numpy nor the engine.
- A committed SHA-256 of a render of a song built in code holds the same session and seed to the same bytes natively and under Pyodide.
- If the owner's check in a browser on their desktop and a phone finds the first load or a render too slow, the engine runs on a server of the site's own instead, as the site plan's appendix sets out.

**Why:** Measured on songs built in code, the code runs under Pyodide unchanged apart from two small fixes, about twice as slow as native, and writes the same bytes, through the whole flow of the tools. The engine then costs no server anything, can't be abused through a server's CPU, leaves nothing to delete, and lets the site be hosted as static files.

**Consequences:** A first visit downloads about 11.6 MB. The browser runs numpy 2.4.6 where `pyproject.toml` pins 2.5.4, and numpy doesn't promise the same stream across versions, so the fixed hash is the check and Pyodide and numpy are upgraded together. `Tools` moves out of `mcp_server.py`, which imports the MCP SDK, `files.name_new` falls back where `os.link` is missing, and testing the Pyodide path needs Node or a browser. A trained backend from M5 wouldn't run under Pyodide as it is.
