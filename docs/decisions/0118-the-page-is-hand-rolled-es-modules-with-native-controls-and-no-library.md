# 0118. The page is hand-rolled ES modules with native controls and no library

- **Status:** Accepted. Its line that the page uses no library, vendored or fetched, is amended by [ADR 0125](0125-the-page-takes-the-owner-s-design-in-tailwind-from-its-play-cdn-with-google-fonts-the-mascot-as-its-logo-and-a-loading-view.md) and [ADR 0126](0126-the-page-s-tailwind-css-is-built-by-tailwind-s-standalone-cli-pinned-like-pyodide-into-a-committed-file.md)
- **Date:** 2026-11-14

- The page is one HTML file, one stylesheet and a few small ES modules of its own, with the platform's native form controls: option (a) of the site plan's comparison of frontends. Its modules update the DOM themselves. It uses no JavaScript library, vendored or fetched, and has no build step, no import map and no npm package ([ADR 0112](0112-node-with-no-npm-package-runs-the-pyodide-test-and-the-page-s-pure-module-tests.md)).
- The pure modules, the tabs' keyboard and ARIA state, the spring, the question count and the download's name, touch no DOM and are tested by `node --test`, as ADR 0112 sets.
- A small vendored library, htm 3.1.1's single-file build of Preact, was weighed and set aside: it would put a third-party file in the page, to pin and keep current, with a Preact of 2022 inside, for a flow that native controls already serve.

**Why:** No library file to pin, check and upgrade, nothing third-party in the page's own code, and a flow of seven steps needs no more than the platform gives.

**Consequences:** The page's modules write each step's, form's and round's DOM updates themselves. The only third-party code the site serves is Pyodide and its wheels.
