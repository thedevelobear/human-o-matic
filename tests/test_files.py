"""Writing a file whole, aside first, then naming it, with or without hard links."""

import os
from pathlib import Path

import pytest

from human_o_matic.files import name_new, write_aside


@pytest.fixture(params=["links", "no links"])
def links(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Each test runs with hard links, and on a file system without them, where linking fails
    as it does on FAT or exFAT."""
    if request.param == "no links":

        def refuse(*_: object) -> None:
            raise PermissionError(1, "Operation not permitted")

        monkeypatch.setattr(os, "link", refuse)
    return str(request.param)


def test_a_file_written_aside_is_hidden_and_whole(tmp_path: Path) -> None:
    aside = write_aside(tmp_path, b"whole", prefix=".x.")

    assert aside.parent == tmp_path
    assert aside.name.startswith(".x.")
    assert aside.suffix == ".tmp"
    assert aside.read_bytes() == b"whole"


@pytest.mark.usefixtures("links")
def test_a_new_name_takes_the_bytes_and_refuses_a_taken_name(tmp_path: Path) -> None:
    aside = write_aside(tmp_path, b"new")
    taken = tmp_path / "taken.mid"
    taken.write_bytes(b"theirs")

    name_new(aside, tmp_path / "song.mid")
    with pytest.raises(FileExistsError):
        name_new(aside, taken)

    assert (tmp_path / "song.mid").read_bytes() == b"new"
    assert taken.read_bytes() == b"theirs"
    assert aside.read_bytes() == b"new"
