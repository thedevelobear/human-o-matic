from pathlib import Path

import pytest

from human_o_matic.maps.convert import DROP, MAX_POSITIONS
from human_o_matic.maps.kit import DrumKit
from human_o_matic.midi.io import MidiSong, Note
from human_o_matic.midi.tempo import TimeSignatureMap
from human_o_matic.normalize.read import Hit, LowConfidence, read_drums
from map_files import articulation, load_kit

PPQ = 960
FOUR_FOUR = TimeSignatureMap(PPQ, [])
SELECT = {"mode": "select", "controller": 4}


@pytest.fixture
def kit(tmp_path: Path) -> DrumKit:
    return load_kit(
        tmp_path,
        articulation("kick.hit", 36),
        articulation("snare.center", 38),
        articulation("snare.rimshot", 40, confidence="low", source="inferred"),
        articulation("hat.closed", 42, cc=SELECT | {"values": [0, 63]}),
        articulation("hat.open", 42, cc=SELECT | {"values": [64, 127]}),
        articulation("tom.1.hit", 48),
        articulation("tom.2.hit", 45, confidence="low", source="inferred"),
    )


def note(pitch: int, start: int = 0, track: int = 0, channel: int = 9) -> Note:
    return Note(
        track=track, channel=channel, pitch=pitch, start=start, end=start + 10, velocity=100
    )


def song(*notes: Note) -> MidiSong:
    ordered = sorted(notes, key=lambda n: (n.start, n.track))
    return MidiSong(
        format=1, ppq=PPQ, source_ppq=PPQ, notes=tuple(ordered), events=(), track_ends=(0, 0)
    )


def test_each_note_of_the_track_is_read_as_its_articulation(kit: DrumKit) -> None:
    drums = song(note(36), note(38, PPQ), note(48, 2 * PPQ), note(60, PPQ, track=1))

    reading = read_drums(drums, 0, kit, FOUR_FOUR)

    assert [(hit.articulation, hit.family, hit.piece) for hit in reading.hits] == [
        ("kick.hit", "kick", 1),
        ("snare.center", "snare", 1),
        ("tom.1.hit", "tom", 1),
    ]
    assert [hit.index for hit in reading.hits] == [0, 1, 3]
    assert all(hit.note == drums.notes[hit.index] for hit in reading.hits)
    assert reading.unmapped == ()
    assert reading.decisions == ()


def test_a_note_a_controller_decides_keeps_every_articulation(kit: DrumKit) -> None:
    reading = read_drums(song(note(42)), 0, kit, FOUR_FOUR)

    (hit,) = reading.hits
    assert hit == Hit(
        index=0,
        note=note(42),
        articulation="hat.closed|hat.open",
        family="hat",
        piece=1,
        confidence="high",
    )


def test_unmapped_notes_are_one_decision_request(kit: DrumKit) -> None:
    starts = [n * PPQ for n in range(MAX_POSITIONS + 2)]
    drums = song(*(note(99, start) for start in starts), note(36), note(77, 5 * PPQ, channel=3))

    reading = read_drums(drums, 0, kit, FOUR_FOUR)

    assert [hit.articulation for hit in reading.hits] == ["kick.hit"]
    assert len(reading.unmapped) == MAX_POSITIONS + 3
    (request,) = reading.decisions
    assert request.kind == "unmapped_notes"
    assert request.answer_with == ("unmapped", "from_map")
    assert request.details == {
        "kit": kit.ref,
        "notes": [
            {"pitch": 77, "channels": [3], "count": 1, "positions": [[1, 1.0]]},
            {
                "pitch": 99,
                "channels": [9],
                "count": MAX_POSITIONS + 2,
                "positions": [[n // 4, float(n % 4)] for n in range(MAX_POSITIONS)],
            },
        ],
    }
    assert request.message.startswith("11 notes on 2 pitches have no articulation in")
    assert "(note 77: 1 note from bar 2; note 99: 10 notes from bar 1)" in request.message


def test_an_answer_maps_or_drops_the_unmapped_notes(kit: DrumKit) -> None:
    drums = song(note(99), note(77, PPQ), note(36, 2 * PPQ))

    reading = read_drums(drums, 0, kit, FOUR_FOUR, unmapped={99: "tom.1.hit", 77: DROP})

    assert [(hit.index, hit.articulation) for hit in reading.hits] == [
        (0, "tom.1.hit"),
        (2, "kick.hit"),
    ]
    assert reading.dropped == (1,)
    assert reading.unmapped == ()
    assert reading.decisions == ()


def test_an_answer_the_kit_cant_play_is_an_error(kit: DrumKit) -> None:
    with pytest.raises(ValueError, match=r"has no crash\.1\.hit"):
        read_drums(song(note(99)), 0, kit, FOUR_FOUR, unmapped={99: "crash.1.hit"})


def test_low_confidence_articulations_are_counted(kit: DrumKit) -> None:
    drums = song(note(40), note(45, 10), note(40, PPQ), note(38, PPQ), note(45, 2 * PPQ))

    reading = read_drums(drums, 0, kit, FOUR_FOUR)

    assert reading.low_confidence == (
        LowConfidence(articulation="snare.rimshot", count=2),
        LowConfidence(articulation="tom.2.hit", count=2),
    )
    assert [hit.confidence for hit in reading.hits] == ["low", "low", "low", "high", "low"]
