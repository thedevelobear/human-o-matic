"""Remapping a song's drums from one kit to another, and nothing else (ADR 0130).

Each note of the drum track is read with the source kit (`normalize.read.read_drums`) and placed
in the target kit by conversion's fallback order, through `maps.convert.place`, as a render
places it (ADR 0048): it takes the target binding's note, and its channel, or else the kit's,
or else its own. It keeps its tick, length, velocity, release velocity, track and order. In the
kit it was read with, a note keeps its pitch and channel too. Every other note and event stays
as read, and the song is meant to be read and written at its own resolution (`keep_ppq`), so
each tick stays the same number.

A velocity outside the target binding's range is kept, not moved into it, and counted for each
articulation. What the fallback order can't settle is asked as conversion asks it: notes the
source kit doesn't map are one `unmapped_notes` request, answered by `unmapped`, from a pitch to
an articulation of the source kit, as `normalize` takes it, and the rest are `conversion`
requests, answered by `substitutions`. Either may be `drop`. A remap reads no tempo, grid, hit
type or section, so it asks only these and which track holds the drums.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from pydantic import BaseModel, ConfigDict

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.convert import (
    DROP,
    Reason,
    Resolution,
    checked,
    collisions,
    conversion_request,
    place,
)
from human_o_matic.maps.kit import DrumKit
from human_o_matic.midi.io import MidiSong, Note
from human_o_matic.midi.tempo import time_signature_map
from human_o_matic.midi.tracks import choose_drum_track
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.normalize.read import read_drums
from human_o_matic.render.target import (
    Changed,
    ConversionReport,
    LowConfidenceNotes,
    controllers,
    written,
)


class RemapReport(BaseModel):
    """What a remap did, as counts and names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    track: int
    """The drum track, from 0."""
    notes: int
    """The drum track's notes."""
    written: int
    dropped: int
    """The notes an `unmapped` or `substitutions` answer left out."""
    waiting: int
    """The notes waiting for a request, which nothing is written for."""
    outside_range: dict[str, int]
    """Per target articulation, the notes whose kept velocity is outside its binding's range."""
    conversion: ConversionReport
    """The articulations written as another, the collisions and the `low` confidence names, as
    a render reports them (ADR 0075), at the notes' own ticks."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Remapped:
    """A song with its drums remapped, and what is asked about the notes it couldn't place."""

    song: MidiSong
    """The song with every placed note moved and every dropped note left out. A note waiting
    for a request is left as it was read."""
    report: RemapReport
    decisions: tuple[DecisionRequest, ...]

    @property
    def complete(self) -> bool:
        return not self.decisions


def remap(
    song: MidiSong,
    source: DrumKit,
    target: DrumKit,
    *,
    track: int | None = None,
    unmapped: Mapping[int, str] | None = None,
    substitutions: Mapping[str, str] | None = None,
) -> Remapped:
    """The song's drum track read with `source` and placed in `target`.

    Raises `DecisionRequired` when the drum track is unclear, `MidiFileError` when the song has
    no notes, `AnswerError` for an answer the drums don't fit, and `ValueError` for a
    substitution the target can't play.
    """
    drums = choose_drum_track(song, track).track
    signatures = time_signature_map(song)
    reading = read_drums(song, drums, source, signatures, unmapped=unmapped)
    picks = checked(substitutions or {}, target)
    stray = sorted(picks.keys() - {hit.articulation for hit in reading.hits})
    if stray:
        raise AnswerError(
            "substitutions", stray[0], f"{stray[0]}: the drums have no notes read as it"
        )
    same_kit = source.ref == target.ref
    resolutions: dict[str, Resolution] = {}
    moved: dict[int, Note] = {}
    left_out = set(reading.dropped)
    waiting: dict[tuple[Reason, str], list[Note]] = {}
    changed: dict[tuple[str, str], Changed] = {}
    outside: dict[str, int] = {}
    read_low: dict[str, int] = {}
    written_low: dict[str, int] = {}
    places: list[tuple[int, int, int]] = []
    origins: list[tuple[str, int, int]] = []
    for hit in reading.hits:
        key, note = hit.articulation, hit.note
        if _low(source, key):
            read_low[key] = read_low.get(key, 0) + 1
        if same_kit and key not in picks:
            name, pitch, channel = key, note.pitch, note.channel
        else:
            first = source.articulation(key.split("|")[0])
            controlled = "|" in key or controllers(first.bindings) is not None
            resolution = place(key, controlled, source, target, picks, resolutions)
            if resolution.target is not None and resolution.steps:
                row = changed.get((key, resolution.target))
                changed[key, resolution.target] = Changed(
                    source=key,
                    target=resolution.target,
                    notes=(row.notes if row else 0) + 1,
                    steps=resolution.steps,
                )
            if resolution.target is None:
                waiting.setdefault((resolution.reason or "family", key), []).append(note)
                continue
            if resolution.target == DROP:
                left_out.add(hit.index)
                continue
            at = written(resolution.target, target, note.channel)
            name, pitch, channel = at.articulation, at.pitch, at.channel
            low, high = at.velocity
            if not low <= note.velocity <= high:
                outside[name] = outside.get(name, 0) + 1
            moved[hit.index] = replace(note, pitch=pitch, channel=channel)
        if _low(target, name):
            written_low[name] = written_low.get(name, 0) + 1
        places.append((pitch, channel, note.start))
        origins.append((key, note.channel, note.pitch))

    decisions = (
        *reading.decisions,
        *(
            conversion_request(
                reason,
                key,
                held,
                resolutions.get(key, Resolution(None)),
                source,
                target,
                signatures,
            )
            for (reason, key), held in waiting.items()
        ),
    )
    on_drums = sum(note.track == drums for note in song.notes)
    report = RemapReport(
        track=drums,
        notes=on_drums,
        written=len(places),
        dropped=len(left_out),
        waiting=on_drums - len(places) - len(left_out),
        outside_range=outside,
        conversion=ConversionReport(
            changed=tuple(changed.values()),
            collisions=collisions(places, origins, signatures),
            low_confidence=LowConfidenceNotes(read=read_low, written=written_low),
        ),
    )
    return Remapped(
        song=replace(song, notes=_ended_first(song, drums, moved, left_out)),
        report=report,
        decisions=decisions,
    )


def _ended_first(
    song: MidiSong, track: int, moved: Mapping[int, Note], left_out: set[int]
) -> tuple[Note, ...]:
    """The song's notes, each moved one in its place and each left out gone. A note that ends on
    the tick where a note from another source pitch now starts on its pitch takes that note's
    order for its note-off, which the writer then puts first, so it doesn't end the other note
    (`midi/io.py`). Only that order changes, and notes that shared a pitch as read keep theirs."""
    notes = {
        index: moved.get(index, note)
        for index, note in enumerate(song.notes)
        if index not in left_out
    }
    starting: dict[tuple[int, int, int], list[int]] = {}
    for index, note in notes.items():
        if note.track == track:
            starting.setdefault((note.channel, note.pitch, note.start), []).append(index)
    for index, note in notes.items():
        was = song.notes[index]
        if note.track != track:
            continue
        for other in starting.get((note.channel, note.pitch, note.end), ()):
            source = song.notes[other]
            if (source.channel, source.pitch) != (was.channel, was.pitch):
                note = replace(note, off_order=min(note.off_order, notes[other].order))
        notes[index] = note
    return tuple(notes.values())


def _low(kit: DrumKit, key: str) -> bool:
    """Whether the kit names any of a key's articulations at `low` confidence."""
    return any(kit.articulation(name).confidence == "low" for name in key.split("|"))
