# 0112. Node, with no npm package, runs the Pyodide test and the page's pure-module tests

- **Status:** Accepted. Its JavaScript supply chain of Node and the pinned Pyodide alone is amended by [ADR 0118](0118-the-page-s-components-use-one-vendored-file-htm-s-build-of-preact-with-no-build-step-and-no-npm.md)
- **Date:** 2026-11-14

- Node's own test runner, `node --test`, runs two kinds of test, in CI and on the developer's machine: the page's pure modules, the parts of its JavaScript that touch no DOM, such as the tabs' keyboard and ARIA state, the spring, the question count and the download's name; and the Pyodide test, which makes the worker's calls on a song built in code under Pyodide and checks its render against the committed SHA-256.
- No npm package is used: no `package.json`, no lockfile and no `node_modules`. The Pyodide test loads Pyodide and the wheels from the files `tools/build_site.py` downloads and checks by SHA-256 ([ADR 0100](0100-the-site-runs-the-engine-in-the-browser-under-pyodide-from-static-files.md)), so the build runs before it.
- The Node tests are ES modules in `tests/web/`, run as `node --test tests/web/`.
- Node is 26.13.1, a release of Node 26's long-term support line, in a committed `.nvmrc`, which CI's setup step reads and the developer's machine uses through nvm. The PR that adds the first Node test adds `.nvmrc`; a step that sets Node up from it with `actions/setup-node@v7`, pinned by its major tag as `actions/checkout@v7` is, since the workflow takes an exact tag only for `astral-sh/setup-uv`, which publishes no major tag; the build and `node --test` to `.github/workflows/ci.yml`; and the command to `AGENTS.md` and the agents' checks.
- No headless browser, for now. What only a real browser shows, a first load's and a render's time, the network and storage panels, and the keyboard and a screen reader on the real page, stays a checklist the owner runs at `feat/web-engine`'s browser check and at M7's gate.

**Why:** The site's engine runs under Pyodide, so its bytes can only be checked in a JavaScript runtime, and Node's own runner tests the page's logic with nothing installed from npm, so the repository takes on no JavaScript supply chain beyond Node and the pinned Pyodide.

**Consequences:** CI downloads Pyodide and its wheels for the Pyodide test, unless a cache holds them: about 18.6 MB as downloaded, the runtime's 13.5 MB and the wheels' 5.1 MB, as the site plan adds them up, where a browser pulls about 11.6 MB compressed. The developer's machine moves to 26.13.1 from whatever Node it runs. JavaScript gets no linter or type checker, which would need packages. Automated accessibility checks, such as axe, wait for a headless browser, if one is ever approved.
