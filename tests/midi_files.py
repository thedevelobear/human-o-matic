"""MIDI files built in code for the tests. No test reads or commits library MIDI (ADR 0007)."""

from io import BytesIO
from pathlib import Path

import mido

type MidoMessage = mido.Message | mido.MetaMessage
type Timed = list[tuple[int, tuple[int, ...]]]


def on(pitch: int, velocity: int = 100, channel: int = 9) -> mido.Message:
    return mido.Message("note_on", note=pitch, velocity=velocity, channel=channel)


def off(pitch: int, channel: int = 9, velocity: int = 64) -> mido.Message:
    return mido.Message("note_off", note=pitch, velocity=velocity, channel=channel)


def cc(control: int, value: int, channel: int = 9) -> mido.Message:
    return mido.Message("control_change", control=control, value=value, channel=channel)


def tempo(bpm: float) -> mido.MetaMessage:
    return mido.MetaMessage("set_tempo", tempo=round(60_000_000 / bpm))


def signature(numerator: int, denominator: int) -> mido.MetaMessage:
    return mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator)


def name(text: str) -> mido.MetaMessage:
    return mido.MetaMessage("track_name", name=text)


def end() -> mido.MetaMessage:
    return mido.MetaMessage("end_of_track")


def track(*items: tuple[int, MidoMessage]) -> list[MidoMessage]:
    """A track from (absolute tick, message) pairs, in the order given."""
    now = 0
    messages: list[MidoMessage] = []
    for tick, message in items:
        assert tick >= now, "items must be in tick order"
        message.time = tick - now
        messages.append(message)
        now = tick
    return messages


def build(*tracks: list[MidoMessage], midi_format: int = 1, ppq: int = 480) -> bytes:
    midi = mido.MidiFile(type=midi_format, ticks_per_beat=ppq)
    midi.tracks.extend(mido.MidiTrack(messages) for messages in tracks)
    out = BytesIO()
    midi.save(file=out)
    return out.getvalue()


def save(path: Path, *tracks: list[MidoMessage], midi_format: int = 1, ppq: int = 480) -> Path:
    path.write_bytes(build(*tracks, midi_format=midi_format, ppq=ppq))
    return path


def messages(data: bytes) -> list[Timed]:
    """Each track's messages as (absolute tick, bytes), in file order, with the end of track."""
    tracks: list[Timed] = []
    for messages_in_track in mido.MidiFile(file=BytesIO(data)).tracks:
        tick = 0
        timed: Timed = []
        for message in messages_in_track:
            tick += message.time
            timed.append((tick, tuple(message.bytes())))
        tracks.append(timed)
    return tracks


def scaled(tracks: list[Timed], factor: int) -> list[Timed]:
    return [[(tick * factor, raw) for tick, raw in timed] for timed in tracks]


def header(data: bytes) -> tuple[int, int, int]:
    """The file's format, track count and PPQ."""
    midi = mido.MidiFile(file=BytesIO(data))
    return midi.type, len(midi.tracks), midi.ticks_per_beat
