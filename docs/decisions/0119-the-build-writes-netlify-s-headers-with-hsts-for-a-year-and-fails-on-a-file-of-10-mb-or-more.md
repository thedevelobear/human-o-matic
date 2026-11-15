# 0119. The build writes Netlify's `_headers`, with HSTS for a year, and fails on a file of 10 MB or more

- **Status:** Accepted. Its CSP and its page naming no other origin are amended by [ADR 0125](0125-the-page-takes-the-owner-s-design-in-tailwind-from-its-play-cdn-with-google-fonts-the-mascot-as-its-logo-and-a-loading-view.md) and [ADR 0126](0126-the-page-s-tailwind-css-is-built-by-tailwind-s-standalone-cli-pinned-like-pyodide-into-a-committed-file.md)
- **Date:** 2026-11-14

- `tools/build_site.py build` writes `dist/site/_headers`, in the form Netlify reads, with these rules:
  - `/*`: the headers `serve` sends, the site plan's CSP and security headers, and `Strict-Transport-Security: max-age=31536000`, a year for the site's own host name, without `includeSubDomains` or `preload`;
  - each `.wasm` file, by its own path: `Content-Type: application/wasm`;
  - `/pyodide/<version>/*` and `/wheels/*`, whose paths name their versions: `Cache-Control: public, max-age=31536000, immutable`. Every other file keeps the host's own caching.
  - No two rules give one path the same header.
- The build fails, exiting 1 and naming the file, when any file of `dist/site/` is 10,000,000 bytes or more, and the site plan's section 10 says where such a file goes.
- A test builds the site from stand-ins of the pinned downloads, without the network, and holds every path of it to these headers, and the page's own files, all but Pyodide's, the wheels, `app.zip` and the check's song, to naming no other origin.

**Why:** One rule a header keeps the host from sending a header twice, a rule a WebAssembly file needs no wildcard inside a file name, and only paths that change with their version can be cached for good, so the page, `app.zip` and `engine.json` reach a browser as soon as they change. HSTS without subdomains holds the site to HTTPS without binding other sites under the same domain. The 10 MB is the only figure a file found for Netlify, from a community answer.

**Consequences:** The owner checks the served headers with `curl -I` when deploying, in `feat/web-deploy`. A Pyodide whose WebAssembly reaches 10 MB stops the build, at 9,598,218 bytes for 314.0.7.
