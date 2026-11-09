"""Hand labels of where a song's sections begin, and the measurement of the detector on them.

A label file is TOML, one for each whole-song drum track, directly in `private/labels/`, which
is never committed (ADR 0007). It has these keys, and any other is an error (ADR 0034):
- `midi`: the song's MIDI file, relative to `private/` unless it is absolute;
- `from_map`: the built-in kit its drums are read through, as `analyze --from-map` takes it;
- `bpm`, optional: a constant tempo that replaces the file's own, from `MIN_BPM` to `MAX_BPM`;
- `track`, optional: the drum track, counting from 0;
- `starts`: the bar where each section begins, counting from 0, strictly increasing from 0 with
  at least one start after it, each below the song's bar count;
- `tuned`, optional: true for a track the detector's parameters were tuned on.

`measure` reads the song as `analyze` would with those answers, finds its sections with the
markers left out, and scores them against the label.
"""

import tomllib
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
)

from human_o_matic.analyze.scoring import BoundaryScore, score_starts
from human_o_matic.analyze.sections import drum_bars, find_sections
from human_o_matic.decisions import DecisionRequired
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiFileError, read_midi
from human_o_matic.midi.tempo import MAX_BPM, MIN_BPM
from human_o_matic.normalize.pipeline import normalize


class LabelError(ValueError):
    """A label file that can't be read or doesn't fit its song. The message names the file."""


class Label(BaseModel):
    """One label file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    midi: StrictStr
    from_map: StrictStr
    bpm: Annotated[float, Strict(), Field(ge=MIN_BPM, le=MAX_BPM)] | None = None
    track: Annotated[StrictInt, Field(ge=0)] | None = None
    starts: tuple[StrictInt, ...]
    tuned: StrictBool = False

    @field_validator("starts")
    @classmethod
    def _starts_from_bar_0(cls, starts: tuple[int, ...]) -> tuple[int, ...]:
        if not starts or starts[0] != 0:
            raise ValueError("the first section starts at bar 0")
        if len(starts) < 2:
            raise ValueError("at least one section starts after bar 0")
        for first, second in pairwise(starts):
            if second <= first:
                raise ValueError(f"bar {second} comes after bar {first}, so starts isn't in order")
        return starts


def read_label(path: Path) -> Label:
    """A label file. Raises `LabelError` saying what is wrong with it."""
    try:
        with path.open("rb") as file:
            return Label.model_validate(tomllib.load(file))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise LabelError(f"{path}: {error}") from error
    except ValidationError as error:
        problems = (
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors(include_url=False)
        )
        raise LabelError(f"{path}: {'; '.join(problems)}") from error


def read_labels(directory: Path) -> tuple[tuple[Path, Label], ...]:
    """Every label file (`*.toml`) directly in `directory`, in name order, with its path."""
    paths = sorted(path for path in directory.glob("*.toml") if path.is_file())
    return tuple((path, read_label(path)) for path in paths)


@dataclass(frozen=True, slots=True, kw_only=True)
class Measured:
    """A labelled track's detected sections and their score."""

    path: Path
    label: Label
    detected: tuple[int, ...]
    """The bar where each detected section starts, from 0."""
    score: BoundaryScore


def measure(path: Path, label: Label, root: Path) -> Measured:
    """The sections found in the song of the label at `path`, with the markers left out, scored
    against it. `root` is the folder a relative `midi` path starts from. Raises `LabelError`,
    naming the file, when the song can't be read, still asks for a tempo or a drum track, or has
    fewer bars than a labelled start."""
    try:
        kit = find_kit(label.from_map)
    except KeyError as error:
        raise LabelError(f"{path}: from_map: {error.args[0]}") from error
    try:
        song = read_midi(root / label.midi)
        normalized = normalize(song, kit, track=label.track, bpm=label.bpm)
    except (OSError, MidiFileError) as error:
        raise LabelError(f"{path}: midi: {error}") from error
    except DecisionRequired as asked:
        raise LabelError(f"{path}: {asked.request.kind}: {asked.request.message}") from asked
    bars = drum_bars(song, normalized.score)
    if label.starts[-1] >= bars:
        raise LabelError(
            f"{path}: starts: bar {label.starts[-1]} isn't in the song, which has {bars} bars"
        )
    found = find_sections(song, normalized.score, markers=False)
    return Measured(
        path=path,
        label=label,
        detected=found.starts,
        score=score_starts(found.starts, label.starts),
    )
