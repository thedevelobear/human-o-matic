"""The site's build without the network, and the fixed hash: the calls of `tests/web/flow.json`
on the check song, built in code, download the file whose SHA-256 the flow holds, as they must
under Pyodide in Node (ADR 0100)."""

import hashlib
import io
import json
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest

from build_site import (
    FLOW,
    ROOT,
    HashMismatchError,
    Pin,
    app_zip,
    built_song,
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


def test_the_check_page_has_no_inline_script_or_style_and_names_no_other_origin() -> None:
    files = [path for path in static_dir().rglob("*") if path.is_file()]
    page = (static_dir() / "check.html").read_text(encoding="utf-8")

    assert '<script type="module" src="js/check.js"></script>' in page
    assert "<style" not in page
    assert "style=" not in page
    assert page.count("<script") == 1
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "http://" not in text, path
        assert "https://" not in text, path
        for storage in ("localStorage", "sessionStorage", "indexedDB", "caches."):
            assert storage not in text, (path, storage)
