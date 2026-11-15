"""The site's build without the network, its `_headers`, its page's origins and its file sizes,
and the fixed hash: the calls of `tests/web/flow.json` on the check song, built in code,
download the file whose SHA-256 the flow holds, as they must under Pyodide in Node (ADR 0100)."""

import hashlib
import io
import json
import re
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest

from build_site import (
    DOWNLOADS,
    FLOW,
    MAX_FILE_BYTES,
    ROOT,
    SONG,
    HashMismatchError,
    Pin,
    Pins,
    app_zip,
    build,
    built_css,
    built_song,
    check_sizes,
    fetched,
    read_pins,
)
from human_o_matic.midi.io import parse_midi
from human_o_matic.web import static_dir
from human_o_matic.web.worker import Worker


def run_flow(worker: Worker, flow: dict[str, Any], song: bytes) -> bytes:
    """The download the flow's calls give, each other reply checked for an error."""
    session: str | None = None
    for step in flow["calls"]:
        args = json.loads(json.dumps(step["args"]).replace('"$session"', json.dumps(session)))
        request = json.dumps({"call": step["call"], "args": args})
        out = worker.handle(request, song if step["call"] == "open_session" else None)
        if isinstance(out, bytes):
            return out
        reply = json.loads(out)
        assert "error" not in reply, (step["call"], reply)
        session = reply.get("session_id", session)
    raise AssertionError("the flow downloads nothing")


def test_the_flow_downloads_the_file_of_the_fixed_sha256(tmp_path: Path) -> None:
    flow = json.loads(FLOW.read_text(encoding="utf-8"))

    data = run_flow(Worker(tmp_path), flow, built_song())

    assert hashlib.sha256(data).hexdigest() == flow["sha256"]


def test_the_check_song_is_304_bars_built_the_same_every_time() -> None:
    song = built_song()

    assert song == built_song()
    assert len(parse_midi(song).notes) == 4956
    assert len(parse_midi(built_song(1)).notes) * 4 == 4956


def test_every_pinned_wheel_but_pyodide_s_own_is_at_uv_lock_s_version() -> None:
    with (ROOT / "uv.lock").open("rb") as file:
        locked = {package["name"]: package["version"] for package in tomllib.load(file)["package"]}
    pins = read_pins()

    assert {pin.name: pin.version for pin in pins.wheels} == {
        name: locked[name]
        for name in (
            "pydantic-core",
            "pydantic",
            "annotated-types",
            "typing-extensions",
            "typing-inspection",
            "mido",
            "packaging",
        )
    }
    assert [pin.name for pin in pins.packages] == ["numpy"]
    assert all(
        pin.url.startswith("https://") for pin in (pins.pyodide, *pins.packages, *pins.wheels)
    )
    assert all(len(pin.sha256) == 64 for pin in (pins.pyodide, *pins.packages, *pins.wheels))


def test_a_download_is_kept_only_when_its_sha256_is_the_one_pinned(tmp_path: Path) -> None:
    source = tmp_path / "wheel.whl"
    source.write_bytes(b"the wheel")
    good = Pin(
        name="wheel",
        version="1",
        url=source.as_uri(),
        sha256=hashlib.sha256(b"the wheel").hexdigest(),
    )
    bad = good.model_copy(update={"sha256": "0" * 64})

    assert fetched(good, tmp_path / "downloads").read_bytes() == b"the wheel"
    (tmp_path / "downloads" / "wheel.whl").unlink()
    with pytest.raises(HashMismatchError, match="where 0000"):
        fetched(bad, tmp_path / "downloads")
    assert list((tmp_path / "downloads").iterdir()) == []


def test_the_app_zip_holds_the_source_data_and_vocabulary_at_their_paths() -> None:
    data = app_zip()
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()

    assert data == app_zip()
    assert "src/human_o_matic/web/worker.py" in names
    assert "src/human_o_matic/service.py" in names
    assert "data/vocabulary.toml" in names
    assert "data/styles/tight.toml" in names
    assert "skills/human-o-matic/references/vocabulary.md" in names
    assert not [name for name in names if "__pycache__" in name or "/static/" in name]
    assert not [name for name in names if name.startswith(("private", "tests", "tools"))]
    assert not [name for name in names if name.endswith(".html")]
    source = [name for name in names if name.startswith("src/")]
    assert source == [name for name in source if name.endswith(".py")]


def test_the_app_zip_takes_only_python_from_the_source_tree(tmp_path: Path) -> None:
    # A page, a design file or any other file left beside the source never ships in the zip.
    package = tmp_path / "src" / "human_o_matic"
    for name in ("service.py", "web/worker.py", "web/example.html", "web/static/index.html"):
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        (package / name).write_text("", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "vocabulary.toml").write_text("", encoding="utf-8")

    names = zipfile.ZipFile(io.BytesIO(app_zip(tmp_path))).namelist()

    assert names == [
        "data/vocabulary.toml",
        "src/human_o_matic/service.py",
        "src/human_o_matic/web/worker.py",
    ]


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The site built without the network, from small stand-ins of the pinned downloads under
    their own names."""
    folder = tmp_path_factory.mktemp("build")
    (folder / "sources").mkdir()
    pins = read_pins()

    def stand_in[P: Pin](pin: P, data: bytes) -> P:
        path = folder / "sources" / pin.file_name
        path.write_bytes(data)
        sha256 = hashlib.sha256(data).hexdigest()
        return pin.model_copy(update={"url": path.as_uri(), "sha256": sha256})

    release = io.BytesIO()
    with tarfile.open(fileobj=release, mode="w:bz2") as archive:
        for name in pins.pyodide.files:
            entry = tarfile.TarInfo(f"pyodide/{name}")
            entry.size = len(name)
            archive.addfile(entry, io.BytesIO(name.encode()))
    stand_ins = Pins(
        pyodide=stand_in(pins.pyodide, release.getvalue()),
        packages=tuple(stand_in(pin, pin.name.encode()) for pin in pins.packages),
        wheels=tuple(stand_in(pin, pin.name.encode()) for pin in pins.wheels),
        tailwind=pins.tailwind,
    )
    return build(folder / "site", folder / "downloads", stand_ins)


def headers_for(text: str, path: str) -> list[tuple[str, str]]:
    """Every header a `_headers` file gives `path`, from each rule that matches it: its own path,
    or a folder's `/*`, which matches every path under it."""
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    for line in text.splitlines():
        if line.startswith("  "):
            name, value = line.strip().split(": ", 1)
            rules[-1][1].append((name, value))
        elif line:
            rules.append((line, []))
    return [
        header
        for rule, headers in rules
        if rule == path or (rule.endswith("/*") and path.startswith(rule[:-1]))
        for header in headers
    ]


EVERY_PATH = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; "
        "connect-src 'self'; style-src 'self' https://fonts.googleapis.com; img-src 'self'; "
        "font-src 'self' https://fonts.gstatic.com; form-action 'self'; base-uri 'none'; "
        "frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000",
}
"""The headers of the website plan's section 7 on every path, written out, not imported, so a
change to the build's shows here."""


def test_every_path_of_the_built_site_gets_the_csp_and_headers_and_its_type_and_caching(
    site: Path,
) -> None:
    text = (site / "_headers").read_text(encoding="utf-8")
    paths = ["/" + path.relative_to(site).as_posix() for path in site.rglob("*") if path.is_file()]

    assert "/pyodide/314.0.7/pyodide.asm.wasm" in paths
    for path in paths:
        found = headers_for(text, path)
        headers = dict(found)
        assert len(headers) == len(found), path
        assert headers.items() >= EVERY_PATH.items(), path
        wasm = headers.get("Content-Type") == "application/wasm"
        assert wasm == path.endswith(".wasm"), path
        immutable = headers.get("Cache-Control") == "public, max-age=31536000, immutable"
        assert immutable == path.startswith(("/pyodide/314.0.7/", "/wheels/")), path


URL = re.compile(rb"([a-z][a-z0-9+.-]*://[^/\s\"'();*]*)|[\"'(=]\s*(//\w)", re.IGNORECASE)
"""A URL's origin, with a scheme, or the start of one that starts `//`, which names another host."""
GOOGLE_FONTS = {b"https://fonts.googleapis.com", b"https://fonts.gstatic.com"}
"""The only other origins the page loads from (ADR 0126)."""


def origins(data: bytes) -> set[bytes]:
    return {found.group(1) or found.group(2) for found in URL.finditer(data)}


def test_the_page_s_own_files_name_only_google_fonts(site: Path) -> None:
    # Pyodide's files, the wheels and the app's zip may hold URLs of their own, which the CSP
    # keeps from being fetched (the website plan's section 12). Of the page's own, the page names
    # Google Fonts' stylesheet, the headers the two hosts the CSP allows, Tailwind's CSS its
    # project in the licence it keeps and the chevron its namespace, neither fetched, and
    # nothing else another origin.
    own = [
        path
        for path in site.rglob("*")
        if path.is_file()
        and path.relative_to(site).parts[0] not in ("pyodide", "wheels", "app.zip", SONG)
    ]
    named = {path.relative_to(site).as_posix(): origins(path.read_bytes()) for path in own}

    page = {path.relative_to(static_dir()).as_posix() for path in static_dir().rglob("*.*")}
    assert {"index.html", "tailwind.css", "check.html", "js/app.js", "js/round.js"} <= page
    assert page | {"_headers", "engine.json", "check-flow.json"} == set(named)
    assert named.pop("index.html") == {b"https://fonts.googleapis.com"}
    assert named.pop("_headers") == GOOGLE_FONTS
    assert named.pop("tailwind.css") == {b"https://tailwindcss.com"}
    # An SVG file names its namespace, which is never fetched.
    assert named.pop("chevron.svg") == {b"http://www.w3.org"}
    assert {path: found for path, found in named.items() if found} == {}


CLI = DOWNLOADS / read_pins().tailwind.file_name


@pytest.mark.skipif(
    not CLI.is_file(),
    reason="Tailwind's CLI isn't in build/site-downloads/: `uv run python tools/build_site.py css` "
    "downloads it, on macOS on Apple silicon",
)
def test_the_css_command_gives_the_committed_tailwind_css_byte_for_byte(tmp_path: Path) -> None:
    out = tmp_path / "tailwind.css"

    built_css(out)

    assert out.read_bytes() == (static_dir() / "tailwind.css").read_bytes()


def test_the_build_fails_on_a_file_of_10_mb_or_more(tmp_path: Path) -> None:
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "page.js").write_text("")
    with (tmp_path / "js" / "big.wasm").open("wb") as file:
        file.truncate(MAX_FILE_BYTES - 1)

    check_sizes(tmp_path)
    with (tmp_path / "js" / "big.wasm").open("wb") as file:
        file.truncate(MAX_FILE_BYTES)
    with pytest.raises(ValueError, match=r"js/big.wasm is 10,000,000 bytes, where a file must"):
        check_sizes(tmp_path)
