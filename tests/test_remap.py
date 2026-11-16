"""The remap (ADR 0130): every drum note keeps its tick, length and velocity, and takes the
target kit's pitch and channel. Songs are built in code."""

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.decisions import DecisionRequired
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_maps, find_kit
from human_o_matic.midi.io import MidiSong, Note, midi_bytes, parse_midi
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.remap import Remapped, remap
from map_files import articulation, load_kit
from midi_files import (
    MidoMessage,
    build,
    cc,
    end,
    header,
    messages,
    name,
    off,
    on,
    signature,
    tempo,
    track,
)

KITS = tuple(built_in_maps())
REFS = [kit.ref for kit in KITS]

type Drawn = tuple[int, int, int, int, int]
"""A drum note as drawn: its start, length, pitch, velocity and release velocity."""


def song_bytes(
    drums: list[Drawn],
    *,
    ppq: int = 480,
    with_tempo: bool = True,
    bass: bool = True,
) -> bytes:
    """A song of a conductor track, a drum track with a controller, and a bass track."""
    conductor: list[tuple[int, MidoMessage]] = [(0, signature(4, 4))]
    if with_tempo:
        conductor.insert(0, (0, tempo(120)))
    timed: list[tuple[int, int, MidoMessage]] = [(0, 0, name("Drums")), (0, 0, cc(4, 90))]
    for start, length, pitch, velocity, release in drums:
        timed.append((start, 2, on(pitch, velocity)))
        # At a shared tick, note-offs come first, but a note's own after its note-on.
        timed.append((start + length, 1 if length else 3, off(pitch, velocity=release)))
    timed.sort(key=lambda item: (item[0], item[1]))
    tracks = [
        track(*conductor, (4 * ppq, end())),
        track(*((tick, message) for tick, _, message in timed)),
    ]
    if bass:
        tracks.append(
            track((0, name("Bass")), (0, on(40, 90, channel=0)), (ppq, off(40, channel=0)))
        )
    return build(*tracks, ppq=ppq)


def answered(song: MidiSong, source: DrumKit, target: DrumKit) -> Remapped:
    """The remap with every request answered: an unmapped pitch dropped, and a conversion by
    its first option, a substitute when it offers one, else `drop`."""
    unmapped: dict[int, str] = {}
    substitutions: dict[str, str] = {}
    for _ in range(3):
        result = remap(song, source, target, unmapped=unmapped, substitutions=substitutions)
        if result.complete:
            return result
        for request in result.decisions:
            groups = request.details.get("notes")
            if request.kind == "unmapped_notes" and isinstance(groups, list):
                for group in groups:
                    assert isinstance(group, dict)
                    assert isinstance(group["pitch"], int)
                    unmapped[group["pitch"]] = "drop"
            else:
                substitutions[str(request.details["source"])] = str(request.options[0].value)
    raise AssertionError("the requests weren't settled")


def by_order(song: MidiSong) -> dict[tuple[int, int], Note]:
    return {(note.track, note.order): note for note in song.notes}


@st.composite
def drawn_songs(draw: st.DrawFn) -> tuple[bytes, str, str]:
    source = draw(st.sampled_from(REFS))
    target = draw(st.sampled_from(REFS))
    pitches = sorted(
        {binding.note for a in find_kit(source).articulations for binding in a.bindings}
    )
    ppq = draw(st.sampled_from([96, 384, 480, 960]))
    notes = draw(
        st.lists(
            st.tuples(
                st.integers(0, 16 * ppq),
                st.integers(0, ppq),
                st.sampled_from(pitches),
                st.integers(1, 127),
                st.integers(0, 127),
            ),
            min_size=1,
            max_size=40,
        )
    )
    return song_bytes(notes, ppq=ppq, with_tempo=draw(st.booleans())), source, target


@given(drawn_songs())
def test_a_remap_keeps_every_note_s_tick_length_velocity_and_track(
    drawn: tuple[bytes, str, str],
) -> None:
    data, source_ref, target_ref = drawn
    source, target = find_kit(source_ref), find_kit(target_ref)
    song = parse_midi(data, keep_ppq=True)

    result = answered(song, source, target)
    again = answered(song, source, target)
    out = result.song
    before, after = by_order(song), by_order(out)

    assert again.song == out
    assert midi_bytes(again.song, keep_ppq=True) == midi_bytes(out, keep_ppq=True)
    assert (out.ppq, out.source_ppq, out.format) == (song.ppq, song.source_ppq, song.format)
    assert out.events == song.events
    assert out.track_ends == song.track_ends
    missing = before.keys() - after.keys()
    assert after.keys() <= before.keys()
    assert all(key[0] == result.report.track for key in missing)
    assert len(missing) == result.report.dropped
    assert result.report.written + result.report.dropped == result.report.notes
    for key, note in after.items():
        was = before[key]
        assert (note.start, note.end, note.velocity, note.release) == (
            was.start,
            was.end,
            was.velocity,
            was.release,
        )
        if key[0] != result.report.track:
            assert note == was
        elif source.ref != target.ref:
            assert target.read(note.pitch, note.velocity, note.channel)
    written = parse_midi(midi_bytes(out, keep_ppq=True), keep_ppq=True)
    assert header(midi_bytes(out, keep_ppq=True))[2] == song.ppq
    assert [(e.track, e.tick, e.status, e.data) for e in written.events] == [
        (e.track, e.tick, e.status, e.data) for e in song.events
    ]
    assert sorted((n.track, n.channel, n.pitch, n.start, n.velocity) for n in written.notes) == (
        sorted((n.track, n.channel, n.pitch, n.start, n.velocity) for n in out.notes)
    )


def test_a_remap_from_a_kit_to_itself_gives_back_every_note() -> None:
    song = parse_midi(song_bytes([(0, 10, 36, 100, 64), (480, 10, 38, 90, 0)]), keep_ppq=True)
    kit = find_kit("gm")

    result = remap(song, kit, kit)

    assert result.complete
    assert result.song == song
    assert parse_midi(midi_bytes(result.song, keep_ppq=True), keep_ppq=True) == song


def test_a_note_takes_the_target_s_pitch_and_keeps_its_tick_length_and_velocity_at_96_ppq() -> None:
    song = parse_midi(song_bytes([(5, 3, 42, 77, 12)], ppq=96), keep_ppq=True)

    result = remap(song, find_kit("gm"), find_kit("ezdrummer-3"))
    (note,) = [note for note in result.song.notes if note.track == 1]

    assert (note.pitch, note.start, note.end, note.velocity, note.release) == (61, 5, 8, 77, 12)
    assert note.channel == 9
    assert result.song.ppq == 96


def test_a_note_the_source_doesn_t_map_is_asked_about_and_answered_with_a_source_name() -> None:
    song = parse_midi(song_bytes([(0, 10, 36, 100, 64), (480, 10, 99, 90, 64)]), keep_ppq=True)
    source, target = find_kit("gm"), find_kit("ezdrummer-3")

    asked = remap(song, source, target)
    placed = remap(song, source, target, unmapped={99: "snare.center"})
    left = remap(song, source, target, unmapped={99: "drop"})

    assert [request.kind for request in asked.decisions] == ["unmapped_notes"]
    assert asked.report.waiting == 1
    assert placed.complete
    assert [n.pitch for n in placed.song.notes if n.track == 1] == [36, 38]
    assert left.complete
    assert left.report.dropped == 1
    with pytest.raises(AnswerError, match="note 98"):
        remap(song, source, target, unmapped={98: "snare.center"})


def test_a_family_the_target_lacks_is_a_conversion_request_until_it_is_answered() -> None:
    song = parse_midi(song_bytes([(0, 10, 56, 100, 64)]), keep_ppq=True)
    source, target = find_kit("gm"), find_kit("ezdrummer-3")

    asked = remap(song, source, target)
    dropped = remap(song, source, target, substitutions={"cowbell.hit": "drop"})

    (request,) = asked.decisions
    assert request.kind == "conversion"
    assert request.details["source"] == "cowbell.hit"
    assert [n.pitch for n in asked.song.notes if n.track == 1] == [56]
    assert dropped.complete
    assert not [n for n in dropped.song.notes if n.track == 1]
    with pytest.raises(AnswerError, match=r"snare\.flam"):
        remap(song, source, target, substitutions={"snare.flam": "drop"})
    with pytest.raises(ValueError, match="has no"):
        remap(song, source, target, substitutions={"cowbell.hit": "cowbell.hit"})


def test_a_velocity_outside_the_target_s_range_is_kept_and_counted(tmp_path: Path) -> None:
    song = parse_midi(song_bytes([(0, 10, 38, 120, 64), (480, 10, 38, 40, 64)]), keep_ppq=True)
    target = load_kit(
        tmp_path,
        articulation("kick.hit", 36),
        articulation("snare.center", 40, velocity=[1, 99]),
    )

    result = remap(song, find_kit("gm"), target)

    assert [n.velocity for n in result.song.notes if n.track == 1] == [120, 40]
    assert result.report.outside_range == {"snare.center": 1}


def test_a_file_with_no_tempo_is_remapped_without_asking_for_one() -> None:
    song = parse_midi(song_bytes([(0, 10, 36, 100, 64)], with_tempo=False), keep_ppq=True)

    result = remap(song, find_kit("gm"), find_kit("ssd5"))

    assert result.complete


def test_an_unclear_drum_track_is_asked_about() -> None:
    data = build(
        track((0, on(36, channel=0)), (10, off(36, channel=0))),
        track((0, on(38, channel=1)), (10, off(38, channel=1))),
    )

    with pytest.raises(DecisionRequired) as asked:
        remap(parse_midi(data, keep_ppq=True), find_kit("gm"), find_kit("gm"))

    assert asked.value.request.kind == "drum_track"
    assert remap(parse_midi(data, keep_ppq=True), find_kit("gm"), find_kit("gm"), track=1).complete


def test_notes_brought_onto_one_pitch_end_before_the_next_starts(tmp_path: Path) -> None:
    # Two of GM's toms, 43 then 45, meet on the one tom of a kit built here: the first note's
    # note-off comes after the second's note-on in the file, so it is ordered first.
    data = build(
        track((0, name("Drums")), (0, on(43)), (240, on(45)), (240, off(43)), (480, off(45)))
    )
    song = parse_midi(data, keep_ppq=True)
    target = load_kit(tmp_path, articulation("kick.hit", 36), articulation("tom.1.hit", 47))

    result = remap(song, find_kit("gm"), target)
    written = midi_bytes(result.song, keep_ppq=True)
    at_240 = [raw[0] & 0xF0 for tick, raw in messages(written)[0] if tick == 240]

    assert [(n.pitch, n.start, n.end) for n in result.song.notes] == [(47, 0, 240), (47, 240, 480)]
    assert at_240 == [0x80, 0x90]
    assert [(n.pitch, n.start, n.end) for n in parse_midi(written, keep_ppq=True).notes] == [
        (47, 0, 240),
        (47, 240, 480),
    ]
