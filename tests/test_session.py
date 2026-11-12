"""Sessions: where they are kept, their JSON, the section edits, the answers and controls they
hold, and the file they render, rebuilt from the MIDI file each time."""

import json
import shutil
from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from grooves import BAR, CRASH, GM, TYPED, midi_file, rock
from human_o_matic.analyze.sections import find_sections
from human_o_matic.cli import RenderAnswers
from human_o_matic.controls import ControlVector
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import midi_bytes
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.session import (
    STATE_ENV,
    AnswersPatch,
    Merge,
    Move,
    Rename,
    SectionOp,
    Session,
    SessionError,
    SessionSection,
    SessionStore,
    Split,
    edit_sections,
    load_song,
    merge_answers,
    opened,
    read_song,
    render_session,
    sessions_dir,
    state_dir,
    with_controls,
    with_takes,
)

TYPED_ALL = RenderAnswers(hit_types=dict.fromkeys(("kick", "snare", "hat", "crash"), TYPED))


def song_file(path: Path, bars: int = 16) -> Path:
    """A rock groove with a crash every 4 bars."""
    file = path / "song.mid"
    file.write_bytes(midi_file([*rock(bars), *((bar * BAR, CRASH) for bar in range(0, bars, 4))]))
    return file


def open_in(store: SessionStore, file: Path) -> Session:
    """A session of the file, opened through General MIDI as `open_session` opens one."""
    data = file.read_bytes()
    loaded = read_song(data, GM, GM)
    found = find_sections(loaded.song, loaded.normalized.score)
    return store.create(lambda session_id: opened(session_id, file, data, loaded, found))


def sections(*spans: tuple[int, int]) -> tuple[SessionSection, ...]:
    return tuple(SessionSection(start=start, bars=bars, group="A") for start, bars in spans)


def test_the_state_directory_is_the_override_then_xdg_then_the_home_default() -> None:
    home = Path.home() / ".local" / "state" / "human-o-matic"

    assert state_dir({STATE_ENV: "/tmp/own", "XDG_STATE_HOME": "/xdg"}) == Path("/tmp/own")
    assert state_dir({"XDG_STATE_HOME": "/xdg"}) == Path("/xdg/human-o-matic")
    assert state_dir({"XDG_STATE_HOME": "relative"}) == home
    assert state_dir({STATE_ENV: "", "XDG_STATE_HOME": ""}) == home
    assert sessions_dir({"XDG_STATE_HOME": "/xdg"}) == Path("/xdg/human-o-matic/sessions")


def test_a_session_round_trips_through_its_file(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions")
    session = open_in(store, song_file(tmp_path))
    changed = with_controls(
        session.model_copy(update={"answers": TYPED_ALL, "seed": 42, "style": "loose"}),
        [0],
        ControlVector(energy=0.9, arc="build"),
        "full power",
    )

    store.save(changed)
    again = store.load(changed.id)

    assert again == changed
    assert Session.model_validate_json(changed.dump()) == changed
    assert store.path(changed.id).parent == tmp_path / "sessions"
    assert json.loads(store.path(changed.id).read_text())["answers"]["hit_types"]["snare"] == {
        "soft_below": 50,
        "accent_from": 110,
    }


def test_a_session_holds_no_notes(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session = open_in(store, song_file(tmp_path, bars=64))

    text = store.path(session.id).read_text()

    assert "velocity" not in text
    assert "pitch" not in text
    assert len(text) < 2000


@pytest.mark.parametrize("session_id", ["../escape", "ABCDEF123456", "abc", "0123456789abc"])
def test_an_id_of_the_wrong_form_names_no_file(tmp_path: Path, session_id: str) -> None:
    with pytest.raises(SessionError, match="not a session ID"):
        SessionStore(tmp_path).path(session_id)


def test_a_new_session_never_takes_a_taken_name_and_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SessionStore(tmp_path / "sessions")
    file = song_file(tmp_path)
    ids = iter(["0123456789ab", "0123456789ab", "ba9876543210"])
    monkeypatch.setattr("human_o_matic.session.secrets.token_hex", lambda _: next(ids))

    first = open_in(store, file)
    second = open_in(store, file)

    assert (first.id, second.id) == ("0123456789ab", "ba9876543210")
    assert sorted(path.name for path in store.directory.iterdir()) == [
        "0123456789ab.json",
        "ba9876543210.json",
    ]
    assert store.load(first.id) == first


def test_a_missing_or_broken_session_is_a_session_error(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    with pytest.raises(SessionError, match="there is no session 0123456789ab"):
        store.load("0123456789ab")
    store.path("0123456789ab").write_text("{}")
    with pytest.raises(SessionError, match="isn't a valid session"):
        store.load("0123456789ab")


def test_a_changed_file_is_refused_rather_than_rendered_differently(tmp_path: Path) -> None:
    file = song_file(tmp_path)
    session = open_in(SessionStore(tmp_path), file)
    file.write_bytes(midi_file(rock(16)))

    with pytest.raises(SessionError, match="has changed since"):
        load_song(session)
    file.unlink()
    with pytest.raises(SessionError, match="can't be read"):
        load_song(session)


def rendered_bytes(session: Session) -> bytes:
    return midi_bytes(render_session(session, load_song(session)).song)


def test_the_same_session_json_and_seed_give_the_same_bytes(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "one")
    session = open_in(store, song_file(tmp_path)).model_copy(
        update={"answers": TYPED_ALL, "seed": 9}
    )
    session = with_controls(session, None, ControlVector(energy=0.8, groove=0.7))
    store.save(session)
    copy = tmp_path / "two"
    copy.mkdir()
    shutil.copy(store.path(session.id), copy / f"{session.id}.json")

    first = rendered_bytes(store.load(session.id))
    again = rendered_bytes(SessionStore(copy).load(session.id))
    other = rendered_bytes(session.model_copy(update={"seed": 10}))

    assert first == again
    assert first != other


def test_another_take_of_one_section_leaves_the_others_notes_as_they_were(
    tmp_path: Path,
) -> None:
    session = open_in(SessionStore(tmp_path), song_file(tmp_path)).model_copy(
        update={"answers": TYPED_ALL}
    )
    session = session.model_copy(update={"sections": sections((0, 8), (8, 8))})
    loaded = load_song(session)

    before = render_session(session, loaded).notes
    after = render_session(with_takes(session, [8], 1), loaded).notes

    assert [note.note for note in before if note.section == 0] == [
        note.note for note in after if note.section == 0
    ]
    assert [note.note for note in before if note.section == 1] != [
        note.note for note in after if note.section == 1
    ]


def test_controls_merge_by_patch_for_the_song_or_the_sections_given(tmp_path: Path) -> None:
    session = open_in(SessionStore(tmp_path), song_file(tmp_path)).model_copy(
        update={"sections": sections((0, 8), (8, 8))}
    )
    session = with_controls(session, None, ControlVector(energy=0.4), "verse")
    session = with_controls(session, [8], ControlVector(energy=0.9, groove=0.2), "chorus")
    session = with_controls(session, [8], ControlVector.model_validate({"groove": None}))

    assert (session.controls, session.note) == (ControlVector(energy=0.4), "verse")
    assert session.section(0).controls == ControlVector()
    assert (session.section(8).controls, session.section(8).note) == (
        ControlVector(energy=0.9),
        "chorus",
    )
    with pytest.raises(SessionError, match="no section starts at bar 4; they start at 0, 8"):
        with_controls(session, [4], ControlVector(energy=0.1))


def test_answers_merge_by_key_and_null_removes_one() -> None:
    held = RenderAnswers(
        hit_types={"kick": HitTypeBounds(), "snare": TYPED}, grids={(3, 1): "32nd"}
    )
    patch = AnswersPatch.model_validate(
        {"hit_types": {"kick": None, "hat": {"soft_below": 40}}, "grids": {"4,0": "16th"}}
    )

    merged = merge_answers(held, patch)

    assert merged.hit_types == {"snare": TYPED, "hat": HitTypeBounds(soft_below=40)}
    assert merged.grids == {(3, 1): "32nd", (4, 0): "16th"}


EIGHT_AND_EIGHT = sections((0, 8), (8, 8))


@pytest.mark.parametrize(
    ("ops", "expected"),
    [
        ([Split(op="split", at=4)], [(0, 4), (4, 4), (8, 8)]),
        ([Split(op="split", at=12)], [(0, 8), (8, 4), (12, 4)]),
        ([Merge(op="merge", start=8)], [(0, 16)]),
        ([Move(op="move", start=8, to=6)], [(0, 6), (6, 10)]),
        ([Move(op="move", start=8, to=15)], [(0, 15), (15, 1)]),
        ([Split(op="split", at=4), Merge(op="merge", start=8)], [(0, 4), (4, 12)]),
    ],
)
def test_section_edits_split_merge_and_move_boundaries(
    ops: list[SectionOp], expected: list[tuple[int, int]]
) -> None:
    edited = edit_sections(EIGHT_AND_EIGHT, ops)

    assert [(section.start, section.bars) for section in edited] == expected


def test_a_split_keeps_the_section_s_controls_in_both_halves_and_a_merge_the_first_s() -> None:
    held = (
        SessionSection(start=0, bars=8, group="A", controls=ControlVector(energy=0.3), note="v"),
        SessionSection(start=8, bars=8, group="B", controls=ControlVector(energy=0.9), take=2),
    )

    split = edit_sections(held, [Split(op="split", at=12)])
    merged = edit_sections(held, [Merge(op="merge", start=8)])
    renamed = edit_sections(held, [Rename(op="rename", start=8, name="chorus", group="C")])

    assert [(s.controls, s.take, s.group) for s in split[1:]] == [
        (ControlVector(energy=0.9), 2, "B")
    ] * 2
    assert merged == (held[0].model_copy(update={"bars": 16}),)
    assert (renamed[1].name, renamed[1].group, renamed[1].controls) == (
        "chorus",
        "C",
        ControlVector(energy=0.9),
    )


@pytest.mark.parametrize(
    ("ops", "message"),
    [
        ([Split(op="split", at=8)], r"ops\[0\] \(split\): bar 8 already starts a section"),
        ([Split(op="split", at=16)], r"ops\[0\] \(split\): the drums have 16 bars, 0 to 15"),
        ([Merge(op="merge", start=0)], "bar 0 starts the song"),
        ([Merge(op="merge", start=4)], "no section starts at bar 4; they start at 0, 8"),
        ([Move(op="move", start=8, to=16)], "can move to bars 1 to 15"),
        ([Move(op="move", start=8, to=0)], "can move to bars 1 to 15"),
        (
            [Split(op="split", at=4), Merge(op="merge", start=6)],
            r"ops\[1\] \(merge\): no section starts at bar 6; they start at 0, 4, 8",
        ),
    ],
)
def test_an_edit_that_can_t_be_applied_says_which_and_why(
    ops: list[SectionOp], message: str
) -> None:
    with pytest.raises(SessionError, match=message):
        edit_sections(EIGHT_AND_EIGHT, ops)


@given(st.lists(st.integers(1, 63), min_size=1, max_size=12))
def test_edits_always_leave_sections_that_cover_the_song_in_order(cuts: list[int]) -> None:
    held = sections((0, 64))
    for cut in cuts:
        starts = [section.start for section in held]
        op: SectionOp = Merge(op="merge", start=cut) if cut in starts else Split(op="split", at=cut)
        held = edit_sections(held, [op])

        assert held[0].start == 0
        assert all(a.end == b.start for a, b in pairwise(held))
        assert held[-1].end == 64


def test_a_session_reads_the_file_through_its_kits_and_answers(tmp_path: Path) -> None:
    file = song_file(tmp_path)
    data = file.read_bytes()
    target = find_kit("sleep-token-ii/default")
    loaded = read_song(data, GM, target, answers=TYPED_ALL)
    found = find_sections(loaded.song, loaded.normalized.score)
    session = opened("0123456789ab", file, data, loaded, found, bpm=100.0)

    assert (session.from_map, session.to_map, session.bpm) == (
        "gm/default",
        "sleep-token-ii/default",
        100.0,
    )
    assert session.midi_path == str(file.resolve())
    assert session.sections_source == "drums"
    assert sum(section.bars for section in session.sections) == 16
