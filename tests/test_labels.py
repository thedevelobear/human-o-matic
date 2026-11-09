"""Label files and the measurement on them (ADR 0034), with songs and labels built in code in
`tmp_path`."""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from human_o_matic.analyze.labels import Label, LabelError, measure, read_label, read_labels
from human_o_matic.analyze.scoring import BoundaryScore
from human_o_matic.midi.io import MidiSong, midi_bytes
from human_o_matic.midi.tempo import MAX_BPM, MIN_BPM
from test_sections import HALF, PPQ, ROCK, song

META_TEMPO = 0x51
LABEL = """
midi = "songs/song.mid"
from_map = "gm"
bpm = 132
track = 0
starts = [0, 8, 16]
tuned = true
"""


def label_file(folder: Path, text: str, name: str = "song.toml") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def song_file(path: Path, midi: MidiSong, *, keep_tempo: bool = True) -> Path:
    if not keep_tempo:
        midi = replace(midi, events=tuple(e for e in midi.events if e.meta_type != META_TEMPO))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(midi_bytes(midi))
    return path


def test_a_label_file_is_read() -> None:
    label = Label.model_validate(
        {"midi": "songs/song.mid", "from_map": "gm", "bpm": 132, "starts": [0, 8, 16]}
    )

    assert label.bpm == 132.0
    assert label.track is None
    assert label.starts == (0, 8, 16)
    assert not label.tuned


@pytest.mark.parametrize(("written", "bpm"), [("3.577", MIN_BPM), ("60_000_000", MAX_BPM)])
def test_a_label_takes_any_bpm_a_midi_tempo_event_can_hold(
    tmp_path: Path, written: str, bpm: float
) -> None:
    path = label_file(tmp_path, LABEL.replace("bpm = 132", f"bpm = {written}"))

    assert read_label(path).bpm == bpm == float(written.replace("_", ""))


def test_a_label_file_is_read_from_toml(tmp_path: Path) -> None:
    label = read_label(label_file(tmp_path, LABEL))

    assert (label.midi, label.from_map, label.bpm, label.track) == ("songs/song.mid", "gm", 132, 0)
    assert label.starts == (0, 8, 16)
    assert label.tuned


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ('name = "verse"\n', "name: Extra inputs are not permitted"),
        ("starts = [8, 16]\n", "starts: Value error, the first section starts at bar 0"),
        ("starts = [0]\n", "starts: Value error, at least one section starts after bar 0"),
        ("starts = [0, 16, 8]\n", "bar 8 comes after bar 16, so starts isn't in order"),
        ("starts = [0, 8, 8]\n", "bar 8 comes after bar 8"),
        ("starts = [0, 8.0]\n", "starts.1: Input should be a valid integer"),
        ("bpm = 2\n", "bpm: Input should be greater than or equal to 3.577"),
        ("bpm = 60_000_001\n", "bpm: Input should be less than or equal to 60000000"),
        ('bpm = "132"\n', "bpm: Input should be a valid number"),
        ("bpm = true\n", "bpm: Input should be a valid number"),
        ("tuned = 1\n", "tuned: Input should be a valid boolean"),
        ("track = -1\n", "track: Input should be greater than or equal to 0"),
    ],
)
def test_a_label_file_that_breaks_the_rules_is_an_error(
    tmp_path: Path, change: str, problem: str
) -> None:
    key = change.split(" ", 1)[0]
    lines = [line for line in LABEL.splitlines() if not line.startswith(f"{key} ")]
    path = label_file(tmp_path, "\n".join(lines) + "\n" + change)

    with pytest.raises(LabelError, match=re.escape(str(path))) as raised:
        read_label(path)
    assert problem in str(raised.value)


def test_a_label_file_that_isnt_toml_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(LabelError, match=r"song\.toml"):
        read_label(label_file(tmp_path, "starts = [0,"))


def test_a_label_file_that_isnt_utf_8_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "song.toml"
    path.write_bytes(b'midi = "songs/\xff.mid"\n')

    with pytest.raises(LabelError, match=re.escape(str(path))) as raised:
        read_label(path)
    assert "utf-8" in str(raised.value)


def test_the_label_files_are_those_directly_in_the_folder_in_name_order(tmp_path: Path) -> None:
    label_file(tmp_path, LABEL, "b.toml")
    label_file(tmp_path, LABEL, "a.toml")
    label_file(tmp_path / "older", LABEL, "c.toml")
    (tmp_path / "notes.txt").write_text("not a label")

    assert [path.name for path, _ in read_labels(tmp_path)] == ["a.toml", "b.toml"]


def test_a_label_is_measured_with_its_answers_and_without_markers(tmp_path: Path) -> None:
    bar = 4 * PPQ
    marked = song((ROCK, 8), (HALF, 8), (ROCK, 8), markers=(4 * bar, 12 * bar))
    song_file(tmp_path / "songs" / "song.mid", marked, keep_tempo=False)
    path = label_file(tmp_path / "labels", LABEL.replace("[0, 8, 16]", "[0, 9, 20]"))

    result = measure(path, read_label(path), tmp_path)

    assert result.detected == (0, 8, 16)
    assert result.score == BoundaryScore(matches=1, detected=2, labelled=2)


def test_an_absolute_midi_path_is_used_as_it_is(tmp_path: Path) -> None:
    midi = song_file(tmp_path / "elsewhere" / "song.mid", song((ROCK, 8), (HALF, 8)))
    text = LABEL.replace('"songs/song.mid"', f'"{midi.as_posix()}"').replace("[0, 8, 16]", "[0, 8]")
    path = label_file(tmp_path / "labels", text)

    result = measure(path, read_label(path), tmp_path / "private")

    assert result.score == BoundaryScore(matches=1, detected=1, labelled=1)


@pytest.mark.parametrize(
    ("key", "value", "problem"),
    [
        ("from_map", '"nothing"', "from_map: no library 'nothing'"),
        ("midi", '"songs/missing.mid"', "midi: "),
        # The song has no tempo of its own, so leaving `bpm` out leaves the tempo unclear.
        ("bpm", None, "tempo: "),
        ("starts", "[0, 8, 16]", "starts: bar 16 isn't in the song, which has 16 bars"),
    ],
)
def test_a_label_that_doesnt_fit_its_song_is_an_error(
    tmp_path: Path, key: str, value: str | None, problem: str
) -> None:
    song_file(tmp_path / "songs" / "song.mid", song((ROCK, 8), (HALF, 8)), keep_tempo=False)
    lines = [line for line in LABEL.splitlines() if not line.startswith(f"{key} ")]
    if value is not None:
        lines.append(f"{key} = {value}")
    path = label_file(tmp_path / "labels", "\n".join(lines) + "\n")

    with pytest.raises(LabelError, match=re.escape(str(path))) as raised:
        measure(path, read_label(path), tmp_path)
    assert problem in str(raised.value)
