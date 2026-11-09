"""Track summaries, and the choice of the track that holds the drums.

The drums are not found by channel 10 alone, since many libraries and DAWs use other channels.
The choice takes, in turn: the track the caller names; the only track with notes; the only track
named like drums; the only track with notes on channel 10. Anything else is a decision request
that lists the tracks.
"""

from dataclasses import dataclass
from typing import Literal

from human_o_matic.decisions import DecisionOption, DecisionRequest, DecisionRequired
from human_o_matic.midi.io import MidiFileError, MidiSong

META_TRACK_NAME = 0x03
DRUM_CHANNEL = 9
"""Channel 10, counted from 0, which General MIDI gives to drums."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TrackSummary:
    index: int
    name: str
    """The track's first name event, or "" when it has none."""
    channels: tuple[int, ...]
    """The channels its notes use, 0 to 15, in order."""
    note_count: int


type DrumTrackReason = Literal["argument", "only_track", "name", "channel"]


@dataclass(frozen=True, slots=True, kw_only=True)
class DrumTrackChoice:
    track: int
    reason: DrumTrackReason
    """Why this track: named by the caller, the only one with notes, named like drums, or the
    only one using channel 10."""


def track_name(song: MidiSong, track: int) -> str:
    """The text of the track's first name event, or "" when it has none."""
    for event in song.events:
        if event.track == track and event.meta_type == META_TRACK_NAME:
            return _decode_text(event.data)
    return ""


def summarize_tracks(song: MidiSong) -> tuple[TrackSummary, ...]:
    channels: list[set[int]] = [set() for _ in range(song.track_count)]
    counts = [0] * song.track_count
    for note in song.notes:
        channels[note.track].add(note.channel)
        counts[note.track] += 1
    return tuple(
        TrackSummary(
            index=index,
            name=track_name(song, index),
            channels=tuple(sorted(channels[index])),
            note_count=counts[index],
        )
        for index in range(song.track_count)
    )


def choose_drum_track(song: MidiSong, track: int | None = None) -> DrumTrackChoice:
    """The track that holds the drums.

    Raises `DecisionRequired` when no rule settles it, or when `track` names a track with no
    notes, and `MidiFileError` when the song has no notes at all.
    """
    with_notes = [summary for summary in summarize_tracks(song) if summary.note_count]
    if not with_notes:
        raise MidiFileError("the file has no notes")
    if track is not None:
        if any(summary.index == track for summary in with_notes):
            return DrumTrackChoice(track=track, reason="argument")
        raise DecisionRequired(
            _which_track(with_notes, f"Track {track} has no notes. Which track holds the drums?")
        )
    if len(with_notes) == 1:
        return DrumTrackChoice(track=with_notes[0].index, reason="only_track")
    named = [summary for summary in with_notes if "drum" in summary.name.casefold()]
    if len(named) == 1:
        return DrumTrackChoice(track=named[0].index, reason="name")
    on_drum_channel = [summary for summary in with_notes if DRUM_CHANNEL in summary.channels]
    if len(on_drum_channel) == 1:
        return DrumTrackChoice(track=on_drum_channel[0].index, reason="channel")
    raise DecisionRequired(
        _which_track(
            with_notes,
            f"{len(with_notes)} tracks have notes, and no single one is named like drums or "
            "uses channel 10. Which track holds the drums?",
        )
    )


def _which_track(tracks: list[TrackSummary], message: str) -> DecisionRequest:
    return DecisionRequest(
        kind="drum_track",
        message=message,
        answer_with=("track",),
        options=tuple(
            DecisionOption(
                value=summary.index,
                label=_label(summary),
                details={
                    "name": summary.name,
                    "channels": list(summary.channels),
                    "note_count": summary.note_count,
                },
            )
            for summary in tracks
        ),
    )


def _label(summary: TrackSummary) -> str:
    """For example `Track 1 "Bass": 412 notes on channel 3`, with channels counted from 1."""
    name = f' "{summary.name}"' if summary.name else ""
    channels = [str(channel + 1) for channel in summary.channels]
    on = f"channel {channels[0]}" if len(channels) == 1 else f"channels {', '.join(channels)}"
    return f"Track {summary.index}{name}: {summary.note_count} notes on {on}"


def _decode_text(data: bytes) -> str:
    """MIDI text has no declared encoding. Most files now use UTF-8, and older ones Latin-1."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text.strip("\x00 \t\r\n")
