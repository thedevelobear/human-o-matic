"""`tools/make_ab.py`: the blind test's five variants of each section, their files, the shuffle,
the hidden key and the ratings sheet, and the count of the ratings (ADRs 0101 to 0106)."""

import csv
import json
import os
from collections import Counter
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from grooves import (
    ACCENT,
    BAR,
    CRASH,
    GM,
    HAT,
    PPQ,
    SIXTEENTH,
    SNARE,
    SOFT,
    TEMPOS,
    TYPED,
    Hit,
    control_vectors,
    grooves,
    midi_file,
    normalized,
    plan_for,
    rock,
    song,
)
from human_o_matic.analyze.sections import find_sections
from human_o_matic.cli import RenderAnswers
from human_o_matic.controls import ControlVector, SectionPlan, SessionPlan, StyleName
from human_o_matic.midi.io import META, MidiSong, Note, parse_midi
from human_o_matic.midi.tempo import META_TEMPO, META_TIME_SIGNATURE
from human_o_matic.render.engine import Rendered, render
from human_o_matic.render.style import STYLE_NAMES, built_in_styles
from human_o_matic.render.target import place_score
from human_o_matic.session import (
    STATE_ENV,
    Loaded,
    Session,
    SessionSection,
    SessionStore,
    file_hash,
    load_song,
    opened,
    read_song,
    render_session,
    sessions_dir,
    with_controls,
    with_takes,
)
from make_ab import (
    EXIT_OPEN,
    EXIT_USAGE,
    FLAT_VELOCITY,
    LETTERS,
    NAIVE_VELOCITY,
    NAMES,
    SHEET,
    TRIAL_FILE,
    VARIANTS,
    FileEntry,
    Key,
    TrialEntry,
    Variant,
    default_plan,
    key_path,
    main,
    make,
    performances,
    playable,
    render_variants,
    score,
    untimed,
    windows_of,
)
from midi_files import cc

SECTIONS = ((0, 4, "A"), (4, 4, "B"), (8, 4, "A"), (12, 4, "C"))
"""The song's sections: a groove, four empty bars, the groove again, and a last section at a
faster tempo."""
ANSWERS = RenderAnswers(hit_types=dict.fromkeys(("kick", "snare", "hat", "crash"), TYPED))
SEED = 3
FASTER = 140


def song_file(folder: Path) -> Path:
    """A rock groove with soft snare notes and a crash at each section's start, four bars of
    silence after the first section, a tempo change at bar 12, and a hat pedal controller."""
    hits = [*rock(4), *rock(4, start=8), *rock(4, start=12)]
    hits += [(bar * BAR + PPQ + 3 * SIXTEENTH, SNARE, SOFT) for bar in (0, 1, 2, 3, 8, 9, 12, 13)]
    hits += [(bar * BAR, CRASH, ACCENT) for bar in (0, 8, 12)]
    file = folder / "song.mid"
    file.write_bytes(
        midi_file(
            hits,
            tempos=[(12 * BAR, FASTER)],
            events=[(0, cc(4, 64)), (9 * BAR, cc(4, 100))],
        )
    )
    return file


def guided(folder: Path, store: SessionStore | None = None) -> Session:
    """A session of the song as the skill would leave it: the hit types confirmed, a style, a
    seed, a song-wide tightness, a section's controls, one section creative, and another take."""
    file = song_file(folder)
    data = file.read_bytes()
    loaded = read_song(data, GM, GM)
    found = find_sections(loaded.song, loaded.normalized.score)
    store = store or SessionStore(folder / "sessions")
    session = store.create(lambda session_id: opened(session_id, file, data, loaded, found))
    session = session.model_copy(
        update={
            "answers": ANSWERS,
            "style": "medium",
            "seed": 5,
            "controls": ControlVector(tightness=0.9),
            "sections": tuple(
                SessionSection(start=start, bars=bars, group=group)
                for start, bars, group in SECTIONS
            ),
        }
    )
    session = with_controls(session, [0], ControlVector(energy=0.9, feel=0.6, ghost_level=0.8))
    session = with_controls(session, [8], ControlVector(arc="build", creative=True))
    session = with_controls(session, [12], ControlVector(groove=0.2, dynamic_range=0.9))
    session = with_takes(session, [12], 1)
    store.save(session)
    return session


def session_file(session: Session, folder: Path) -> Path:
    return SessionStore(folder / "sessions").path(session.id)


def run(folder: Path, session: Session, *extra: str, seed: int = SEED, out: str = "ab") -> int:
    return main(
        [
            "make",
            str(session_file(session, folder)),
            "--kit",
            "gm",
            "--seed",
            str(seed),
            "--out",
            str(folder / out),
            *extra,
        ]
    )


def read_key(path: Path) -> Key:
    return Key.model_validate_json(path.read_bytes())


def files_of(key: Key, trial: int) -> dict[Variant, str]:
    return {entry.variant: entry.file for entry in key.files if entry.trial == trial}


def trial_of(key: Key, start: int) -> int:
    (found,) = (trial.trial for trial in key.trials if trial.start == start)
    return found


def in_file(rendered: Rendered, loaded: Loaded, session: Session) -> tuple[tuple[Note, ...], ...]:
    """A render's notes, section by section, at the ticks of their section's file: a bar after
    the bar line before the section, on one track."""
    windows = windows_of(loaded.normalized.score, default_plan(session))
    return tuple(
        tuple(
            replace(
                note.note,
                track=0,
                start=note.note.start - span.shift,
                end=note.note.end - span.shift,
            )
            for note in rendered.notes
            if note.section == number
        )
        for number, span in enumerate(windows)
    )


def meta_events(midi: MidiSong) -> list[tuple[int, int | None, bytes]]:
    return [
        (event.tick, event.meta_type, event.data) for event in midi.events if event.status == META
    ]


def test_the_same_session_and_seed_write_the_same_bytes(tmp_path: Path) -> None:
    session = guided(tmp_path)
    loaded = load_song(session)
    kept = session_file(session, tmp_path).read_bytes()

    assert run(tmp_path, session, out="first") == 0
    assert run(tmp_path, session, out="second") == 0

    assert session_file(session, tmp_path).read_bytes() == kept
    first, second = tmp_path / "first", tmp_path / "second"
    assert sorted(path.name for path in first.iterdir()) == sorted(
        path.name for path in second.iterdir()
    )
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes(), path.name
    assert key_path(first).read_bytes() == key_path(second).read_bytes()
    assert make(session, loaded, seed=SEED) == make(session, loaded, seed=SEED)


def test_every_section_with_notes_is_a_trial_of_five_files_the_key_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = guided(tmp_path)

    assert run(tmp_path, session) == 0

    key = read_key(tmp_path / "ab.key.json")
    out = tmp_path / "ab"
    assert sorted(trial.start for trial in key.trials) == [0, 8, 12]
    assert key.left_out == (4,)
    assert key.creative_off == (8,)
    assert [trial.trial for trial in key.trials] == [1, 2, 3]
    names = [entry.file for entry in key.files]
    assert names == sorted(names)
    assert sorted(path.name for path in out.iterdir()) == sorted([*names, SHEET])
    for trial in key.trials:
        entries = [entry for entry in key.files if entry.trial == trial.trial]
        assert sorted(entry.variant for entry in entries) == list(VARIANTS)
        assert [entry.file for entry in entries] == [
            f"trial-{trial.trial:02d}-{letter}.mid" for letter in LETTERS
        ]
    for entry in key.files:
        assert TRIAL_FILE.fullmatch(entry.file)
        assert file_hash((out / entry.file).read_bytes()) == entry.sha256
    assert (key.kit, key.style, key.session_seed, key.seed) == ("gm/default", "medium", 5, SEED)
    assert key.variants == {str(variant): NAMES[variant] for variant in VARIANTS}
    with (out / SHEET).open(newline="") as sheet:
        rows = list(csv.reader(sheet))
    assert rows == [["file", "rating", "comment"], *([name, "", ""] for name in names)]
    printed = json.loads(capsys.readouterr().out)
    assert set(printed) == {
        "out",
        "key",
        "sheet",
        "kit",
        "trials",
        "files",
        "left_out",
        "creative_off",
    }
    assert (printed["trials"], printed["files"]) == (3, 15)


def test_the_files_of_a_trial_play_the_same_notes_for_as_long_and_name_nothing(
    tmp_path: Path,
) -> None:
    session = guided(tmp_path)
    assert run(tmp_path, session) == 0
    key = read_key(tmp_path / "ab.key.json")

    for trial in key.trials:
        songs = [
            parse_midi((tmp_path / "ab" / name).read_bytes())
            for name in files_of(key, trial.trial).values()
        ]
        first = songs[0]
        for midi in songs:
            assert (midi.format, midi.track_count, midi.ppq) == (0, 1, PPQ)
            assert midi.track_ends == first.track_ends
            assert Counter((note.channel, note.pitch) for note in midi.notes) == Counter(
                (note.channel, note.pitch) for note in first.notes
            )
            assert meta_events(midi) == meta_events(first)
            assert {meta for _, meta, _ in meta_events(midi)} == {META_TEMPO, META_TIME_SIGNATURE}
            assert all(event.status == META or 0xA0 <= event.status < 0xF0 for event in midi.events)
            assert min(note.start for note in midi.notes) >= 0


def test_a_trial_holds_its_bars_after_one_before_them_with_the_song_s_tempo_and_controllers(
    tmp_path: Path,
) -> None:
    session = guided(tmp_path)
    assert run(tmp_path, session) == 0
    key = read_key(tmp_path / "ab.key.json")

    def quantized(start: int) -> MidiSong:
        return parse_midi((tmp_path / "ab" / files_of(key, trial_of(key, start))[1]).read_bytes())

    first, middle, last = quantized(0), quantized(8), quantized(12)
    tempo = round(60_000_000 / 120).to_bytes(3, "big")
    faster = round(60_000_000 / FASTER).to_bytes(3, "big")
    assert [(tick, data) for tick, meta, data in meta_events(last) if meta == META_TEMPO] == [
        (0, tempo),
        (BAR, faster),
    ]
    assert [(tick, data) for tick, meta, data in meta_events(first) if meta == META_TEMPO] == [
        (0, tempo)
    ]
    controllers = [(event.tick, event.data) for event in middle.events if event.status != META]
    assert controllers == [(0, bytes((4, 64))), (2 * BAR, bytes((4, 100)))]
    assert [(event.tick, event.data) for event in last.events if event.status != META] == [
        (0, bytes((4, 100)))
    ]
    for midi in (first, middle, last):
        assert min(note.start for note in midi.notes) == BAR
        assert midi.track_ends == (5 * BAR,)


def test_variant_1_is_every_note_on_its_grid_point_at_one_velocity(tmp_path: Path) -> None:
    session = guided(tmp_path)
    loaded = load_song(session)
    renders = render_variants(session, loaded)

    played = performances(session, loaded, renders, seed=SEED, velocity=80)

    assert all(note.note.start == note.tick for note in renders.quantized.notes)
    assert played[1] == tuple(
        tuple(replace(note, velocity=80) for note in section)
        for section in in_file(renders.quantized, loaded, session)
    )
    assert run(tmp_path, session) == 0
    key = read_key(tmp_path / "ab.key.json")
    for trial in key.trials:
        midi = parse_midi((tmp_path / "ab" / files_of(key, trial.trial)[1]).read_bytes())
        assert {note.velocity for note in midi.notes} == {FLAT_VELOCITY}


def test_variant_2_moves_each_note_by_a_spread_of_8_ms_and_its_velocity_by_at_most_12(
    tmp_path: Path,
) -> None:
    file = tmp_path / "hats.mid"
    file.write_bytes(midi_file([(step * SIXTEENTH, HAT) for step in range(16 * 64)]))
    data = file.read_bytes()
    hats = RenderAnswers(hit_types={"hat": TYPED})
    loaded = read_song(data, GM, GM, answers=hats)
    found = find_sections(loaded.song, loaded.normalized.score)
    session = opened("0123456789ab", file, data, loaded, found).model_copy(update={"answers": hats})
    loaded = load_song(session)
    renders = render_variants(session, loaded)

    played = performances(session, loaded, renders, seed=SEED, velocity=FLAT_VELOCITY)

    tempos = loaded.normalized.score.tempos
    offsets: list[float] = []
    for flat, naive in zip(played[1], played[2], strict=True):
        assert len(flat) == len(naive)
        for before, after in zip(flat, sorted(naive, key=lambda note: note.start), strict=True):
            offsets.append(tempos.tick_to_ms(after.start) - tempos.tick_to_ms(before.start))
            assert abs(after.velocity - FLAT_VELOCITY) <= NAIVE_VELOCITY
            assert after.end - after.start <= before.end - before.start
    count = len(offsets)
    mean = sum(offsets) / count
    spread = (sum((offset - mean) ** 2 for offset in offsets) / count) ** 0.5
    assert count == 16 * 64
    assert abs(mean) < 1.0
    assert 7.5 < spread < 8.5
    velocities = {note.velocity for section in played[2] for note in section}
    assert min(velocities) == FLAT_VELOCITY - NAIVE_VELOCITY
    assert max(velocities) == FLAT_VELOCITY + NAIVE_VELOCITY


@given(
    st.lists(
        st.tuples(st.integers(0, 40), st.integers(1, 30), st.sampled_from((36, 38))),
        min_size=1,
        max_size=40,
    )
)
def test_variant_2_s_notes_on_one_pitch_never_start_together_or_overlap(
    spans: list[tuple[int, int, int]],
) -> None:
    notes = [
        Note(track=0, channel=9, pitch=pitch, start=start, end=start + length, velocity=100)
        for start, length, pitch in spans
    ]

    out = playable(notes, 7)

    assert len(out) == len(notes)
    assert Counter(note.pitch for note in out) == Counter(note.pitch for note in notes)
    assert [note.order for note in out] == list(range(7, 7 + len(out)))
    assert all(note.order == note.off_order for note in out)
    assert [note.start for note in out] == sorted(note.start for note in out)
    for pitch in (36, 38):
        mine = [note for note in out if note.pitch == pitch]
        for before, after in pairwise(mine):
            assert before.start < after.start
            assert before.start < before.end <= after.start


def test_variant_3_is_the_engine_s_default_render_with_the_session_s_seed(tmp_path: Path) -> None:
    session = guided(tmp_path)
    loaded = load_song(session)
    renders = render_variants(session, loaded)
    played = performances(session, loaded, renders, seed=SEED, velocity=FLAT_VELOCITY)

    plan = SessionPlan(
        style="tight",
        seed=session.seed,
        sections=tuple(
            SectionPlan(start=start, bars=bars, group=group) for start, bars, group in SECTIONS
        ),
    )
    expected = render(loaded.song, loaded.normalized, loaded.placement, plan)

    assert played[3] == in_file(expected, loaded, session)
    assert played[3] != played[4]


def test_variant_4_is_the_session_s_render_with_creative_mode_off(tmp_path: Path) -> None:
    session = guided(tmp_path)
    loaded = load_song(session)
    renders = render_variants(session, loaded)
    played = performances(session, loaded, renders, seed=SEED, velocity=FLAT_VELOCITY)

    plain = with_controls(session, [8], ControlVector(creative=False))
    creative = render_session(session, loaded)

    assert played[4] == in_file(render_session(plain, loaded), loaded, session)
    assert len(in_file(creative, loaded, session)[2]) > len(played[4][2])
    assert played[4][0] == in_file(creative, loaded, session)[0]


def test_variant_5_is_on_the_grid_with_variant_4_s_velocities(tmp_path: Path) -> None:
    session = guided(tmp_path)
    loaded = load_song(session)
    renders = render_variants(session, loaded)

    timed = {note.position: note for note in renders.guided.notes}
    assert [note.position for note in renders.untimed.notes] == list(timed)
    for note in renders.untimed.notes:
        assert note.note.start == note.tick
        assert note.offset_ms == 0
        assert note.note.velocity == timed[note.position].note.velocity
    assert any(note.offset_ms != 0 for note in renders.guided.notes)
    played = performances(session, loaded, renders, seed=SEED, velocity=FLAT_VELOCITY)
    for ours, quantized in zip(played[5], played[1], strict=True):
        assert [note.start for note in ours] == [note.start for note in quantized]


@given(
    groove=grooves(),
    bpm=TEMPOS,
    cuts=st.lists(st.integers(1, 5), max_size=2),
    controls=st.lists(control_vectors(skip=False), min_size=3, max_size=3),
    style=st.sampled_from(STYLE_NAMES),
    seed=st.integers(0, 2**32),
)
def test_with_no_timing_every_note_is_on_its_grid_point_at_its_timed_velocity(
    groove: list[Hit],
    bpm: float,
    cuts: list[int],
    controls: list[ControlVector],
    style: StyleName,
    seed: int,
) -> None:
    midi = song(groove, bpm=bpm)
    result = normalized(midi)
    plan = plan_for(
        midi, result, cuts=cuts, sections=dict(enumerate(controls)), style=style, seed=seed
    )
    placement = place_score(result.score, GM, GM)

    timed = render(midi, result, placement, plan)
    quiet = render(midi, result, placement, plan, style=untimed(built_in_styles()[style]))

    for loud, still in zip(timed.notes, quiet.notes, strict=True):
        assert still.position == loud.position
        assert still.note.start == still.tick
        assert still.note.velocity == loud.note.velocity


def test_the_shuffle_moves_with_the_seed_and_the_names_and_output_say_nothing_of_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = guided(tmp_path)
    loaded = load_song(session)

    keys = [make(session, loaded, seed=seed).key for seed in range(8)]

    firsts = {next(entry.variant for entry in key.files) for key in keys}
    orders = {tuple(trial.start for trial in key.trials) for key in keys}
    assert len(firsts) >= 3
    assert len(orders) >= 2
    for key in keys:
        assert any(
            [entry.variant for entry in key.files if entry.trial == trial.trial] != list(VARIANTS)
            for trial in key.trials
        )
    assert run(tmp_path, session) == 0
    printed = capsys.readouterr().out
    assert "variant" not in printed
    written = sorted((tmp_path / "ab").iterdir())
    times = [path.stat().st_mtime_ns for path in written if path.name != SHEET]
    assert times == sorted(times)


def test_a_section_left_as_it_came_in_is_so_in_variants_4_and_5_and_the_key_says_so(
    tmp_path: Path,
) -> None:
    session = with_controls(guided(tmp_path), [12], ControlVector(skip=True))
    loaded = load_song(session)

    blind = make(session, loaded, seed=SEED)

    renders = render_variants(session, loaded)
    kept = [note for note in renders.untimed.notes if note.section == 3]
    assert kept
    assert all(note.kept for note in kept)
    assert [note.note for note in kept] == [
        note.note for note in renders.guided.notes if note.section == 3
    ]
    assert {trial.start: trial.skip for trial in blind.key.trials} == {0: False, 8: False, 12: True}


def test_make_writes_over_neither_the_input_nor_what_exists_without_overwrite(
    tmp_path: Path,
) -> None:
    session = guided(tmp_path)
    source = Path(session.midi_path)
    original = source.read_bytes()
    out, key = tmp_path / "ab", tmp_path / "ab.key.json"
    assert run(tmp_path, session) == 0
    before = {path.name: path.read_bytes() for path in out.iterdir()}
    held = key.read_bytes()

    assert run(tmp_path, session, seed=SEED + 1) == EXIT_USAGE
    assert run(tmp_path, session, "--key", str(tmp_path / "other.json"), seed=4) == EXIT_USAGE
    assert run(tmp_path, session, "--key", str(key), out="fresh") == EXIT_USAGE
    assert not (tmp_path / "fresh").exists()
    assert run(tmp_path, session, "--key", str(source), out="fresh") == EXIT_USAGE
    inside = str(tmp_path / "fresh" / "key.json")
    assert run(tmp_path, session, "--key", inside, out="fresh") == EXIT_USAGE
    assert run(tmp_path, session, "--overwrite", out=".") == EXIT_USAGE
    assert {path.name: path.read_bytes() for path in out.iterdir()} == before
    assert key.read_bytes() == held

    (out / "notes.txt").write_text("mine")
    (out / "trial-09-a.mid").write_bytes(b"old")
    assert run(tmp_path, session, "--overwrite", seed=SEED + 1) == 0

    replaced = read_key(key)
    assert replaced.seed == SEED + 1
    assert (out / "notes.txt").read_text() == "mine"
    assert not (out / "trial-09-a.mid").exists()
    assert sorted(path.name for path in out.iterdir()) == sorted(
        [*(entry.file for entry in replaced.files), SHEET, "notes.txt"]
    )
    for entry in replaced.files:
        assert file_hash((out / entry.file).read_bytes()) == entry.sha256
    assert source.read_bytes() == original
    assert not [path for path in tmp_path.iterdir() if path.name.startswith(".")]


def test_make_never_writes_the_session_s_file_even_with_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(STATE_ENV, str(tmp_path / "state"))
    session = guided(tmp_path, SessionStore(sessions_dir()))
    held = SessionStore(sessions_dir()).path(session.id)
    kept = held.read_bytes()
    link = tmp_path / "link.json"
    os.link(held, link)
    common = ["--kit", "gm", "--seed", "1", "--overwrite"]
    out = str(tmp_path / "ab")
    elsewhere = str(tmp_path / "key.json")

    for named in (session.id, str(held)):
        for outputs in (
            ["--out", out, "--key", str(held)],
            ["--out", out, "--key", str(link)],
            ["--out", str(held.parent)],
            ["--out", str(held.parent.parent), "--key", elsewhere],
        ):
            assert main(["make", named, *common, *outputs]) == EXIT_USAGE, (named, outputs)
            assert "the session's file, which make_ab never writes" in capsys.readouterr().err

    assert held.read_bytes() == kept
    assert sorted(path.name for path in held.parent.iterdir()) == [held.name]
    assert not (tmp_path / "ab").exists()
    assert main(["make", session.id, *common, "--out", out]) == 0
    assert held.read_bytes() == kept


@pytest.mark.parametrize("kit", ["nope", "gm/nope", "sleep-token-ii"])
def test_make_refuses_a_kit_that_isn_t_built_in(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kit: str
) -> None:
    session = guided(tmp_path)

    code = main(
        [
            "make",
            str(session_file(session, tmp_path)),
            "--kit",
            kit,
            "--seed",
            "1",
            "--out",
            str(tmp_path / "ab"),
        ]
    )

    assert code == EXIT_USAGE
    assert "--kit" in capsys.readouterr().err
    assert not (tmp_path / "ab").exists()
    assert not (tmp_path / "ab.key.json").exists()


def test_make_reads_a_session_by_its_id_from_the_state_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(STATE_ENV, str(tmp_path / "state"))
    session = guided(tmp_path, SessionStore(sessions_dir()))
    common = ["--kit", "gm", "--seed", "1", "--out"]

    assert main(["make", session.id, *common, str(tmp_path / "ab")]) == 0
    assert read_key(tmp_path / "ab.key.json").session == session.id
    assert main(["make", "0123456789ab", *common, str(tmp_path / "none")]) == EXIT_USAGE


def test_make_refuses_a_session_with_requests_open_or_a_changed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = guided(tmp_path)
    store = SessionStore(tmp_path / "sessions")
    store.save(session.model_copy(update={"answers": RenderAnswers()}))

    assert run(tmp_path, session) == EXIT_OPEN
    assert json.loads(capsys.readouterr().out.splitlines()[0])["decisions"][0]["kind"] == (
        "hit_types"
    )
    assert not (tmp_path / "ab").exists()

    store.save(session)
    Path(session.midi_path).write_bytes(midi_file(rock(16)))
    assert run(tmp_path, session) == EXIT_USAGE
    assert "has changed" in capsys.readouterr().err
    assert not (tmp_path / "ab").exists()


def hand_key() -> Key:
    """Two trials, each with its variants under letters in an order of its own."""
    letters: dict[int, tuple[Variant, ...]] = {1: (4, 2, 3, 5, 1), 2: (1, 5, 4, 3, 2)}
    return Key(
        session="0123456789ab",
        midi_path="/song.mid",
        midi_sha256="0" * 64,
        kit="gm/default",
        style="tight",
        session_seed=0,
        seed=1,
        velocity=FLAT_VELOCITY,
        variants={str(variant): NAMES[variant] for variant in VARIANTS},
        trials=(
            TrialEntry(trial=1, start=0, bars=4, group="A"),
            TrialEntry(trial=2, start=8, bars=4, group="B"),
        ),
        files=tuple(
            FileEntry(file=f"trial-0{trial}-{letter}.mid", trial=trial, variant=variant, sha256="0")
            for trial, variants in letters.items()
            for letter, variant in zip(LETTERS, variants, strict=True)
        ),
        questions=11,
    )


SHEETS = (
    {
        "trial-01-a.mid": 5,
        "trial-01-b.mid": 2,
        "trial-01-c.mid": 4,
        "trial-01-d.mid": 5,
        "trial-01-e.mid": 1,
        "trial-02-a.mid": 1,
        "trial-02-b.mid": 3,
        "trial-02-c.mid": 4,
        "trial-02-d.mid": 4,
        "trial-02-e.mid": 2,
    },
    {
        "trial-01-a.mid": 4,
        "trial-01-b.mid": 3,
        "trial-01-c.mid": 4,
        "trial-01-d.mid": 3,
        "trial-01-e.mid": 2,
        "trial-02-a.mid": 2,
        "trial-02-b.mid": 4,
        "trial-02-d.mid": 3,
        "trial-02-e.mid": 1,
    },
)
"""Two listeners' ratings of `hand_key`'s files, the second leaving one unrated."""


def test_score_counts_each_variant_and_the_gate_s_pairs_per_trial_and_overall() -> None:
    counted = score(hand_key(), SHEETS)

    assert counted["sheets"] == 2
    assert counted["questions"] == 11
    assert counted["variants"] == [
        {"variant": 1, "name": NAMES[1], "ratings": 4, "mean": 1.5},
        {"variant": 2, "name": NAMES[2], "ratings": 4, "mean": 2.0},
        {"variant": 3, "name": NAMES[3], "ratings": 4, "mean": 3.75},
        {"variant": 4, "name": NAMES[4], "ratings": 3, "mean": 4.333},
        {"variant": 5, "name": NAMES[5], "ratings": 4, "mean": 3.75},
    ]
    assert counted["comparisons"] == [
        {
            "pair": [4, 2],
            "trials": [
                {"trial": 1, "start": 0, "means": [4.5, 2.5], "higher": 4},
                {"trial": 2, "start": 8, "means": [4.0, 2.0], "higher": 4},
            ],
            "first_higher": 2,
            "second_higher": 0,
            "ties": 0,
            "mean_difference": 2.0,
        },
        {
            "pair": [4, 3],
            "trials": [
                {"trial": 1, "start": 0, "means": [4.5, 4.0], "higher": 4},
                {"trial": 2, "start": 8, "means": [4.0, 4.0], "higher": None},
            ],
            "first_higher": 1,
            "second_higher": 0,
            "ties": 1,
            "mean_difference": 0.25,
        },
        {
            "pair": [5, 4],
            "trials": [
                {"trial": 1, "start": 0, "means": [4.0, 4.5], "higher": 4},
                {"trial": 2, "start": 8, "means": [3.0, 4.0], "higher": 4},
            ],
            "first_higher": 0,
            "second_higher": 2,
            "ties": 0,
            "mean_difference": -0.75,
        },
    ]


def write_sheet(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", newline="") as file:
        csv.writer(file).writerows([["file", "rating", "comment"], *rows])
    return path


def test_score_reads_filled_sheets_and_refuses_what_the_key_doesn_t_take(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key = tmp_path / "ab.key.json"
    key.write_text(hand_key().model_dump_json(indent=2))
    sheets = [
        write_sheet(
            tmp_path / f"rater-{number}.csv",
            [[name, str(rating), "fine"] for name, rating in sheet.items()],
        )
        for number, sheet in enumerate(SHEETS)
    ]
    with sheets[1].open("a", newline="") as file:
        csv.writer(file).writerows([["trial-02-c.mid", "", "not heard"], []])

    assert main(["score", str(key), *map(str, sheets)]) == 0
    assert json.loads(capsys.readouterr().out) == score(hand_key(), SHEETS)

    for rows in (
        [["trial-03-a.mid", "3", ""]],
        [["trial-01-a.mid", "6", ""]],
        [["trial-01-a.mid", "4.5", ""]],
        [["trial-01-a.mid", "3", ""], ["trial-01-a.mid", "4", ""]],
    ):
        bad = write_sheet(tmp_path / "bad.csv", rows)
        assert main(["score", str(key), str(bad)]) == EXIT_USAGE
    (tmp_path / "bad.csv").write_text("name,stars\n")
    assert main(["score", str(key), str(tmp_path / "bad.csv")]) == EXIT_USAGE
    assert main(["score", str(tmp_path / "missing.json"), str(sheets[0])]) == EXIT_USAGE


def test_the_blank_sheet_make_writes_scores_as_nothing_rated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = guided(tmp_path)
    assert run(tmp_path, session, "--questions", "9") == 0
    capsys.readouterr()

    assert main(["score", str(tmp_path / "ab.key.json"), str(tmp_path / "ab" / SHEET)]) == 0

    counted = json.loads(capsys.readouterr().out)
    assert counted["questions"] == 9
    assert all(row["ratings"] == 0 and row["mean"] is None for row in counted["variants"])
    assert all(
        row["first_higher"] == row["second_higher"] == row["ties"] == 0
        for row in counted["comparisons"]
    )
