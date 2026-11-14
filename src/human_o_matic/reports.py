"""What the command line and the tools read and report, with no command line of their own: the
answers to the decision requests, and the summaries of a song and of a render, as JSON models.

`session` keeps a session's answers as `RenderAnswers`, and `service` replies with `summarize`'s
summary and `RenderSummary`, as `cli` prints them. This module imports neither `typer` nor
`rich`, so the site's engine, which runs `service` in a browser, loads neither (ADR 0100).
"""

import re
from collections import Counter
from typing import Annotated

import numpy as np
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from human_o_matic.analyze.sections import Sections, SectionSource, drum_bars
from human_o_matic.controls import StyleName
from human_o_matic.decisions import DecisionRequired
from human_o_matic.midi.io import MidiSong
from human_o_matic.midi.tempo import MICROSECONDS_PER_MINUTE, tempo_map
from human_o_matic.midi.tracks import DrumTrackReason, choose_drum_track, track_name
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.normalize.grid import GRIDS, Grid
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.creative import CreativeReport
from human_o_matic.render.engine import Rendered
from human_o_matic.render.guards import GuardCounts
from human_o_matic.render.target import ConversionReport, Placement

_PITCH = re.compile(r"[0-9]+")
_BEAT = re.compile(r"([0-9]+),([0-9]+)")


def _pitch(value: object) -> object:
    """A pitch key, written in decimal, as a number."""
    if isinstance(value, str):
        if _PITCH.fullmatch(value) is None:
            raise ValueError(f"{value!r} is not a pitch, 0 to 127")
        return int(value)
    return value


def _beat(value: object) -> object:
    """A beat key, `"bar,beat"` with both from 0, as `(bar, beat)`."""
    if isinstance(value, str):
        found = _BEAT.fullmatch(value)
        if found is None:
            raise ValueError(f'{value!r} is not a beat as "bar,beat", both counted from 0')
        return int(found[1]), int(found[2])
    return value


type Pitch = Annotated[int, BeforeValidator(_pitch), Field(ge=0, le=127)]
type BeatKey = Annotated[tuple[int, int], BeforeValidator(_beat)]


class Answers(BaseModel):
    """The answers file: the answers `normalize` takes that are not flags.

    `unmapped` is from a pitch, such as `"99"`, to an articulation of the kit or `"drop"`.
    `grids` is from a beat, `"bar,beat"` with both counted from 0, such as `"32,1"`, to its
    grid. `hit_types` is from a family to its `soft_below` and `accent_from` velocities.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    unmapped: dict[Pitch, str] = Field(default_factory=dict[Pitch, str])
    grids: dict[BeatKey, Grid] = Field(default_factory=dict[BeatKey, Grid])
    hit_types: dict[str, HitTypeBounds] = Field(default_factory=dict[str, HitTypeBounds])


def answer_problem(error: AnswerError) -> str:
    """An answer that doesn't fit the song, as `where: what` in the answers file, such as
    `grids.32,1: bar 33, beat 2 has no notes, so it has no grid`."""
    key = error.key
    where = f"{key[0]},{key[1]}" if isinstance(key, tuple) else str(key)
    return f"{error.argument}.{where}: {error}"


class DrumTrack(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    """Counted from 0."""
    name: str
    reason: DrumTrackReason


class Tempo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    given: bool
    """The tempo is the `bpm` given."""
    replaced: bool
    """The `bpm` given replaced the file's own tempo."""
    bpm: float
    """The tempo at the start."""
    changes: int
    """How many times the tempo changes after the start."""
    min_bpm: float
    max_bpm: float


class TimeSignatures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assumed: bool
    """No time signature is set at the start, so 4/4 is assumed until the first."""
    changes: tuple[tuple[int, str], ...]
    """Each signature in force as `(bar, "N/D")`, from bar 0."""


class NoteCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    read: int
    """The drum track's notes, which are the other three together."""
    score: int
    pending: int
    """Notes the kit doesn't map, waiting for an `unmapped` answer."""
    dropped: int
    """Notes an `unmapped` answer left out."""


class BeatCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    """The beats with notes."""
    ambiguous: int
    grids: dict[Grid, int]
    """The beats on each grid, in the order of `GRIDS`."""


class HitTypeCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    soft: int
    normal: int
    accent: int
    low_confidence: int
    """The notes whose type is a guess."""


class SectionCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    source: SectionSource
    """`markers` when the file's markers set the sections, and `drums` when the drums did."""


class SectionEntry(BaseModel):
    """One section as `analyze` prints it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: int
    """Its first bar, counting from 0."""
    bars: int
    group: str
    """Its repeat group, `A` for the first."""


class Summary(BaseModel):
    """What `analyze` found, as counts. No note is listed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    kit: str
    """`library/kit`."""
    track: DrumTrack
    ppq: int
    """The resolution the song is worked on at."""
    source_ppq: int
    tempo: Tempo
    time_signatures: TimeSignatures
    bars: int
    """From the start to the bar of the drum track's last note."""
    sections: SectionCounts
    notes: NoteCounts
    beats: BeatCounts
    families: dict[str, int]
    """The score's notes per family, by name."""
    hit_types: HitTypeCounts
    low_confidence: dict[str, int]
    """The notes read through each `low` confidence articulation (ADR 0025)."""


def summarize(
    file: str,
    song: MidiSong,
    normalized: Normalized,
    sections: Sections,
    *,
    track: int | None = None,
    bpm: float | None = None,
) -> Summary:
    """The summary of a song normalized with `track` and `bpm`, and its sections."""
    score = normalized.score
    drums = [note for note in song.notes if note.track == score.track]
    bpms = MICROSECONDS_PER_MINUTE / score.tempos.tempos
    families = Counter(note.family for note in score.notes)
    types = Counter(note.hit_type for note in score.notes)
    return Summary(
        file=file,
        kit=score.kit,
        track=DrumTrack(
            index=score.track,
            name=track_name(song, score.track),
            reason=choose_drum_track(song, track).reason,
        ),
        ppq=song.ppq,
        source_ppq=song.source_ppq,
        tempo=Tempo(
            given=bpm is not None,
            replaced=bpm is not None and _has_tempo(song),
            bpm=round(float(bpms[0]), 3),
            changes=int(np.count_nonzero(np.diff(score.tempos.tempos))),
            min_bpm=round(float(bpms.min()), 3),
            max_bpm=round(float(bpms.max()), 3),
        ),
        time_signatures=TimeSignatures(
            assumed=score.signatures.assumed,
            changes=tuple((bar, str(sig)) for _, bar, sig in score.signatures.changes),
        ),
        bars=drum_bars(song, score),
        sections=SectionCounts(count=len(sections.sections), source=sections.source),
        notes=NoteCounts(
            read=len(drums),
            score=len(score.notes),
            pending=len(normalized.pending),
            dropped=len(normalized.dropped),
        ),
        beats=BeatCounts(
            count=len(score.beats),
            ambiguous=len(score.ambiguous),
            grids={grid: sum(beat.grid == grid for beat in score.beats) for grid in GRIDS},
        ),
        families=dict(sorted(families.items())),
        hit_types=HitTypeCounts(
            soft=types["soft"],
            normal=types["normal"],
            accent=types["accent"],
            low_confidence=sum(note.hit_type_confidence == "low" for note in score.notes),
        ),
        low_confidence={entry.articulation: entry.count for entry in normalized.low_confidence},
    )


def _has_tempo(song: MidiSong) -> bool:
    """Whether the file has a tempo of its own."""
    try:
        tempo_map(song)
    except DecisionRequired:
        return False
    return True


class RenderAnswers(Answers):
    """The answers file of `render`: those of `analyze`, and `substitutions`, from a source
    articulation to an articulation of the target kit or `"drop"`, for `conversion` requests."""

    substitutions: dict[str, str] = Field(default_factory=dict[str, str])


class RenderedNotes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    written: int
    """The drum notes written."""
    kept: int
    """Of those, the notes of sections played as they came in."""
    dropped: int
    """Drum notes an `unmapped` or `substitutions` answer left out."""
    added: int
    """Of those written, the notes creative sections added (ADR 0091)."""


class RenderSummary(BaseModel):
    """What `render` wrote, as counts. No note is listed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    output: str
    kit: str
    """The kit the file was read with, as `library/kit`."""
    to_kit: str
    """The kit it was written to."""
    style: StyleName
    placeholder: bool
    """Whether the style's numbers are placeholders calibration hasn't replaced yet."""
    seed: int
    notes: RenderedNotes
    guards: GuardCounts
    conversion: ConversionReport
    """How the notes were placed in `to_kit`: the articulations written as another, the drums
    that land on one pitch, and the names read or written at `low` confidence (ADR 0075)."""
    creative: CreativeReport | None
    """What the creative sections added and couldn't, together, or None when none is
    (ADR 0095)."""


def rendered_notes(
    rendered: Rendered, normalized: Normalized, placement: Placement
) -> RenderedNotes:
    """How many drum notes a render wrote, kept, left out and added."""
    return RenderedNotes(
        written=len(rendered.notes),
        kept=sum(note.kept for note in rendered.notes),
        dropped=len(normalized.dropped) + len(placement.dropped),
        added=sum(report.notes for report in rendered.creative if report is not None),
    )
