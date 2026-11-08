from dataclasses import replace
from pathlib import Path

import mido
import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.midi.io import (
    MAX_PPQ,
    MIN_PPQ,
    Event,
    MidiFileError,
    MidiSong,
    Note,
    midi_bytes,
    parse_midi,
    read_midi,
    rescale,
    working_ppq,
    write_midi,
)
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
    save,
    scaled,
    signature,
    tempo,
    track,
)


def conductor() -> list[tuple[int, MidoMessage]]:
    return [
        (0, name("Song")),
        (0, mido.MetaMessage("copyright", text="(c) nobody")),
        (0, signature(4, 4)),
        (0, mido.MetaMessage("key_signature", key="Em")),
        (0, mido.MetaMessage("smpte_offset", frame_rate=25, hours=1)),
        (0, tempo(129)),
        (96, mido.MetaMessage("marker", text="Verse")),
        (192, tempo(140)),
        (192, signature(7, 8)),
        (200, mido.MetaMessage("sequencer_specific", data=[0, 33, 9])),
        (200, mido.UnknownMetaMessage(0x60, [1, 2, 3])),
        (300, mido.MetaMessage("cue_marker", text="Hit")),
        (400, end()),
    ]


def drums() -> list[tuple[int, MidoMessage]]:
    return [
        (0, name("Drums")),
        (0, mido.Message("program_change", program=0, channel=9)),
        # RPN 0, pitch bend range, then the null RPN.
        (0, cc(101, 0)),
        (0, cc(100, 0)),
        (0, cc(6, 2)),
        (0, cc(38, 0)),
        (0, cc(101, 127)),
        (0, cc(100, 127)),
        (0, mido.Message("sysex", data=[0x7E, 0x7F, 0x09, 0x01])),
        # Hi-hat openness before the note it shapes, at the same tick.
        (0, cc(4, 90)),
        (0, on(42)),
        (0, on(36, 120)),
        (12, off(42)),
        (12, off(36)),
        (24, on(38, 30)),
        (24, mido.Message("pitchwheel", pitch=-1000, channel=9)),
        # Two overlapping notes on one pitch.
        (48, on(36, 90)),
        (60, on(36, 91)),
        (70, off(36)),
        (80, off(36, velocity=10)),
        # A zero-length note, and a retrigger at the tick where the last note ends.
        (96, on(49)),
        (96, off(49)),
        (96, off(38)),
        (96, on(38, 110)),
        (100, mido.Message("polytouch", note=49, value=0, channel=9)),
        (100, mido.Message("aftertouch", value=50, channel=9)),
        (110, off(50)),  # a note-off with no note to end
        (120, off(38)),
        (192, end()),
    ]


def bass() -> list[tuple[int, MidoMessage]]:
    return [
        (0, mido.MetaMessage("channel_prefix", channel=1)),
        (0, name("Bass")),
        (0, mido.Message("program_change", program=33, channel=1)),
        (0, cc(7, 100, channel=1)),
        (0, on(40, 80, channel=1)),
        (48, mido.Message("pitchwheel", pitch=4000, channel=1)),
        (90, off(40, channel=1)),
        (96, on(43, 81, channel=1)),
        (190, off(43, channel=1)),
        (300, end()),
    ]


def merged(*tracks: list[tuple[int, MidoMessage]]) -> list[tuple[int, MidoMessage]]:
    """One format 0 track from several, keeping the order of messages at one tick."""
    items = [item for items in tracks for item in items if item[1].type != "end_of_track"]
    return [*sorted(items, key=lambda item: item[0]), (400, end())]


@pytest.mark.parametrize("midi_format", [0, 1])
def test_round_trip_keeps_every_message_in_order(tmp_path: Path, midi_format: int) -> None:
    tracks = (
        [track(*conductor()), track(*drums()), track(*bass())]
        if midi_format == 1
        else [track(*merged(conductor(), drums(), bass()))]
    )
    source = save(tmp_path / "in.mid", *tracks, midi_format=midi_format, ppq=96)

    song = read_midi(source)
    write_midi(song, tmp_path / "out.mid")
    written = (tmp_path / "out.mid").read_bytes()

    assert header(written) == (midi_format, len(tracks), 960)
    assert messages(written) == scaled(messages(source.read_bytes()), 10)
    assert replace(read_midi(tmp_path / "out.mid"), source_ppq=96) == song


def test_read_pairs_notes_and_keeps_the_rest_as_events() -> None:
    song = parse_midi(build(track(*conductor()), track(*drums()), track(*bass()), ppq=96))

    assert (song.format, song.ppq, song.source_ppq, song.track_ends) == (
        1,
        960,
        96,
        (4000, 1920, 3000),
    )
    drum_notes = [
        (n.pitch, n.start, n.end, n.velocity, n.release) for n in song.notes if n.track == 1
    ]
    assert drum_notes == [
        (42, 0, 120, 100, 64),
        (36, 0, 120, 120, 64),
        (38, 240, 960, 30, 64),
        (36, 480, 700, 90, 64),
        (36, 600, 800, 91, 10),
        (49, 960, 960, 100, 64),
        (38, 960, 1200, 110, 64),
    ]
    orphan = [e for e in song.events if e.track == 1 and e.status == 0x89]
    assert orphan == [Event(track=1, tick=1100, status=0x89, data=bytes((50, 64)), order=26)]
    unknown = [e for e in song.events if e.meta_type == 0x60]
    assert [(e.tick, e.data) for e in unknown] == [(2000, bytes((1, 2, 3)))]
    sysex = [e for e in song.events if e.status == 0xF0]
    assert [e.data for e in sysex] == [bytes((0x7E, 0x7F, 0x09, 0x01))]
    assert all(e.meta_type != 0x2F for e in song.events)


def test_note_on_at_velocity_zero_ends_a_note_and_is_written_as_note_off() -> None:
    data = build(track((0, on(36)), (100, on(36, velocity=0)), (200, end())), ppq=960)

    song = parse_midi(data)

    assert [(n.start, n.end, n.release) for n in song.notes] == [(0, 100, 64)]
    assert messages(midi_bytes(song))[0][1] == (100, (0x89, 36, 64))


def test_a_note_never_ended_ends_with_its_track() -> None:
    song = parse_midi(build(track((0, on(36)), (50, on(38)), (60, off(38)), (300, end())), ppq=960))

    assert [(n.pitch, n.start, n.end) for n in song.notes] == [(36, 0, 300), (38, 50, 60)]
    assert messages(midi_bytes(song))[0][-2:] == [(300, (0x89, 36, 64)), (300, (0xFF, 0x2F, 0))]


def test_write_puts_end_of_track_after_the_last_message() -> None:
    song = parse_midi(build(track((0, on(36)), (100, off(36)), (100, end())), ppq=960))
    moved = replace(song, notes=(replace(song.notes[0], end=500),))

    assert messages(midi_bytes(moved))[0][-1] == (500, (0xFF, 0x2F, 0))


@pytest.mark.parametrize(
    ("ppq", "expected"),
    [
        (96, 960),
        (120, 960),
        (192, 960),
        (480, 960),
        (960, 960),
        (384, 1152),
        (100, 1000),
        (7, 966),
        (1000, 1000),
        (MAX_PPQ, MAX_PPQ),
    ],
)
def test_working_ppq(ppq: int, expected: int) -> None:
    assert working_ppq(ppq) == expected


@given(st.integers(1, MAX_PPQ))
def test_working_ppq_is_the_smallest_whole_multiple_from_960(ppq: int) -> None:
    result = working_ppq(ppq)

    assert result % ppq == 0
    assert result >= MIN_PPQ
    assert result - ppq < MIN_PPQ or result == ppq
    assert result <= MAX_PPQ


def test_96_ppq_is_rescaled_by_exactly_ten() -> None:
    data = build(track((0, on(36)), (1, off(36)), (95, on(38)), (97, off(38)), (98, end())), ppq=96)

    song = parse_midi(data)

    assert song.ppq == 960
    assert [(n.start, n.end) for n in song.notes] == [(0, 10), (950, 970)]
    assert header(midi_bytes(song))[2] == 960


def test_384_ppq_is_rescaled_by_three_to_1152() -> None:
    song = parse_midi(build(track((0, on(36)), (1, off(36)), (5, end())), ppq=384))

    assert (song.ppq, song.notes[0].end, song.track_ends) == (1152, 3, (15,))


def test_rescale_refuses_a_resolution_that_is_not_a_whole_multiple() -> None:
    song = parse_midi(build(track((0, on(36)), (1, off(36))), ppq=960))

    with pytest.raises(ValueError, match="whole multiple"):
        rescale(song, 1000)
    with pytest.raises(ValueError, match="whole multiple"):
        rescale(song, 480)


def test_a_song_built_in_code_is_written_at_960_ppq_or_more() -> None:
    song = MidiSong(
        format=0,
        ppq=96,
        source_ppq=96,
        notes=(Note(track=0, channel=9, pitch=36, start=0, end=0, velocity=100),),
        events=(Event(track=0, tick=0, status=0xB9, data=bytes((4, 10))),),
        track_ends=(96,),
    )

    data = midi_bytes(song)

    # At one tick with the same order, a note-off comes first and a note-on last.
    assert header(data) == (0, 1, 960)
    assert messages(data) == [
        [(0, (0x89, 36, 64)), (0, (0xB9, 4, 10)), (0, (0x99, 36, 100)), (960, (0xFF, 0x2F, 0))]
    ]


def test_writing_twice_gives_the_same_bytes() -> None:
    song = parse_midi(build(track(*conductor()), track(*drums()), track(*bass()), ppq=96))

    assert midi_bytes(song) == midi_bytes(parse_midi(midi_bytes(song)))


def test_write_refuses_an_existing_file_unless_told_to_overwrite(tmp_path: Path) -> None:
    song = parse_midi(build(track((0, on(36)), (1, off(36)))))
    path = tmp_path / "out.mid"
    path.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        write_midi(song, path)
    assert path.read_bytes() == b"keep"
    write_midi(song, path, overwrite=True)
    assert read_midi(path).notes == song.notes


def test_rejects_data_that_is_not_midi() -> None:
    with pytest.raises(MidiFileError, match="not a readable MIDI file"):
        parse_midi(b"RIFF....WAVEfmt ")


def test_rejects_format_2() -> None:
    with pytest.raises(MidiFileError, match="format 2"):
        parse_midi(build(track((0, on(36)), (1, off(36))), midi_format=2))


def test_rejects_smpte_time_division() -> None:
    data = bytearray(build(track((0, on(36)), (1, off(36)))))
    data[12:14] = bytes((0xE7, 0x28))  # -25 frames per second, 40 ticks per frame

    with pytest.raises(MidiFileError, match="SMPTE"):
        parse_midi(bytes(data))


def test_notes_and_events_reject_impossible_values() -> None:
    with pytest.raises(ValueError, match="velocity"):
        Note(track=0, channel=0, pitch=36, start=0, end=1, velocity=0)
    with pytest.raises(ValueError, match="span"):
        Note(track=0, channel=0, pitch=36, start=5, end=1, velocity=1)
    with pytest.raises(ValueError, match="end of track"):
        Event(track=0, tick=0, status=0xFF, meta_type=0x2F)
    with pytest.raises(ValueError, match="track 1 does not exist"):
        MidiSong(
            format=0,
            ppq=960,
            source_ppq=960,
            notes=(Note(track=1, channel=0, pitch=36, start=0, end=1, velocity=1),),
            events=(),
            track_ends=(10,),
        )


# A random track: notes that each end after they start, among other messages, at ticks up to
# 2000. Messages at one tick keep the order they were drawn in.
_notes = st.lists(
    st.tuples(
        st.integers(0, 2000),
        st.integers(1, 300),
        st.integers(0, 15),
        st.integers(0, 127),
        st.integers(1, 127),
        st.integers(0, 127),
    ),
    max_size=20,
)
_data = st.integers(0, 127)
_others = st.lists(
    st.tuples(
        st.integers(0, 2000),
        st.one_of(
            st.builds(lambda c, v, ch: cc(c, v, ch), _data, _data, st.integers(0, 15)),
            st.builds(
                lambda p, ch: mido.Message("pitchwheel", pitch=p, channel=ch),
                st.integers(-8192, 8191),
                st.integers(0, 15),
            ),
            st.builds(lambda p: mido.Message("program_change", program=p), _data),
            st.builds(lambda n, v: mido.Message("polytouch", note=n, value=v), _data, _data),
            st.builds(lambda d: mido.Message("sysex", data=d), st.lists(_data, max_size=8)),
            st.builds(lambda t: mido.MetaMessage("marker", text=t), st.text("abc xyz", max_size=5)),
            st.builds(tempo, st.floats(20, 400)),
        ),
    ),
    max_size=20,
)


@st.composite
def _track(draw: st.DrawFn) -> list[MidoMessage]:
    items: list[tuple[int, MidoMessage]] = []
    for start, length, channel, pitch, velocity, release in draw(_notes):
        items.append((start, on(pitch, velocity, channel)))
        items.append((start + length, off(pitch, channel, release)))
    items.extend(draw(_others))
    items = draw(st.permutations(items))
    items.sort(key=lambda item: item[0])
    last = items[-1][0] if items else 0
    return track(*items, (last + draw(st.integers(0, 50)), end()))


@given(
    tracks=st.lists(_track(), min_size=1, max_size=3),
    ppq=st.integers(1, 2000),
    single=st.booleans(),
)
def test_round_trip_property(tracks: list[list[MidoMessage]], ppq: int, single: bool) -> None:
    midi_format = 0 if single else 1
    source = build(*(tracks[:1] if single else tracks), midi_format=midi_format, ppq=ppq)

    song = parse_midi(source)
    written = midi_bytes(song)

    assert header(written)[2] == working_ppq(ppq)
    assert messages(written) == scaled(messages(source), working_ppq(ppq) // ppq)
    assert replace(parse_midi(written), source_ppq=ppq) == song
