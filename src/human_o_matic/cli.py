"""The command line: `human-o-matic analyze` and `human-o-matic render`, for tests and scripting.

`analyze` reads a MIDI file through a built-in kit, normalizes its drums and finds their
sections, then prints one line of compact JSON on stdout: a summary of what was found, the
sections, and the decision requests, each as the MCP layer returns it
(`DecisionRequest.model_dump(mode="json")`). It never prints notes, only counts, bars, sections
and the requests, and it only reads: it writes no file and converts to no other kit.

The requests are answered by running it again. `--from-map`, `--track` and `--bpm` are flags, and
`--answers` names a JSON file holding `unmapped`, `grids` and `hit_types`, the other arguments a
request's `answer_with` names (ADR 0033).

`render` does the same, then renders the drums by a plan and writes them to a new MIDI file,
through `--to-map` when given, and prints its summary and each section's statistics instead
(ADR 0054). Its answers file also takes `substitutions`, and `--plan` names a JSON file of the
song's controls and each section's. It writes nothing while a request is open.

The exit code is 0 when no request is open and 3 when one is, with the JSON printed either way.
A usage error, such as a map that doesn't exist, a `--bpm` outside `MIN_BPM` to `MAX_BPM`, or an
answer that names something the song doesn't have (`AnswerError`), is 2 with its message on
stderr.
Anything else is a crash, 1.
"""

import json
import re
import textwrap
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, ValidationError

from human_o_matic.analyze.sections import Sections, SectionSource, drum_bars, find_sections
from human_o_matic.controls import (
    MAX_SEED,
    ControlVector,
    SectionPlan,
    SessionPlan,
    StyleName,
)
from human_o_matic.decisions import DecisionRequest, DecisionRequired
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_maps, find_kit
from human_o_matic.midi.io import MidiFileError, MidiSong, read_midi, write_midi
from human_o_matic.midi.tempo import MAX_BPM, MICROSECONDS_PER_MINUTE, MIN_BPM, tempo_map
from human_o_matic.midi.tracks import DrumTrackReason, choose_drum_track, track_name
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.normalize.grid import GRIDS, Grid
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.pipeline import normalize
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import render
from human_o_matic.render.guards import GuardCounts
from human_o_matic.render.measure import SectionStats, section_stats
from human_o_matic.render.style import STYLE_NAMES, built_in_styles
from human_o_matic.render.target import place_score

EXIT_OPEN = 3
"""The exit code when a decision request is open."""
FLAGS = ("from_map", "track", "bpm")
"""Answers given as flags, which the answers file doesn't take."""

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


def read_answers(text: str) -> Answers:
    """The answers in the text of an answers file. Raises `ValueError` saying what is wrong."""
    try:
        return Answers.model_validate_json(text)
    except ValidationError as error:
        raise ValueError("; ".join(_problems(error))) from error


def _problems(error: ValidationError) -> list[str]:
    """Each problem as `where: what`, such as `grids.32,1: Input should be ...`."""
    problems: list[str] = []
    for problem in error.errors(include_url=False):
        place = problem["loc"]
        where = ".".join(str(part) for part in place if part != "[key]")
        message = problem["msg"].removeprefix("Value error, ")
        if problem["type"] == "extra_forbidden" and len(place) == 1 and place[0] in FLAGS:
            message = f"given as --{str(place[0]).replace('_', '-')}, not in the answers file"
        problems.append(f"{where}: {message}" if where else message)
    return problems


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


def report(
    summary: Summary | None, sections: Sections | None, decisions: Sequence[DecisionRequest]
) -> str:
    """The compact JSON `analyze` prints: the summary and the sections, unless no score was
    made, and the decision requests."""
    out: dict[str, JsonValue] = {}
    if summary is not None:
        out["summary"] = summary.model_dump(mode="json")
    if sections is not None:
        out["sections"] = [
            SectionEntry(start=section.start, bars=section.bars, group=section.group).model_dump(
                mode="json"
            )
            for section in sections.sections
        ]
    out["decisions"] = [request.model_dump(mode="json") for request in decisions]
    return json.dumps(out, separators=(",", ":"))


def _maps_help() -> str:
    """The built-in maps, for the help of the commands that take one: a library with one kit by
    its id, and each kit of any other as `library/kit`. The help keeps these lines as they are
    (`\\b`), since rewrapping them could break an id at a hyphen."""
    kits = list(built_in_maps())
    per_library = Counter(kit.library.id for kit in kits)
    names = [kit.library.id if per_library[kit.library.id] == 1 else kit.ref for kit in kits]
    lines = textwrap.wrap(f"{', '.join(names)}.", width=76, break_on_hyphens=False)
    return "\b\nThe built-in maps:\n" + "\n".join(lines)


app = typer.Typer(
    name="human-o-matic",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


@app.callback()
def main() -> None:
    """Re-perform a drum MIDI file, section by section."""


@app.command(epilog=_maps_help())
def analyze(
    midi_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            metavar="MIDI_FILE",
            help="The MIDI file to read.",
        ),
    ],
    from_map: Annotated[
        str,
        typer.Option(
            "--from-map",
            metavar="LIBRARY[/KIT]",
            help="The built-in map the file is in, from those listed below. A library with one "
            "kit needs no kit.",
        ),
    ],
    track: Annotated[
        int | None, typer.Option(min=0, help="The track that holds the drums, from 0.")
    ] = None,
    bpm: Annotated[
        float | None,
        typer.Option(
            help=f"A constant tempo, which replaces the file's: {MIN_BPM:g} to {MAX_BPM:.0f} BPM."
        ),
    ] = None,
    answers: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="A JSON file of answers: unmapped, grids and hit_types, as the requests ask, "
            'such as {"hit_types": {"snare": {"soft_below": 50, "accent_from": 110}}}.',
        ),
    ] = None,
) -> None:
    """Normalize a song's drums, find their sections, and print a summary, the sections and the
    decision requests as JSON."""
    try:
        kit = find_kit(from_map)
    except KeyError as error:
        raise typer.BadParameter(str(error.args[0]), param_hint="'--from-map'") from error
    if bpm is not None and not MIN_BPM <= bpm <= MAX_BPM:
        raise typer.BadParameter(
            f"{bpm} is outside {MIN_BPM:g} to {MAX_BPM:.0f} BPM, a range of tempos a MIDI file "
            "can hold",
            param_hint="'--bpm'",
        )
    given = Answers()
    if answers is not None:
        try:
            given = read_answers(answers.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error), param_hint="'--answers'") from error
    try:
        song = read_midi(midi_file)
    except (OSError, MidiFileError) as error:
        raise typer.BadParameter(str(error), param_hint="'MIDI_FILE'") from error
    try:
        normalized = normalize(
            song,
            kit,
            track=track,
            bpm=bpm,
            unmapped=given.unmapped,
            grids=given.grids,
            hit_types=given.hit_types,
        )
    except DecisionRequired as asked:
        typer.echo(report(None, None, [asked.request]))
        raise typer.Exit(EXIT_OPEN) from None
    except MidiFileError as error:
        raise typer.BadParameter(str(error), param_hint="'MIDI_FILE'") from error
    except AnswerError as error:
        raise typer.BadParameter(answer_problem(error), param_hint="'--answers'") from error
    sections = find_sections(song, normalized.score)
    summary = summarize(str(midi_file), song, normalized, sections, track=track, bpm=bpm)
    typer.echo(report(summary, sections, normalized.decisions))
    if normalized.decisions:
        raise typer.Exit(EXIT_OPEN)


class RenderAnswers(Answers):
    """The answers file of `render`: those of `analyze`, and `substitutions`, from a source
    articulation to an articulation of the target kit or `"drop"`, for `conversion` requests."""

    substitutions: dict[str, str] = Field(default_factory=dict[str, str])


def read_render_answers(text: str) -> RenderAnswers:
    """The answers in the text of `render`'s answers file. Raises `ValueError` saying what is
    wrong."""
    try:
        return RenderAnswers.model_validate_json(text)
    except ValidationError as error:
        raise ValueError("; ".join(_problems(error))) from error


def _bar(value: object) -> object:
    """A bar key, written in decimal, as a number."""
    if isinstance(value, str):
        if _PITCH.fullmatch(value) is None:
            raise ValueError(f"{value!r} is not a bar, counted from 0")
        return int(value)
    return value


type BarKey = Annotated[int, BeforeValidator(_bar), Field(ge=0)]


class PlanFile(BaseModel):
    """The plan file of `render`: the song's `controls`, and each section's under `sections`,
    by the bar it starts at, counted from 0 as `analyze` prints `start`, such as `"8"`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    controls: ControlVector = ControlVector()
    sections: dict[BarKey, ControlVector] = Field(default_factory=dict[BarKey, ControlVector])


def read_plan(text: str) -> PlanFile:
    """The plan in the text of a plan file. Raises `ValueError` saying what is wrong."""
    try:
        return PlanFile.model_validate_json(text)
    except ValidationError as error:
        raise ValueError("; ".join(_problems(error))) from error


class RenderedNotes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    written: int
    """The drum notes written."""
    kept: int
    """Of those, the notes of sections played as they came in."""
    dropped: int
    """Drum notes an `unmapped` or `substitutions` answer left out."""


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


class RenderedSection(BaseModel):
    """One section as `render` prints it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: int
    bars: int
    group: str
    skip: bool
    """Played as it came in."""
    stats: SectionStats


def render_report(
    summary: RenderSummary | None,
    sections: Sequence[RenderedSection | SectionEntry],
    decisions: Sequence[DecisionRequest],
) -> str:
    """The compact JSON `render` prints: the summary unless nothing was written, the sections,
    and the decision requests."""
    out: dict[str, JsonValue] = {}
    if summary is not None:
        out["summary"] = summary.model_dump(mode="json")
    out["sections"] = [section.model_dump(mode="json") for section in sections]
    out["decisions"] = [request.model_dump(mode="json") for request in decisions]
    return json.dumps(out, separators=(",", ":"))


def _kit(name: str, flag: str) -> DrumKit:
    try:
        return find_kit(name)
    except KeyError as error:
        raise typer.BadParameter(str(error.args[0]), param_hint=f"'{flag}'") from error


def _listed(names: Sequence[str]) -> str:
    """`a, b and c`."""
    return f"{', '.join(names[:-1])} and {names[-1]}" if len(names) > 1 else "".join(names)


@app.command(name="render", epilog=_maps_help())
def render_song(
    midi_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            metavar="MIDI_FILE",
            help="The MIDI file to read.",
        ),
    ],
    from_map: Annotated[
        str,
        typer.Option(
            "--from-map",
            metavar="LIBRARY[/KIT]",
            help="The built-in map the file is in, from those listed below. A library with one "
            "kit needs no kit.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="The MIDI file to write: never the input, and not one that exists unless "
            "--overwrite is given.",
        ),
    ],
    seed: Annotated[
        int,
        typer.Option(
            min=0,
            max=MAX_SEED,
            help="The seed. The same file, answers, plan and seed write the same bytes, and "
            "another seed plays another take.",
        ),
    ],
    to_map: Annotated[
        str | None,
        typer.Option(
            "--to-map",
            metavar="LIBRARY[/KIT]",
            help="The built-in map to write to, from those listed below: the kit of the drum "
            "instrument that will play the file. Left out, the file's own.",
        ),
    ] = None,
    track: Annotated[
        int | None, typer.Option(min=0, help="The track that holds the drums, from 0.")
    ] = None,
    bpm: Annotated[
        float | None,
        typer.Option(
            help=f"A constant tempo, which replaces the file's: {MIN_BPM:g} to {MAX_BPM:.0f} BPM."
        ),
    ] = None,
    style: Annotated[
        str, typer.Option(help="The style: tight, the default, medium or loose.")
    ] = "tight",
    answers: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="A JSON file of answers: unmapped, grids, hit_types and substitutions, as the "
            'requests ask, such as {"hit_types": {"snare": {"soft_below": 50, "accent_from": '
            "110}}}.",
        ),
    ] = None,
    plan: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="A JSON file of controls: the song's under \"controls\", and each section's "
            'under "sections" by the bar it starts at, from 0, as the sections print "start", '
            'such as {"controls": {"energy": 0.8}, "sections": {"8": {"skip": true}}}. The '
            f"controls are {_listed(list(ControlVector.model_fields))}.",
        ),
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace the output file if it exists.")
    ] = False,
) -> None:
    """Normalize a song's drums, find their sections, render them by a plan and write a new MIDI
    file, then print a summary and each section's statistics as JSON.

    While a decision request is open it writes nothing, prints the sections and the requests, and
    exits 3: answer them, in --answers or with --track or --bpm, and run it again."""
    kit = _kit(from_map, "--from-map")
    target = _kit(to_map, "--to-map") if to_map is not None else kit
    if bpm is not None and not MIN_BPM <= bpm <= MAX_BPM:
        raise typer.BadParameter(
            f"{bpm} is outside {MIN_BPM:g} to {MAX_BPM:.0f} BPM, a range of tempos a MIDI file "
            "can hold",
            param_hint="'--bpm'",
        )
    chosen: StyleName | None = None
    for name in STYLE_NAMES:
        if name == style:
            chosen = name
    if chosen is None:
        raise typer.BadParameter(
            f"{style!r} is not a style; there are {', '.join(STYLE_NAMES)}",
            param_hint="'--style'",
        )
    if output.resolve() == midi_file.resolve():
        raise typer.BadParameter(
            "it is the input file, which is never overwritten", param_hint="'--output'"
        )
    if output.exists() and not overwrite:
        raise typer.BadParameter(
            f"{output} exists; give --overwrite to replace it", param_hint="'--output'"
        )
    given = RenderAnswers()
    if answers is not None:
        try:
            given = read_render_answers(answers.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error), param_hint="'--answers'") from error
    controls = PlanFile()
    if plan is not None:
        try:
            controls = read_plan(plan.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error), param_hint="'--plan'") from error
    try:
        song = read_midi(midi_file)
    except (OSError, MidiFileError) as error:
        raise typer.BadParameter(str(error), param_hint="'MIDI_FILE'") from error
    try:
        normalized = normalize(
            song,
            kit,
            track=track,
            bpm=bpm,
            unmapped=given.unmapped,
            grids=given.grids,
            hit_types=given.hit_types,
        )
    except DecisionRequired as asked:
        typer.echo(render_report(None, (), [asked.request]))
        raise typer.Exit(EXIT_OPEN) from None
    except MidiFileError as error:
        raise typer.BadParameter(str(error), param_hint="'MIDI_FILE'") from error
    except AnswerError as error:
        raise typer.BadParameter(answer_problem(error), param_hint="'--answers'") from error
    found = find_sections(song, normalized.score)
    entries = [
        SectionEntry(start=section.start, bars=section.bars, group=section.group)
        for section in found.sections
    ]
    try:
        placement = place_score(normalized.score, kit, target, given.substitutions)
    except AnswerError as error:
        raise typer.BadParameter(answer_problem(error), param_hint="'--answers'") from error
    except ValueError as error:
        raise typer.BadParameter(f"substitutions.{error}", param_hint="'--answers'") from error
    decisions = [*normalized.decisions, *placement.decisions]
    if decisions:
        typer.echo(render_report(None, entries, decisions))
        raise typer.Exit(EXIT_OPEN)
    starts = [section.start for section in found.sections]
    for start in sorted(controls.sections):
        if start not in starts:
            listed = ", ".join(str(bar) for bar in starts)
            raise typer.BadParameter(
                f"sections.{start}: no section starts at bar {start}; they start at {listed}",
                param_hint="'--plan'",
            )
    session = SessionPlan(
        style=chosen,
        seed=seed,
        controls=controls.controls,
        sections=tuple(
            SectionPlan(
                start=section.start,
                bars=section.bars,
                group=section.group,
                controls=controls.sections.get(section.start, ControlVector()),
            )
            for section in found.sections
        ),
    )
    rendered = render(song, normalized, placement, session)
    try:
        write_midi(rendered.song, output, overwrite=overwrite)
    except OSError as error:
        raise typer.BadParameter(str(error), param_hint="'--output'") from error
    defaults = built_in_styles()[chosen].defaults
    summary = RenderSummary(
        file=str(midi_file),
        output=str(output),
        kit=kit.ref,
        to_kit=target.ref,
        style=chosen,
        placeholder=built_in_styles()[chosen].placeholder,
        seed=seed,
        notes=RenderedNotes(
            written=len(rendered.notes),
            kept=sum(note.kept for note in rendered.notes),
            dropped=len(normalized.dropped) + len(placement.dropped),
        ),
        guards=rendered.guards,
    )
    sections = [
        RenderedSection(
            start=section.start,
            bars=section.bars,
            group=section.group,
            skip=session.controls_of(section, defaults).skip,
            stats=section_stats([note for note in rendered.notes if note.section == number]),
        )
        for number, section in enumerate(session.sections)
    ]
    typer.echo(render_report(summary, sections, ()))
