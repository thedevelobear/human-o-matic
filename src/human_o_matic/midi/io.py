"""Lossless reading and writing of Standard MIDI Files, formats 0 and 1.

A read keeps every message of every track at its absolute tick: note-ons and note-offs become
paired `Note`s, and everything else (controllers including RPNs, pitch bend, program changes,
aftertouch, sysex and meta events) is kept as an `Event` with its raw bytes. A write puts them
back in the order they were read, so a read followed by a write keeps every note and every other
event at the same position, once converted to the output resolution.

What a round trip does not keep, because MIDI gives it no meaning:
- the byte form of a note-off: a note-on at velocity 0 is written as a note-off at velocity 64,
  which the MIDI specification defines as the same thing, and running status is chosen anew;
- a note that never ends is ended at the end of its track;
- an `F7` escape sequence is written as an ordinary sysex message.

Only this module imports mido, through the local stubs in `typings/mido`.
"""

from collections import deque
from dataclasses import dataclass, replace
from io import BytesIO
from os import PathLike
from pathlib import Path

import mido

MIN_PPQ = 960
"""The lowest resolution worked on and written, in ticks per quarter note. At 96 PPQ and 129 BPM
one tick is 4.8 ms, too coarse for performed timing."""
MAX_PPQ = 0x7FFF
"""The highest resolution a Standard MIDI File header can hold."""

NOTE_OFF = 0x80
NOTE_ON = 0x90
SYSEX = 0xF0
META = 0xFF
META_END_OF_TRACK = 0x2F
DEFAULT_RELEASE = 64
"""The note-off velocity for a note-off that gives none, as the MIDI specification defines it."""


class MidiFileError(ValueError):
    """The data is not a MIDI file this app can read."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Note:
    """One note, from its note-on to its note-off.

    `order` and `off_order` are the positions of the note-on and note-off messages in their
    source track. The writer orders messages at the same tick by them, which is what keeps the
    source order through a round trip, so a step that changes a note keeps them as they are. A
    step that moves a note-off onto the tick of a later note-on of the same pitch must give the
    note-off the lower order, or it would end the new note.
    """

    track: int
    channel: int
    """0 to 15. Channel 10 on an instrument is 9 here."""
    pitch: int
    start: int
    """Absolute tick of the note-on."""
    end: int
    """Absolute tick of the note-off, never before `start`."""
    velocity: int
    """Note-on velocity, 1 to 127."""
    release: int = DEFAULT_RELEASE
    """Note-off velocity, 0 to 127."""
    order: int = 0
    off_order: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.channel <= 15:
            raise ValueError(f"channel {self.channel} is outside 0 to 15")
        if not 0 <= self.pitch <= 127:
            raise ValueError(f"pitch {self.pitch} is outside 0 to 127")
        if not 1 <= self.velocity <= 127:
            raise ValueError(f"velocity {self.velocity} is outside 1 to 127")
        if not 0 <= self.release <= 127:
            raise ValueError(f"release velocity {self.release} is outside 0 to 127")
        if not 0 <= self.start <= self.end:
            raise ValueError(f"note from tick {self.start} to {self.end} is not a valid span")


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """A message other than a paired note, kept as it was read.

    `status` is the message's first byte: 0x80 to 0xEF for a channel message, 0xF0 for sysex,
    0xF1 to 0xF6 for system common, and 0xFF for a meta event, whose type is `meta_type`. `data`
    is what follows it: the data bytes of a channel message, the payload of sysex without its
    F0 and F7, or the payload of a meta event without its type and length. End of track is not
    an event: the writer adds it.
    """

    track: int
    tick: int
    status: int
    data: bytes = b""
    meta_type: int | None = None
    order: int = 0

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError(f"event at negative tick {self.tick}")
        if not NOTE_OFF <= self.status <= META:
            raise ValueError(f"status byte {self.status:#04x} is not a message")
        if (self.status == META) != (self.meta_type is not None):
            raise ValueError("a meta event, and only a meta event, has a meta type")
        if self.meta_type == META_END_OF_TRACK:
            raise ValueError("end of track is written by the writer, not kept as an event")

    @property
    def channel(self) -> int | None:
        """The channel, 0 to 15, of a channel message, and None for anything else."""
        return self.status & 0x0F if self.status < SYSEX else None


@dataclass(frozen=True, slots=True, kw_only=True)
class MidiSong:
    """The whole content of a MIDI file, with absolute ticks.

    `notes` are sorted by start, track and order, and `events` by tick, track and order.
    """

    format: int
    """0 (one track) or 1 (several tracks, played together)."""
    ppq: int
    """Ticks per quarter note of every tick in the song."""
    source_ppq: int
    """Ticks per quarter note of the file the song was read from."""
    notes: tuple[Note, ...]
    events: tuple[Event, ...]
    track_ends: tuple[int, ...]
    """Absolute tick of each track's end of track. Its length is the number of tracks."""

    def __post_init__(self) -> None:
        if self.format not in (0, 1):
            raise ValueError(f"format {self.format} is not supported, only 0 and 1")
        if not 1 <= self.ppq <= MAX_PPQ:
            raise ValueError(f"resolution {self.ppq} PPQ is outside 1 to {MAX_PPQ}")
        if self.format == 0 and len(self.track_ends) != 1:
            raise ValueError("a format 0 song has exactly one track")
        tracks = len(self.track_ends)
        for item in (*self.notes, *self.events):
            if not 0 <= item.track < tracks:
                raise ValueError(f"track {item.track} does not exist in a song of {tracks}")

    @property
    def track_count(self) -> int:
        return len(self.track_ends)


def working_ppq(ppq: int) -> int:
    """The resolution a song at `ppq` is worked on and written at.

    It is the smallest multiple of `ppq` that is at least `MIN_PPQ`, so every tick scales by a
    whole number and none is rounded. 96 becomes 960 and 480 becomes 960, while 384 becomes
    1152 and 100 becomes 1000. A resolution of `MIN_PPQ` or more is kept as it is.
    """
    if ppq <= 0:
        raise ValueError(f"resolution {ppq} PPQ is not positive")
    return ppq * -(-MIN_PPQ // ppq)


def rescale(song: MidiSong, ppq: int) -> MidiSong:
    """The song at resolution `ppq`, which must be a whole multiple of the song's own."""
    if ppq < song.ppq or ppq % song.ppq:
        raise ValueError(f"{ppq} PPQ is not a whole multiple of {song.ppq} PPQ")
    factor = ppq // song.ppq
    if factor == 1:
        return song
    return replace(
        song,
        ppq=ppq,
        notes=tuple(
            replace(note, start=note.start * factor, end=note.end * factor) for note in song.notes
        ),
        events=tuple(replace(event, tick=event.tick * factor) for event in song.events),
        track_ends=tuple(end * factor for end in song.track_ends),
    )


def read_midi(path: str | PathLike[str]) -> MidiSong:
    """Read a MIDI file, at its `working_ppq`."""
    return parse_midi(Path(path).read_bytes())


def parse_midi(data: bytes) -> MidiSong:
    """Parse the bytes of a MIDI file, at its `working_ppq`."""
    try:
        midi = mido.MidiFile(file=BytesIO(data))
    except (OSError, EOFError, ValueError, KeyError, IndexError, mido.KeySignatureError) as error:
        # An error with no message, such as the EOFError of a truncated file, gives its type.
        reason = str(error) or type(error).__name__
        raise MidiFileError(f"not a readable MIDI file: {reason}") from error
    if midi.type not in (0, 1):
        raise MidiFileError(f"format {midi.type} MIDI files are not supported, only 0 and 1")
    if midi.ticks_per_beat <= 0:
        raise MidiFileError("SMPTE time division is not supported, only ticks per quarter note")

    notes: list[Note] = []
    events: list[Event] = []
    ends = tuple(
        _read_track(index, track, notes, events) for index, track in enumerate(midi.tracks)
    )
    notes.sort(key=lambda note: (note.start, note.track, note.order))
    events.sort(key=lambda event: (event.tick, event.track, event.order))
    song = MidiSong(
        format=midi.type,
        ppq=midi.ticks_per_beat,
        source_ppq=midi.ticks_per_beat,
        notes=tuple(notes),
        events=tuple(events),
        track_ends=ends,
    )
    return rescale(song, working_ppq(song.ppq))


def _read_track(index: int, track: mido.MidiTrack, notes: list[Note], events: list[Event]) -> int:
    """Add a track's notes and events to the lists, and return the tick where it ends."""
    tick = 0
    # Note-ons waiting for their note-off, per channel and pitch. The first one waiting is the
    # one a note-off ends, so overlapping notes on one pitch end in the order they started.
    pending: dict[tuple[int, int], deque[tuple[int, int, int]]] = {}
    for order, message in enumerate(track):
        tick += message.time
        raw = message.bytes()
        status = raw[0]
        if message.is_meta:
            if raw[1] != META_END_OF_TRACK:
                events.append(
                    Event(
                        track=index,
                        tick=tick,
                        status=META,
                        meta_type=raw[1],
                        data=bytes(_meta_payload(raw)),
                        order=order,
                    )
                )
            continue
        kind = status & 0xF0
        if kind in (NOTE_ON, NOTE_OFF):
            channel, pitch, velocity = status & 0x0F, raw[1], raw[2]
            waiting = pending.setdefault((channel, pitch), deque())
            if kind == NOTE_ON and velocity > 0:
                waiting.append((tick, velocity, order))
                continue
            if waiting:
                start, on_velocity, on_order = waiting.popleft()
                notes.append(
                    Note(
                        track=index,
                        channel=channel,
                        pitch=pitch,
                        start=start,
                        end=tick,
                        velocity=on_velocity,
                        release=velocity if kind == NOTE_OFF else DEFAULT_RELEASE,
                        order=on_order,
                        off_order=order,
                    )
                )
                continue
            # A note-off with no note to end is kept as it is, below.
        data = raw[1:-1] if status == SYSEX else raw[1:]
        events.append(Event(track=index, tick=tick, status=status, data=bytes(data), order=order))
    for (channel, pitch), waiting in pending.items():
        notes.extend(
            Note(
                track=index,
                channel=channel,
                pitch=pitch,
                start=start,
                end=tick,
                velocity=velocity,
                order=on_order,
                off_order=len(track),
            )
            for start, velocity, on_order in waiting
        )
    return tick


def _meta_payload(raw: list[int]) -> list[int]:
    """The payload of a meta message's bytes: FF, type, a variable-length length, payload."""
    position = 2
    while raw[position] & 0x80:
        position += 1
    return raw[position + 1 :]


# Among messages at one tick with the same order, which only songs built in code have, note-offs
# come first and note-ons last.
_OFF_RANK, _EVENT_RANK, _ON_RANK = 0, 1, 2


def midi_bytes(song: MidiSong) -> bytes:
    """The song as the bytes of a MIDI file, at its `working_ppq`."""
    song = rescale(song, working_ppq(song.ppq))
    timed: list[list[tuple[int, int, int, int, Event | bytes]]] = [[] for _ in song.track_ends]
    for note in song.notes:
        on = bytes((NOTE_ON | note.channel, note.pitch, note.velocity))
        off = bytes((NOTE_OFF | note.channel, note.pitch, note.release))
        items = timed[note.track]
        items.append((note.start, note.order, _ON_RANK, len(items), on))
        items.append((note.end, note.off_order, _OFF_RANK, len(items), off))
    for event in song.events:
        items = timed[event.track]
        items.append((event.tick, event.order, _EVENT_RANK, len(items), event))

    midi = mido.MidiFile(type=song.format, ticks_per_beat=song.ppq)
    for items, end in zip(timed, song.track_ends, strict=True):
        items.sort(key=lambda item: item[:4])
        track = mido.MidiTrack()
        now = 0
        for tick, _, _, _, item in items:
            track.append(_message(item, tick - now))
            now = tick
        track.append(mido.MetaMessage("end_of_track", time=max(end - now, 0)))
        midi.tracks.append(track)
    out = BytesIO()
    midi.save(file=out)
    return out.getvalue()


def write_midi(song: MidiSong, path: str | PathLike[str], *, overwrite: bool = False) -> None:
    """Write the song as a MIDI file, at its `working_ppq`. An existing file is an error unless
    `overwrite` is set."""
    data = midi_bytes(song)
    with Path(path).open("wb" if overwrite else "xb") as file:
        file.write(data)


def _message(item: Event | bytes, delta: int) -> mido.Message | mido.MetaMessage:
    if isinstance(item, bytes):
        return mido.Message.from_bytes(item, time=delta)
    if item.meta_type is not None:
        # An unknown meta message writes its type and payload exactly as given.
        return mido.UnknownMetaMessage(item.meta_type, item.data, time=delta)
    if item.status == SYSEX:
        return mido.Message.from_bytes((SYSEX, *item.data, 0xF7), time=delta)
    return mido.Message.from_bytes((item.status, *item.data), time=delta)
