"""The site's build: the page, Pyodide, the wheels and the app's source, as static files in
`dist/site/` (ADRs 0100 and 0112).

`build` downloads Pyodide's core release and the wheels in `tools/build_site.toml` into
`build/site-downloads/`, both gitignored, and refuses any file whose SHA-256 isn't the one the
list gives. It then writes `dist/site/`:
- `pyodide/<version>/`: the runtime's files, taken from the release, and numpy beside its
  `pyodide-lock.json`, where Pyodide loads it by name;
- `wheels/`: the other wheels;
- `app.zip`: `src/human_o_matic/`, `data/` and `skills/human-o-matic/references/vocabulary.md`
  at their repository paths, so `resources.data_dir()` and `resources.skill_dir()` find them;
- the page's own files from `human_o_matic/web/static/`, as they are: `index.html`, `site.css`
  and the modules in `js/`, with the engine check's `check.html`;
- `engine.json`, which tells the page's engine where each of these is and how big;
- for the engine check, `check.html`: `check-song.mid`, a song built in code by `built_song`,
  and `check-flow.json`, the calls it makes on it and the SHA-256 of the file they give
  natively, copied from `tests/web/flow.json`;
- `_headers`, the headers Netlify sends for each path (`headers_file`).
The build fails when a file is 10 MB or more (`check_sizes`).

`serve` serves `dist/site/` on this machine with the headers the site will send, its CSP among
them, for the owner's check in a browser and on a phone on the same network.

Run from the repository root:
    uv run python tools/build_site.py build
    uv run python tools/build_site.py serve [--host 0.0.0.0] [--port 8000]
"""

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from collections.abc import Iterator, Sequence
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import mido
from pydantic import BaseModel, ConfigDict

from human_o_matic.web import static_dir

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tools" / "build_site.toml"
DOWNLOADS = ROOT / "build" / "site-downloads"
SITE = ROOT / "dist" / "site"
APP = ("src/human_o_matic", "data", "skills/human-o-matic/references/vocabulary.md")
"""What the app's zip holds, at these repository paths."""
LEFT_OUT = ("__pycache__", "static")
"""Folders the app's zip leaves out: compiled files, and the page's own, served beside it."""
FLOW = ROOT / "tests" / "web" / "flow.json"
SONG = "check-song.mid"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
"""Every entry of the app's zip is dated the same, so the same source gives the same zip."""
CSP = (
    "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; "
    "connect-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)
HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
"""The headers every response of the site carries (the website plan's section 7). On this
machine's server, without HTTPS, `Strict-Transport-Security` is left out, and nothing is cached."""
HSTS = "max-age=31536000"
"""`Strict-Transport-Security` on the host, which serves HTTPS only: a year, for the site's own
host name, not its subdomains."""
IMMUTABLE = "public, max-age=31536000, immutable"
"""Caching for the folders whose paths name their versions, so an upgrade is a new path."""
MAX_FILE_BYTES = 10_000_000
"""A built file must stay under this: the 10 MB a file Netlify is said to take (the website
plan's section 10)."""


class Pin(BaseModel):
    """A file to download, at an exact version, and its SHA-256."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "pyodide"
    version: str
    url: str
    sha256: str

    @property
    def file_name(self) -> str:
        return self.url.rsplit("/", 1)[1]


class Runtime(Pin):
    files: tuple[str, ...]
    """The runtime's files, taken from the release."""


class Pins(BaseModel):
    """`tools/build_site.toml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pyodide: Runtime
    packages: tuple[Pin, ...]
    """Pyodide's own packages, loaded by name beside its lock file."""
    wheels: tuple[Pin, ...]


def read_pins(path: Path = PINS) -> Pins:
    with path.open("rb") as file:
        return Pins.model_validate(tomllib.load(file))


class HashMismatchError(ValueError):
    """A downloaded file whose SHA-256 isn't the one pinned."""


def fetched(pin: Pin, folder: Path = DOWNLOADS) -> Path:
    """The pinned file, downloaded into `folder` unless it is there already, and checked by its
    SHA-256 either way. Raises `HashMismatchError`, and keeps no file that fails."""
    path = folder / pin.file_name
    if not path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(pin.url, timeout=120) as response, part.open("wb") as out:
            shutil.copyfileobj(response, out)
        part.replace(path)
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != pin.sha256:
        path.unlink()
        raise HashMismatchError(f"{pin.file_name}: SHA-256 {found}, where {pin.sha256} is pinned")
    return path


def app_zip(root: Path = ROOT) -> bytes:
    """The app's source, data and vocabulary at their repository paths, with fixed dates, in
    name order, so the same files give the same bytes."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(_app_files(root)):
            entry = zipfile.ZipInfo(path.relative_to(root).as_posix(), ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    return out.getvalue()


def _app_files(root: Path) -> Iterator[Path]:
    for name in APP:
        path = root / name
        if path.is_file():
            yield path
            continue
        for found in path.rglob("*"):
            parts = found.relative_to(path).parts
            if found.is_file() and not any(part in LEFT_OUT for part in parts):
                yield found


def build(site: Path = SITE, downloads: Path = DOWNLOADS, pins: Pins | None = None) -> Path:
    """Write the site into `site`, replacing what it held, and return it."""
    pins = pins or read_pins()
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(static_dir(), site)
    runtime = site / "pyodide" / pins.pyodide.version
    runtime.mkdir(parents=True)
    with tarfile.open(fetched(pins.pyodide, downloads), "r:bz2") as release:
        for name in pins.pyodide.files:
            member = release.extractfile(f"pyodide/{name}")
            if member is None:
                raise ValueError(f"the release has no file {name}")
            (runtime / name).write_bytes(member.read())
    for pin in pins.packages:
        shutil.copyfile(fetched(pin, downloads), runtime / pin.file_name)
    wheels = site / "wheels"
    wheels.mkdir()
    for pin in pins.wheels:
        shutil.copyfile(fetched(pin, downloads), wheels / pin.file_name)
    (site / "app.zip").write_bytes(app_zip())
    (site / SONG).write_bytes(built_song())
    shutil.copyfile(FLOW, site / "check-flow.json")
    manifest = {
        "pyodide": f"pyodide/{pins.pyodide.version}/",
        "packages": [pin.name for pin in pins.packages],
        "wheels": [f"wheels/{pin.file_name}" for pin in pins.wheels],
        "app": "app.zip",
        "bytes": {
            "runtime": sum((runtime / name).stat().st_size for name in pins.pyodide.files),
            "packages": sum((runtime / pin.file_name).stat().st_size for pin in pins.packages),
            "wheels": sum((wheels / pin.file_name).stat().st_size for pin in pins.wheels),
            "app": (site / "app.zip").stat().st_size,
        },
    }
    (site / "engine.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (site / "_headers").write_text(headers_file(site, pins), encoding="utf-8")
    check_sizes(site)
    return site


def headers_file(site: Path, pins: Pins) -> str:
    """Netlify's `_headers` for the built `site`: `HEADERS` and HSTS on every path, the type of
    each WebAssembly file, and a year's immutable caching under the versioned folders. No two
    rules give one path the same header, which Netlify would send twice."""
    rules: list[tuple[str, dict[str, str]]] = [
        ("/*", {**HEADERS, "Strict-Transport-Security": HSTS})
    ]
    # Each .wasm file by its own path, so no rule needs a wildcard inside a path's last part.
    rules += [
        (f"/{path.relative_to(site).as_posix()}", {"Content-Type": "application/wasm"})
        for path in sorted(site.rglob("*.wasm"))
    ]
    rules += [
        (f"/{folder}/*", {"Cache-Control": IMMUTABLE})
        for folder in (f"pyodide/{pins.pyodide.version}", "wheels")
    ]
    return "\n".join(
        path + "\n" + "".join(f"  {name}: {value}\n" for name, value in headers.items())
        for path, headers in rules
    )


def check_sizes(site: Path) -> None:
    """Raise `ValueError` when the site's largest file is `MAX_FILE_BYTES` or more."""
    largest = max(
        (path for path in site.rglob("*") if path.is_file()), key=lambda path: path.stat().st_size
    )
    size = largest.stat().st_size
    if size >= MAX_FILE_BYTES:
        raise ValueError(
            f"{largest.relative_to(site).as_posix()} is {size:,} bytes, where a file must stay "
            f"under {MAX_FILE_BYTES:,}: see the website plan's section 10"
        )


# The check's song: General MIDI, 4/4 at 140 BPM and 480 PPQ, a form of intro, verse, chorus, verse,
# chorus and breakdown, 76 bars, repeated. Its timing is pushed off the grid by a fixed pattern,
# so it needs no randomness and every build writes the same bytes.
KICK, SNARE, HAT, RIDE, CRASH = 36, 38, 42, 51, 49
TOMS = (50, 48, 47)
SONG_PPQ = 480
SONG_BPM = 140
FORM = (("intro", 4), ("verse", 16), ("chorus", 16), ("verse", 16), ("chorus", 16), ("drop", 8))
SOFT, NORMAL, ACCENT = 35, 96, 120


def _bar_hits(kind: str, bar: int, last: bool) -> list[tuple[int, int, int]]:
    """One bar's `(tick in the bar, pitch, velocity)`: its groove, and a tom fill over its last
    two beats when it ends a section."""
    beat, sixteenth = SONG_PPQ, SONG_PPQ // 4
    hits: list[tuple[int, int, int]] = []
    if kind == "chorus":
        hits += [(n * beat, RIDE, NORMAL) for n in range(4)]
        hits += [(n * sixteenth, KICK, NORMAL - 6 * (n % 2)) for n in range(16)]
        hits += [(beat, SNARE, ACCENT), (3 * beat, SNARE, ACCENT)]
    elif kind == "drop":
        hits += [(n * beat, RIDE, NORMAL) for n in range(4)]
        hits += [(0, KICK, ACCENT), (2 * beat, SNARE, ACCENT)]
    else:
        hits += [(n * beat // 2, HAT, NORMAL - 8 * (n % 2)) for n in range(8)]
        hits += [(0, KICK, NORMAL), (2 * beat, KICK, NORMAL)]
        hits += [(beat, SNARE, NORMAL), (3 * beat, SNARE, NORMAL)]
        if kind == "verse":
            hits.append((beat + 3 * sixteenth, SNARE, SOFT))
    if bar % 4 == 0 and kind != "intro":
        hits.append((0, CRASH, ACCENT))
    if last:
        hits = [hit for hit in hits if hit[0] < 2 * beat]
        hits += [(2 * beat + n * sixteenth, TOMS[n // 3 % 3], NORMAL) for n in range(8)]
    return hits


def built_song(repeats: int = 4) -> bytes:
    """The check's song as a MIDI file: the form `repeats` times, 304 bars by default."""
    bar_ticks = 4 * SONG_PPQ
    notes: list[tuple[int, int, int]] = []
    bar = 0
    for _ in range(repeats):
        for kind, bars in FORM:
            for number in range(bars):
                start = (bar + number) * bar_ticks
                hits = _bar_hits(kind, number, number == bars - 1)
                notes += [(start + tick, pitch, velocity) for tick, pitch, velocity in hits]
            bar += bars
    events: list[tuple[int, int, mido.Message]] = []
    for index, (tick, pitch, velocity) in enumerate(sorted(notes)):
        at = max(0, tick + (index * 7) % 9 - 4)
        events.append((at, 1, mido.Message("note_on", note=pitch, velocity=velocity, channel=9)))
        events.append((at + 30, 0, mido.Message("note_off", note=pitch, channel=9)))
    events.sort(key=lambda event: (event[0], event[1]))
    track = mido.MidiTrack(
        [
            mido.MetaMessage("track_name", name="Drums"),
            mido.MetaMessage("set_tempo", tempo=round(60_000_000 / SONG_BPM)),
            mido.MetaMessage("time_signature", numerator=4, denominator=4),
        ]
    )
    now = 0
    for tick, _, message in events:
        message.time = tick - now
        track.append(message)
        now = tick
    midi = mido.MidiFile(type=0, ticks_per_beat=SONG_PPQ)
    midi.tracks.append(track)
    out = io.BytesIO()
    midi.save(file=out)
    return out.getvalue()


class _Handler(SimpleHTTPRequestHandler):
    """Serves the site's files with its headers, and nothing cached."""

    def end_headers(self) -> None:
        for header, value in HEADERS.items():
            self.send_header(header, value)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(site: Path, host: str, port: int) -> None:
    handler = partial(_Handler, directory=str(site))
    with ThreadingHTTPServer((host, port), handler) as server:
        print(
            f"serving {site}: the page at http://{host}:{port}/ and the engine check at "
            f"http://{host}:{port}/check.html; stop with Ctrl+C"
        )
        server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the site, or serve it on this machine.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="download and check Pyodide and the wheels, write the site")
    serving = commands.add_parser("serve", help="serve the built site with its headers")
    serving.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to reach it from a phone")
    serving.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "build":
        try:
            site = build()
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(json.dumps(json.loads((site / "engine.json").read_text(encoding="utf-8"))["bytes"]))
        return 0
    if not (SITE / "engine.json").is_file():
        print("error: no site to serve; run build first", file=sys.stderr)
        return 1
    with contextlib.suppress(KeyboardInterrupt):
        serve(SITE, args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
