"""M4's blind test: each section of one song in five variants, shuffled under neutral names, with
a hidden key and a ratings sheet, and the ratings counted (ADRs 0101 to 0106).

`make` reads a session the owner saved by running the skill on the song (ADR 0079), renders the
whole song five ways through one built-in kit, `--kit`, and cuts each section with notes out of
each render into a file of its own (ADR 0101). The variants (ADRs 0102 and 0103):
1. quantized, one flat velocity: every note on its grid point at `--velocity`, 100 by default;
2. naive randomization: variant 1 with each note moved by its own draw from a normal spread of
   `NAIVE_SD_MS` and its velocity by a whole number from -`NAIVE_VELOCITY` to +`NAIVE_VELOCITY`;
3. the engine's defaults, no questions: the default style and controls, the session's seed;
4. guided by answers: the session's style, seed, controls and takes;
5. guided, velocities only: variant 4 with its style's timing set to nothing, so its
   velocities are variant 4's and every note is on its grid point.
Creative mode is off in every variant, so each variant of a section plays the same notes.

A trial's file is its section's bars, with a bar before them for any note played early, at the
song's tempo and meter, holding only those, the drum track's channel messages and the notes
(ADR 0104). The trials and each trial's variants are shuffled by `--seed`, the files are named
`trial-NN-x.mid` and written in that order, and the key that says which is which goes beside the
folder, never in it, with a blank ratings sheet in the folder, where each listener rates each
file in a copy of it from 1, the worst, to 5, the best (ADR 0105). `make` prints counts and
paths, never which file is which. It reads the session and never writes it: neither the folder
nor the key may be or hold the session's file or its input, even with `--overwrite`, and a folder
or key that exists is refused unless `--overwrite` is given.

`score` reads the key and one or more filled sheets, one per listener, and prints each variant's
mean rating and the gate's three comparisons, 4 against 2, 4 against 3 and 5 against 4, per trial
and overall, as JSON. It judges nothing: it counts (ADR 0106).

Run from the repository root:
    uv run python tools/make_ab.py make SESSION --kit LIBRARY[/KIT] --seed N --out FOLDER
    uv run python tools/make_ab.py score FOLDER.key.json RATINGS.csv [RATINGS.csv ...]
"""

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from human_o_matic.controls import MAX_SEED, SectionPlan, SessionPlan, StyleName
from human_o_matic.decisions import DecisionRequired
from human_o_matic.files import name_new, write_aside
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import META, Event, MidiFileError, MidiSong, Note, midi_bytes
from human_o_matic.midi.tempo import (
    META_TEMPO,
    META_TIME_SIGNATURE,
    MICROSECONDS_PER_MINUTE,
    TimeSignature,
)
from human_o_matic.normalize.score import Score
from human_o_matic.render.engine import Rendered, render
from human_o_matic.render.parts import LIMBS
from human_o_matic.render.style import Style, built_in_styles
from human_o_matic.render.target import Placement
from human_o_matic.session import (
    ID_PATTERN,
    INSTRUMENTS,
    Loaded,
    Session,
    SessionError,
    SessionStore,
    file_hash,
    load_song,
    plan_of,
)

type Variant = Literal[1, 2, 3, 4, 5]
VARIANTS: tuple[Variant, ...] = (1, 2, 3, 4, 5)
NAMES: Mapping[Variant, str] = {
    1: "quantized, one flat velocity",
    2: "naive randomization",
    3: "engine defaults, no questions",
    4: "guided by answers",
    5: "guided, velocities only with quantized timing",
}
PAIRS: tuple[tuple[Variant, Variant], ...] = ((4, 2), (4, 3), (5, 4))
"""The comparisons the gate reads: 4 must beat 2, 4 should beat 3, and 5 against 4 says whether
the timing is worth having."""

FLAT_VELOCITY = 100
"""Variant 1's one velocity: a common default note velocity, inside the range of every built-in
articulation."""
NAIVE_SD_MS = 8.0
"""The spread of variant 2's offsets, in milliseconds (the plan's M4)."""
NAIVE_VELOCITY = 12
"""Variant 2's velocities are variant 1's moved by at most this either way (the plan's M4)."""
LETTERS = "abcde"
"""A trial's files, one letter per variant in an order shuffled for each trial."""
SHEET = "ratings.csv"
SHEET_COLUMNS = ("file", "rating", "comment")
KEY_SUFFIX = ".key.json"
"""The key's default name: the folder's, with this after it, beside the folder."""
LOWEST, HIGHEST = 1, 5
"""A rating is a whole number from 1, the worst, to 5, the best."""
TRIAL_FILE = re.compile(r"trial-\d+-[a-e]\.mid")
"""The name of a trial's file: what `make` writes in its folder, with the sheet."""
MIN_DIGITS = 2
STREAM_SHUFFLE = 0
STREAM_NAIVE = 1
"""The spawn keys of the streams `make` draws from itself: the shuffle, and variant 2's draws for
each section, keyed by its first bar. The engine's variants draw from the session's seed."""
CHANNEL_MESSAGES = range(0xA0, 0xF0)
"""The status bytes of the channel messages a trial keeps besides its notes: aftertouch,
controllers, program changes, channel pressure and pitch bend."""
KEYED = (0xA0, 0xB0)
"""Of these, the kinds whose first data byte says which value they set: a key or a controller."""
MIDI_CLOCKS = 24
THIRTY_SECONDS = 8
"""A time signature's MIDI clocks per metronome click and 32nds per quarter note: the usual."""
MAX_TEMPO = 0xFFFFFF
EXIT_USAGE = 2
EXIT_OPEN = 3

type Performance = tuple[tuple[Note, ...], ...]
"""One variant's notes, section by section in the session's order, each at the ticks of its
section's file (`Window`), on its one track."""


class OutputError(ValueError):
    """An output `make` won't write: the input, or a file or folder that exists."""


class TrialEntry(BaseModel):
    """One trial: the section it plays."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trial: int = Field(ge=1)
    start: int = Field(ge=0)
    """The section's first bar, from 0, which names it."""
    bars: int = Field(ge=1)
    group: str
    name: str = ""
    skip: bool = False
    """Variant 4 plays it as it came in, as the user asked, and so does variant 5."""


class FileEntry(BaseModel):
    """One file: its trial and the variant it holds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    trial: int = Field(ge=1)
    variant: Variant
    sha256: str
    """The hash of the file's bytes as written."""


class Key(BaseModel):
    """The hidden key: which file is which, and what made them. Its JSON is `model_dump_json`,
    which `Key.model_validate_json` reads back."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1] = 1
    session: str
    midi_path: str
    midi_sha256: str
    kit: str
    """The kit every file is written through, as `library/kit`."""
    style: StyleName
    """The session's style, variant 4's and variant 5's."""
    session_seed: int
    """The engine's seed, the session's, which variants 3 to 5 render with."""
    seed: int
    """`make`'s own seed: the shuffle and variant 2's draws."""
    velocity: int
    """Variant 1's velocity, about which variant 2's are drawn."""
    questions: int | None = None
    """How many questions the session took, as the agent counted them (ADR 0090)."""
    variants: dict[str, str]
    """Each variant's number and what it is."""
    trials: tuple[TrialEntry, ...]
    files: tuple[FileEntry, ...]
    left_out: tuple[int, ...] = ()
    """The first bars of the sections with no notes, which make no trial."""
    creative_off: tuple[int, ...] = ()
    """The first bars of the sections the session made creative, rendered here without it."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Renders:
    """The engine's four renders of the song that the five variants come from."""

    quantized: Rendered
    """Variant 3's plan with no timing: every note on its grid point. Variants 1 and 2 take
    their notes from it."""
    defaults: Rendered
    """Variant 3."""
    guided: Rendered
    """Variant 4."""
    untimed: Rendered
    """Variant 5."""


@dataclass(frozen=True, slots=True)
class Window:
    """Where a section's file lies in the song: file tick 0 is the song's tick `shift`, the bar
    line before the section, or a bar of the first bar's length before the song for the first."""

    shift: int
    first: int
    """The section's first bar line."""
    end: int
    """The bar line after its last bar."""

    @property
    def origin(self) -> int:
        """The song's first tick the file holds."""
        return max(self.shift, 0)


@dataclass(frozen=True, slots=True, kw_only=True)
class Blind:
    """Everything `make` writes, in memory."""

    files: dict[str, bytes]
    """Each trial's files, by name, in name order."""
    key: Key
    sheet: str
    """The blank ratings sheet: a row per file, in name order."""


def untimed(style: Style) -> Style:
    """The style with nothing that moves a note in time (ADR 0103): each tempo band's offset
    shared by an onset, each hit's own jitter and its clip, and each limb's offset, `feel`'s
    offsets either way, and the song's timing drift, are 0. Its velocities are as they were."""
    nothing = dict.fromkeys(LIMBS, 0.0)
    return style.model_copy(
        update={
            "timing": tuple(
                band.model_copy(
                    update={
                        "shared_sd": 0.0,
                        "jitter_sd": (0.0, 0.0),
                        "jitter_clip": 0.0,
                        "limb_ms": nothing,
                    }
                )
                for band in style.timing
            ),
            "feel_ms": (0.0, 0.0),
            "drift_sd": 0.0,
        }
    )


def default_plan(session: Session) -> SessionPlan:
    """Variant 3's plan: the session's sections and seed, with no controls, the default style and
    every section's first take."""
    return SessionPlan(
        seed=session.seed,
        sections=tuple(
            SectionPlan(start=section.start, bars=section.bars, group=section.group)
            for section in session.sections
        ),
    )


def guided_plan(session: Session) -> SessionPlan:
    """Variant 4's plan: the session's, with creative mode off in every section."""
    plan = plan_of(session)
    return plan.model_copy(
        update={
            "sections": tuple(
                section.model_copy(
                    update={"controls": section.controls.model_copy(update={"creative": False})}
                )
                for section in plan.sections
            )
        }
    )


def render_variants(session: Session, loaded: Loaded) -> Renders:
    """The song rendered by the engine for each variant, through the session's instrument."""
    instrument = INSTRUMENTS[session.instrument]
    defaults, guided = default_plan(session), guided_plan(session)
    styles = built_in_styles()

    def run(plan: SessionPlan, style: Style | None = None) -> Rendered:
        return render(
            loaded.song,
            loaded.normalized,
            loaded.placement,
            plan,
            instrument=instrument,
            style=style,
        )

    return Renders(
        quantized=run(defaults, untimed(styles[defaults.style])),
        defaults=run(defaults),
        guided=run(guided),
        untimed=run(guided, untimed(styles[guided.style])),
    )


def window(score: Score, start: int, end: int) -> Window:
    """The window of the section from bar `start` to the bar before `end`."""
    signatures = score.signatures
    first = signatures.bar_start(start)
    if start > 0:
        shift = signatures.bar_start(start - 1)
    else:
        shift = first - (signatures.bar_start(1) - first)
    return Window(shift, first, signatures.bar_start(end))


def windows_of(score: Score, plan: SessionPlan) -> tuple[Window, ...]:
    """Each section's window, in the plan's order."""
    return tuple(window(score, section.start, section.end) for section in plan.sections)


def _in_file(note: Note, span: Window) -> Note:
    """A note of the song at its section's file's ticks, on the file's one track."""
    return replace(note, track=0, start=note.start - span.shift, end=note.end - span.shift)


def by_section(rendered: Rendered, windows: Sequence[Window]) -> Performance:
    """A render's notes as written, section by section, in play order."""
    return tuple(
        tuple(_in_file(note.note, span) for note in rendered.notes if note.section == number)
        for number, span in enumerate(windows)
    )


def _within(velocity: int, placement: Placement, position: int) -> int:
    """`velocity` held to 1 to 127 and to the velocities its note's articulation takes, so every
    variant plays the same articulations."""
    placed = placement.notes[position]
    if placed is None:
        raise ValueError("a note left out was taken to be written")
    low, high = placed.velocity
    return min(max(min(max(velocity, 1), 127), low), high)


def flat(
    quantized: Rendered, placement: Placement, windows: Sequence[Window], velocity: int
) -> Performance:
    """Variant 1: every note where the quantized render puts it, at one velocity."""
    return tuple(
        tuple(
            replace(_in_file(note.note, span), velocity=_within(velocity, placement, note.position))
            for note in quantized.notes
            if note.section == number
        )
        for number, span in enumerate(windows)
    )


def naive_stream(seed: int, start: int) -> np.random.Generator:
    """Variant 2's stream for the section whose first bar is `start`."""
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(STREAM_NAIVE, start)))


def naive(
    quantized: Rendered,
    loaded: Loaded,
    plan: SessionPlan,
    windows: Sequence[Window],
    *,
    seed: int,
    velocity: int,
) -> Performance:
    """Variant 2: each of variant 1's notes moved by its own offset, drawn from a normal spread of
    `NAIVE_SD_MS` about 0, and its velocity by a whole number drawn evenly from
    -`NAIVE_VELOCITY` to +`NAIVE_VELOCITY`, each section from its own stream. Nothing holds
    them to the engine's guards, but each note keeps its length and stays in its file, and the
    notes of one pitch never start on one tick or overlap, so the file plays as written."""
    score = loaded.normalized.score
    tempos = score.tempos
    after = 1 + max(
        [event.order for event in quantized.song.events if event.track == score.track]
        + [note.note.off_order for note in quantized.notes],
        default=0,
    )
    out: list[tuple[Note, ...]] = []
    for number, (section, span) in enumerate(zip(plan.sections, windows, strict=True)):
        notes = [note for note in quantized.notes if note.section == number]
        rng = naive_stream(seed, section.start)
        offsets: list[float] = rng.normal(0.0, NAIVE_SD_MS, len(notes)).tolist()
        changes: list[int] = rng.integers(
            -NAIVE_VELOCITY, NAIVE_VELOCITY, size=len(notes), endpoint=True
        ).tolist()
        moved: list[Note] = []
        for note, offset, change in zip(notes, offsets, changes, strict=True):
            written = note.note
            # Before the song's first tick, its first tempo goes on, as in the file's lead-in.
            start = round(tempos.ms_to_tick(tempos.tick_to_ms(written.start) + offset))
            start = max(start - span.shift, 0)
            moved.append(
                replace(
                    written,
                    track=0,
                    start=start,
                    end=start + max(written.end - written.start, 1),
                    velocity=_within(velocity + change, loaded.placement, note.position),
                )
            )
        out.append(playable(moved, after))
    return tuple(out)


def playable(notes: Sequence[Note], after: int) -> tuple[Note, ...]:
    """The notes with no two of one pitch starting on one tick, each ending by the next of its
    pitch, and each taking its order by when it starts, after `after`, so a note-off on the
    tick of the next note-on of its pitch is written first."""
    held = list(notes)
    last: dict[tuple[int, int], int] = {}
    for index in sorted(range(len(held)), key=lambda index: (held[index].start, index)):
        note = held[index]
        key = (note.channel, note.pitch)
        if key in last:
            before = held[last[key]]
            if note.start <= before.start:
                length = note.end - note.start
                note = replace(note, start=before.start + 1, end=before.start + 1 + length)
                held[index] = note
            held[last[key]] = replace(before, end=min(before.end, note.start))
        last[key] = index
    ranked = sorted(range(len(held)), key=lambda index: (held[index].start, index))
    return tuple(
        replace(held[index], order=after + rank, off_order=after + rank)
        for rank, index in enumerate(ranked)
    )


def performances(
    session: Session, loaded: Loaded, renders: Renders, *, seed: int, velocity: int
) -> dict[Variant, Performance]:
    """Each variant's notes, section by section."""
    plan = default_plan(session)
    windows = windows_of(loaded.normalized.score, plan)
    return {
        1: flat(renders.quantized, loaded.placement, windows, velocity),
        2: naive(renders.quantized, loaded, plan, windows, seed=seed, velocity=velocity),
        3: by_section(renders.defaults, windows),
        4: by_section(renders.guided, windows),
        5: by_section(renders.untimed, windows),
    }


def trial_file(
    song: MidiSong, score: Score, span: Window, notes: Sequence[Note], length: int
) -> bytes:
    """One variant of a section as a format 0 file `length` ticks long: the notes, at the file's
    ticks, and the song's tempo, time signature and drum track's channel messages over the
    window, moved by its shift, with the values in force at its origin at the file's first tick.
    It names nothing: no track name, marker or text."""
    shift, origin = span.shift, span.origin
    end = length + shift
    tempos = score.tempos
    meta: list[Event] = [_tempo(0, MICROSECONDS_PER_MINUTE / tempos.bpm(origin))]
    starts: list[int] = tempos.starts.tolist()
    values: list[float] = tempos.tempos.tolist()
    meta.extend(
        _tempo(start - shift, value)
        for start, value in zip(starts, values, strict=True)
        if origin < start < end
    )
    signatures = score.signatures
    meta.append(_signature(0, signatures.signature_at(origin)))
    meta.extend(
        _signature(tick - shift, signature)
        for tick, _, signature in signatures.changes
        if origin < tick < end
    )
    held: dict[tuple[int, int | None], Event] = {}
    """The last of each kind of channel message before the origin."""
    inside: list[Event] = []
    for event in song.events:
        if event.track != score.track or event.status not in CHANNEL_MESSAGES:
            continue
        if event.tick < origin:
            which = event.data[0] if (event.status & 0xF0) in KEYED and event.data else None
            held[(event.status, which)] = event
        elif event.tick < end:
            inside.append(event)
    carried = [
        replace(event, track=0, tick=0) for event in sorted(held.values(), key=_by_order)
    ] + [replace(event, track=0, tick=event.tick - shift) for event in inside]
    trial = MidiSong(
        format=0,
        ppq=song.ppq,
        source_ppq=song.ppq,
        notes=tuple(sorted(notes, key=lambda note: (note.start, note.order))),
        events=tuple(sorted([*meta, *carried], key=lambda event: (event.tick, event.order))),
        track_ends=(length,),
    )
    return midi_bytes(trial)


def _by_order(event: Event) -> int:
    return event.order


def _tempo(tick: int, microseconds: float) -> Event:
    value = min(max(round(microseconds), 1), MAX_TEMPO)
    return Event(
        track=0,
        tick=tick,
        status=META,
        meta_type=META_TEMPO,
        data=value.to_bytes(3, "big"),
        order=-1,
    )


def _signature(tick: int, signature: TimeSignature) -> Event:
    power = signature.denominator.bit_length() - 1
    return Event(
        track=0,
        tick=tick,
        status=META,
        meta_type=META_TIME_SIGNATURE,
        data=bytes((signature.numerator, power, MIDI_CLOCKS, THIRTY_SECONDS)),
        order=-1,
    )


def shuffle_stream(seed: int) -> np.random.Generator:
    """The stream the trials' order and each trial's letters are drawn from."""
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(STREAM_SHUFFLE,)))


def make(
    session: Session,
    loaded: Loaded,
    *,
    seed: int,
    velocity: int = FLAT_VELOCITY,
    questions: int | None = None,
) -> Blind:
    """The blind test of the session's song, read as `loaded` through the kit every file is
    written in: each section with notes a trial, in an order the seed shuffles, each with its
    five variants under letters shuffled again for each trial, and the key and the sheet."""
    renders = render_variants(session, loaded)
    played = performances(session, loaded, renders, seed=seed, velocity=velocity)
    score = loaded.normalized.score
    guided = guided_plan(session)
    defaults = built_in_styles()[guided.style].defaults
    sections = guided.sections
    windows = windows_of(score, guided)
    chosen = [number for number in range(len(sections)) if played[3][number]]
    rng = shuffle_stream(seed)
    order: list[int] = rng.permutation(len(chosen)).tolist()
    digits = max(MIN_DIGITS, len(str(len(chosen))))
    files: dict[str, bytes] = {}
    entries: list[FileEntry] = []
    trials: list[TrialEntry] = []
    for trial, index in enumerate(order, start=1):
        number = chosen[index]
        section = session.sections[number]
        trials.append(
            TrialEntry(
                trial=trial,
                start=section.start,
                bars=section.bars,
                group=section.group,
                name=section.name,
                skip=guided.controls_of(sections[number], defaults).skip,
            )
        )
        span = windows[number]
        length = max(
            [span.end - span.shift]
            + [note.end for variant in VARIANTS for note in played[variant][number]]
        )
        letters: list[int] = rng.permutation(len(VARIANTS)).tolist()
        for letter, which in zip(LETTERS, letters, strict=True):
            variant = VARIANTS[which]
            name = f"trial-{trial:0{digits}d}-{letter}.mid"
            data = trial_file(loaded.song, score, span, played[variant][number], length)
            files[name] = data
            entries.append(
                FileEntry(file=name, trial=trial, variant=variant, sha256=file_hash(data))
            )
    asked = plan_of(session)
    key = Key(
        session=session.id,
        midi_path=session.midi_path,
        midi_sha256=session.midi_sha256,
        kit=loaded.target.ref,
        style=session.style,
        session_seed=session.seed,
        seed=seed,
        velocity=velocity,
        questions=questions,
        variants={str(variant): NAMES[variant] for variant in VARIANTS},
        trials=tuple(trials),
        files=tuple(entries),
        left_out=tuple(
            section.start for number, section in enumerate(sections) if number not in chosen
        ),
        creative_off=tuple(
            section.start
            for section in asked.sections
            if asked.controls_of(section, defaults).creative
        ),
    )
    sheet = io.StringIO()
    writer = csv.writer(sheet, lineterminator="\n")
    writer.writerow(SHEET_COLUMNS)
    writer.writerows((name, "", "") for name in files)
    return Blind(files=files, key=key, sheet=sheet.getvalue())


def key_path(out: Path) -> Path:
    """The key's default path: beside the folder, named after it."""
    return out.with_name(out.name + KEY_SUFFIX)


def _ours(path: Path) -> bool:
    """Whether `make` writes a file of this name in its folder."""
    return path.name == SHEET or TRIAL_FILE.fullmatch(path.name) is not None


def check_outputs(out: Path, key: Path, kept: Mapping[str, Path], *, overwrite: bool) -> None:
    """Raises `OutputError` when the folder holds, or the key is, a file of `kept`, the files
    `make` never writes, by what each is, such as the session's file and its input, whatever
    `overwrite` says; when the key would go in the folder or a parent folder is missing; and when
    the folder or the key exists without `overwrite`, or exists as something `make` doesn't
    write."""
    folder = out.resolve()
    for what, path in kept.items():
        if path.resolve().is_relative_to(folder):
            raise OutputError(f"{out} holds {what}, which make_ab never writes")
        if key.resolve() == path.resolve() or (
            key.exists() and path.exists() and key.samefile(path)
        ):
            raise OutputError(f"{key} is {what}, which make_ab never writes")
    if key.resolve().is_relative_to(folder):
        raise OutputError(f"the key {key} goes beside {out}, never in it, so no listener opens it")
    for path in (out, key):
        if not path.resolve().parent.is_dir():
            raise OutputError(f"{path.parent} isn't a folder that exists")
    if out.exists():
        if not overwrite:
            raise OutputError(f"{out} exists; give --overwrite to replace what make_ab wrote there")
        if not out.is_dir():
            raise OutputError(f"{out} isn't a folder")
        for path in sorted(out.iterdir()):
            if _ours(path) and not path.is_file():
                raise OutputError(f"{path} isn't a file, so it is left as it is")
    if key.exists():
        if not overwrite:
            raise OutputError(f"{key} exists; give --overwrite to replace it")
        if not key.is_file():
            raise OutputError(f"{key} isn't a file")


def write(blind: Blind, out: Path, key: Path, *, overwrite: bool) -> None:
    """Write the trials and the sheet into `out`, in name order, and the key to `key`.

    A new folder is written whole beside itself first and only then takes its name, and a new
    key takes its name by `files.name_new`, which fails when it is taken, so a failure leaves
    neither. With `overwrite`, the files `make` wrote in the folder before are removed, any other
    file is left as it is, each new file replaces its name, and the key replaces the old one.
    Raises `OSError`, and `FileExistsError` for a name taken meanwhile."""
    named: Path | None = None
    aside = write_aside(key.resolve().parent, blind.key.model_dump_json(indent=2).encode())
    try:
        if out.exists() and overwrite:
            for path in sorted(out.iterdir()):
                if _ours(path):
                    path.unlink()
            _fill(out, blind)
        else:
            building = Path(tempfile.mkdtemp(dir=out.resolve().parent, prefix=f".{out.name}."))
            try:
                _fill(building, blind)
                building.rename(out)
                named = out
            finally:
                if building.exists():
                    shutil.rmtree(building)
        if overwrite:
            os.replace(aside, key)
        else:
            name_new(aside, key)
    except BaseException:
        if named is not None:
            shutil.rmtree(named)
        raise
    finally:
        aside.unlink(missing_ok=True)


def _fill(folder: Path, blind: Blind) -> None:
    """The trials' files then the sheet, each in name order, so not even the order the files
    were made in says which variant is which."""
    for name, data in [*blind.files.items(), (SHEET, blind.sheet.encode())]:
        os.replace(write_aside(folder, data), folder / name)


def session_path(given: str) -> Path:
    """The file of the session given by an ID, kept in the state directory, or by the path of its
    JSON file."""
    if ID_PATTERN.fullmatch(given) is not None and not Path(given).exists():
        return SessionStore().path(given)
    return Path(given).expanduser()


def read_session(given: str) -> Session:
    """The session of an ID, kept in the state directory, or of the path of its JSON file.
    Raises `SessionError`."""
    if ID_PATTERN.fullmatch(given) is not None and not Path(given).exists():
        return SessionStore().load(given)
    path = session_path(given)
    try:
        return Session.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SessionError(f"the session {path} can't be read: {error}") from error
    except ValidationError as error:
        raise SessionError(f"{path} isn't a valid session: {error}") from error


class SheetError(ValueError):
    """A ratings sheet that can't be read, or names a file or a rating the key doesn't take."""


def read_sheet(path: Path, key: Key) -> dict[str, int]:
    """A filled sheet: each rated file's rating. A blank rating is a file not rated. Raises
    `SheetError`."""
    known = {entry.file for entry in key.files}
    try:
        rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise SheetError(f"{path} can't be read: {error}") from error
    if not rows or tuple(cell.strip() for cell in rows[0][:2]) != SHEET_COLUMNS[:2]:
        raise SheetError(f"{path} doesn't start with the columns {', '.join(SHEET_COLUMNS)}")
    ratings: dict[str, int] = {}
    seen: set[str] = set()
    for number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        name = row[0].strip()
        text = row[1].strip() if len(row) > 1 else ""
        where = f"{path.name}, line {number}"
        if name not in known:
            raise SheetError(f"{where}: {name!r} isn't a file of this key")
        if name in seen:
            raise SheetError(f"{where}: {name} has two rows")
        seen.add(name)
        if not text:
            continue
        if not text.isdigit() or not LOWEST <= int(text) <= HIGHEST:
            raise SheetError(f"{where}: {text!r} isn't a rating from {LOWEST} to {HIGHEST}")
        ratings[name] = int(text)
    return ratings


def score(key: Key, sheets: Sequence[Mapping[str, int]]) -> dict[str, JsonValue]:
    """Each variant's mean rating over every sheet, and for each of the gate's pairs, each trial's
    mean of each variant over the sheets that rate both, which of them is higher, and over the
    trials, how often each is higher, how often they tie and the mean difference."""
    entry_of = {entry.file: entry for entry in key.files}
    given: dict[tuple[int, int, Variant], int] = {}
    """Each sheet's rating of each trial's variant."""
    for number, sheet in enumerate(sheets):
        for name, rating in sheet.items():
            entry = entry_of[name]
            given[(number, entry.trial, entry.variant)] = rating
    variants: list[JsonValue] = []
    for variant in VARIANTS:
        found = [rating for (_, _, which), rating in given.items() if which == variant]
        variants.append(
            {
                "variant": variant,
                "name": NAMES[variant],
                "ratings": len(found),
                "mean": _mean(found),
            }
        )
    comparisons: list[JsonValue] = []
    for first, second in PAIRS:
        rows: list[JsonValue] = []
        higher = {first: 0, second: 0}
        ties = 0
        differences: list[float] = []
        for trial in key.trials:
            both = [
                (given[(number, trial.trial, first)], given[(number, trial.trial, second)])
                for number in range(len(sheets))
                if (number, trial.trial, first) in given and (number, trial.trial, second) in given
            ]
            if not both:
                rows.append(
                    {"trial": trial.trial, "start": trial.start, "means": None, "higher": None}
                )
                continue
            ours, theirs = sum(pair[0] for pair in both), sum(pair[1] for pair in both)
            better: Variant | None = first if ours > theirs else second if theirs > ours else None
            if better is None:
                ties += 1
            else:
                higher[better] += 1
            differences.append((ours - theirs) / len(both))
            rows.append(
                {
                    "trial": trial.trial,
                    "start": trial.start,
                    "means": [_mean([pair[0] for pair in both]), _mean([pair[1] for pair in both])],
                    "higher": better,
                }
            )
        comparisons.append(
            {
                "pair": [first, second],
                "trials": rows,
                "first_higher": higher[first],
                "second_higher": higher[second],
                "ties": ties,
                "mean_difference": _mean(differences),
            }
        )
    return {
        "sheets": len(sheets),
        "questions": key.questions,
        "variants": variants,
        "comparisons": comparisons,
    }


def _mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _seed(text: str) -> int:
    return _whole(text, 0, MAX_SEED, "a seed")


def _velocity(text: str) -> int:
    return _whole(text, 1, 127, "a velocity")


def _count(text: str) -> int:
    return _whole(text, 0, None, "a count")


def _whole(text: str, low: int, high: int | None, what: str) -> int:
    span = f"from {low} to {high}" if high is not None else f"from {low}"
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not {what} {span}") from error
    if value < low or (high is not None and value > high):
        raise argparse.ArgumentTypeError(f"{text!r} is not {what} {span}")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M4's blind test: five variants of each section, shuffled, and their ratings."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    making = commands.add_parser(
        "make", help="write each section's five variants, the hidden key and a ratings sheet"
    )
    making.add_argument(
        "session", help="the session's ID, kept in the state directory, or its JSON file's path"
    )
    making.add_argument(
        "--kit",
        required=True,
        metavar="LIBRARY[/KIT]",
        help="the built-in kit every file is written through: the drum instrument's",
    )
    making.add_argument(
        "--seed", required=True, type=_seed, help="the seed of the shuffle and of variant 2's draws"
    )
    making.add_argument(
        "--out",
        required=True,
        type=Path,
        help="the folder of the trials and the ratings sheet, which mustn't exist",
    )
    making.add_argument(
        "--key",
        type=Path,
        help=f"the hidden key, by default beside the folder as FOLDER{KEY_SUFFIX}",
    )
    making.add_argument(
        "--velocity",
        type=_velocity,
        default=FLAT_VELOCITY,
        help=f"variant 1's one velocity, which variant 2's are drawn about (default "
        f"{FLAT_VELOCITY})",
    )
    making.add_argument(
        "--questions",
        type=_count,
        help="how many questions the session took, as the agent counted them, kept in the key",
    )
    making.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the key, and the files make_ab wrote in the folder before",
    )
    scoring = commands.add_parser(
        "score", help="count the ratings of one or more filled sheets against the key"
    )
    scoring.add_argument("key", type=Path, help="the key make wrote")
    scoring.add_argument("sheets", type=Path, nargs="+", help="filled sheets, one per listener")
    args = parser.parse_args(argv)
    if args.command == "score":
        return _score(args.key, args.sheets)
    return _make(
        args.session,
        args.kit,
        seed=args.seed,
        out=args.out,
        key=args.key if args.key is not None else key_path(args.out),
        velocity=args.velocity,
        questions=args.questions,
        overwrite=args.overwrite,
    )


def _make(
    given: str,
    kit_name: str,
    *,
    seed: int,
    out: Path,
    key: Path,
    velocity: int,
    questions: int | None,
    overwrite: bool,
) -> int:
    try:
        kit = find_kit(kit_name)
    except KeyError as error:
        print(f"error: --kit: {error.args[0]}", file=sys.stderr)
        return EXIT_USAGE
    try:
        session = read_session(given)
        kept = {
            "the session's file": session_path(given),
            "the session's input file": Path(session.midi_path),
        }
        check_outputs(out, key, kept, overwrite=overwrite)
        loaded = load_song(session.model_copy(update={"to_map": kit.ref}))
    except DecisionRequired as asked:
        print(json.dumps({"decisions": [asked.request.model_dump(mode="json")]}))
        return EXIT_OPEN
    except KeyError as error:
        print(f"error: the session's kit: {error.args[0]}", file=sys.stderr)
        return EXIT_USAGE
    except (SessionError, OutputError, MidiFileError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    if loaded.decisions:
        decisions = [request.model_dump(mode="json") for request in loaded.decisions]
        print(json.dumps({"decisions": decisions}, separators=(",", ":")))
        print(
            "error: the session has requests open in this kit; answer them in the session first",
            file=sys.stderr,
        )
        return EXIT_OPEN
    blind = make(session, loaded, seed=seed, velocity=velocity, questions=questions)
    try:
        write(blind, out, key, overwrite=overwrite)
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    summary = {
        "out": str(out),
        "key": str(key),
        "sheet": str(out / SHEET),
        "kit": blind.key.kit,
        "trials": len(blind.key.trials),
        "files": len(blind.files),
        "left_out": list(blind.key.left_out),
        "creative_off": list(blind.key.creative_off),
    }
    print(json.dumps(summary, separators=(",", ":")))
    return 0


def _score(path: Path, sheets: Sequence[Path]) -> int:
    try:
        key = Key.model_validate_json(path.read_bytes())
        ratings = [read_sheet(sheet, key) for sheet in sheets]
    except (OSError, ValidationError, SheetError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    print(json.dumps(score(key, ratings), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
