import json

import pytest

from human_o_matic.decisions import DecisionRequired
from human_o_matic.midi.io import MidiFileError, parse_midi
from human_o_matic.midi.tracks import (
    DrumTrackChoice,
    TrackSummary,
    choose_drum_track,
    summarize_tracks,
)
from midi_files import MidoMessage, build, name, off, on, tempo, track


def notes(channel: int, pitch: int = 36, count: int = 2) -> list[tuple[int, MidoMessage]]:
    items: list[tuple[int, MidoMessage]] = []
    for index in range(count):
        items.extend(
            [(index * 10, on(pitch, channel=channel)), (index * 10 + 5, off(pitch, channel))]
        )
    return items


def test_the_only_track_with_notes() -> None:
    song = parse_midi(build(track((0, tempo(120))), track((0, name("Kit")), *notes(channel=0))))

    assert choose_drum_track(song) == DrumTrackChoice(track=1, reason="only_track")


def test_a_format_0_file_on_any_channel() -> None:
    song = parse_midi(build(track(*notes(channel=15)), midi_format=0))

    assert choose_drum_track(song) == DrumTrackChoice(track=0, reason="only_track")


@pytest.mark.parametrize("label", ["Drums", "DRUM KIT", "Big Drums", "superior drummer 3"])
def test_the_only_track_named_like_drums(label: str) -> None:
    song = parse_midi(
        build(
            track((0, name("Bass")), *notes(channel=1, pitch=40)),
            track((0, name(label)), *notes(channel=2)),
            track((0, name("Keys")), *notes(channel=9, pitch=60)),
        )
    )

    assert choose_drum_track(song) == DrumTrackChoice(track=1, reason="name")


def test_the_only_track_on_channel_10() -> None:
    song = parse_midi(
        build(
            track((0, name("Bass")), *notes(channel=1, pitch=40)),
            track((0, name("Part 2")), *notes(channel=9)),
        )
    )

    assert choose_drum_track(song) == DrumTrackChoice(track=1, reason="channel")


def test_two_drum_names_fall_through_to_channel_10() -> None:
    song = parse_midi(
        build(
            track((0, name("Drums L")), *notes(channel=0)),
            track((0, name("Drums R")), *notes(channel=9)),
        )
    )

    assert choose_drum_track(song) == DrumTrackChoice(track=1, reason="channel")


def test_an_ambiguous_file_lists_its_tracks() -> None:
    song = parse_midi(
        build(
            track((0, tempo(120))),
            track((0, name("Bass")), *notes(channel=1, pitch=40, count=3)),
            track((0, name("Part 2")), *notes(channel=9)),
            track(*notes(channel=4), *[(30 + t, m) for t, m in notes(channel=9)]),
        )
    )

    with pytest.raises(DecisionRequired) as raised:
        choose_drum_track(song)

    request = raised.value.request
    assert request.kind == "drum_track"
    assert request.answer_with == ("track",)
    assert [option.value for option in request.options] == [1, 2, 3]
    assert [option.label for option in request.options] == [
        'Track 1 "Bass": 3 notes on channel 2',
        'Track 2 "Part 2": 2 notes on channel 10',
        "Track 3: 4 notes on channels 5, 10",
    ]
    assert request.options[2].details == {"name": "", "channels": [4, 9], "note_count": 4}
    assert json.loads(request.model_dump_json())["options"][0]["value"] == 1


def test_a_track_argument_overrides_the_rules() -> None:
    song = parse_midi(
        build(
            track((0, name("Drums")), *notes(channel=9)),
            track((0, name("Other")), *notes(channel=0)),
        )
    )

    assert choose_drum_track(song, track=1) == DrumTrackChoice(track=1, reason="argument")


def test_a_track_argument_without_notes_is_a_decision_request() -> None:
    song = parse_midi(build(track((0, tempo(120))), track(*notes(channel=9))))

    with pytest.raises(DecisionRequired, match="Track 0 has no notes") as raised:
        choose_drum_track(song, track=0)
    assert [option.value for option in raised.value.request.options] == [1]


def test_a_file_without_notes_is_an_error() -> None:
    song = parse_midi(build(track((0, tempo(120)))))

    with pytest.raises(MidiFileError, match="no notes"):
        choose_drum_track(song)


def test_track_summaries() -> None:
    song = parse_midi(
        build(
            track((0, name("Tempo")), (0, tempo(120))),
            track((0, name("Drüms")), *notes(channel=9), *[(20 + t, m) for t, m in notes(2)]),
        )
    )

    assert summarize_tracks(song) == (
        TrackSummary(index=0, name="Tempo", channels=(), note_count=0),
        TrackSummary(index=1, name="Drüms", channels=(2, 9), note_count=4),
    )
