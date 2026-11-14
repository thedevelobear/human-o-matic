# 0116. The engine check is `check.html`, which runs `tests/web/flow.json`'s calls on a song built in code, served by `build_site.py serve` with the site's headers

- **Status:** Accepted
- **Date:** 2026-11-14

- `tests/web/flow.json` holds the calls of one whole session, from `open_session` to `download`, and the SHA-256 of the file they give. The same calls run natively in `tests/test_web_site.py`, under Pyodide in Node in `tests/web/engine.test.mjs`, and in a browser in `check.html`, all on `check-song.mid`, a 304-bar song that `tools/build_site.py`'s `built_song` makes in code at build time, with no randomness.
- `check.html` is PR 1's test page: it loads the engine in a module Web Worker with a progress bar, runs the flow, and shows the load's time, each call's, the whole flow's, and whether the download's SHA-256 is the flow's, where the browser can hash, then resets the worker. It has no other UI, stores nothing and asks nothing of another origin.
- `uv run python tools/build_site.py serve` serves `dist/site/` on the owner's machine with the headers of the website plan's section 7, the CSP among them, and nothing cached, so the check shows whether Pyodide runs under that CSP. `--host 0.0.0.0` lets a phone on the same network reach it.

**Why:** One flow in one file keeps the three runtimes making the same calls, so one hash compares them. A real browser is the only place to see the first load, the network and storage panels and the CSP at work, and a check page needs no UI to show them.

**Consequences:** Over plain HTTP, a phone has no `crypto.subtle`, so the page there shows the times but not the hash. The check page and its song stay in the built site until a later PR decides otherwise.
