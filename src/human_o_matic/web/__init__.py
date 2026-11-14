"""The site: a static page whose Web Worker runs the engine under Pyodide (ADR 0100).

`worker` is what the page's worker calls, and `static/` holds the page's own files, which
`tools/build_site.py` copies into the site with Pyodide, the wheels and the app's source.
"""

from pathlib import Path


def static_dir() -> Path:
    """The page's own files: HTML, CSS and the JavaScript modules."""
    return Path(__file__).resolve().parent / "static"
