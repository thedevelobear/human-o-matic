"""Rendering a score: each section drawn from its own stream, the song's drifts, the guards, and
the drum track written back with the rendered notes (ADRs 0048 to 0050).

Randomness comes only from `numpy.random.Generator`s built from a `SeedSequence` of the plan's
seed (ADR 0049). Each section draws from its own stream, keyed by its first bar and its take, so
rendering one section again leaves the others' draws as they were. The song's slow drifts in
timing and velocity have streams of their own, drawn once at every tick of the score, so they
change only with the seed. The same song, answers, plan and seed always give the same file.
"""

import bisect
from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import exp, sqrt

import numpy as np

from human_o_matic.analyze.sections import drum_bars
from human_o_matic.controls import SessionPlan
from human_o_matic.instruments.base import Instrument
from human_o_matic.instruments.drums import DRUMS
from human_o_matic.midi.io import MidiSong, Note
from human_o_matic.midi.tempo import FloatArray
from human_o_matic.normalize.hit_types import HitType
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.backends.parametric import sample
from human_o_matic.render.controllers import windows
from human_o_matic.render.guards import GuardCounts, Slot, Tally, hold_timing, hold_velocity
from human_o_matic.render.output import with_drums
from human_o_matic.render.parts import Part, play_key
from human_o_matic.render.style import STYLES
from human_o_matic.render.target import Placement

STREAM_DRIFT = 0
STREAM_SECTION = 1
DRIFT_TIMING = 0
DRIFT_ENERGY = 1


def section_stream(seed: int, start: int, take: int) -> np.random.Generator:
    """The stream of the section whose first bar is `start`, for one take."""
    return np.random.default_rng(
        np.random.SeedSequence(seed, spawn_key=(STREAM_SECTION, start, take))
    )


def drift_stream(seed: int, kind: int) -> np.random.Generator:
    """The stream of one of the song's drifts, `DRIFT_TIMING` or `DRIFT_ENERGY`."""
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(STREAM_DRIFT, kind)))


def drift(
    times: FloatArray, sd: float, constants: Sequence[float], rng: np.random.Generator
) -> FloatArray:
    """A slow drift at ascending `times`: the sum of one process per time constant, each
    reverting to 0 at that pace (Ornstein-Uhlenbeck, sampled exactly), with `sd` the spread of
    the sum."""
    total = np.zeros(times.size)
    if not times.size or not constants:
        return total
    each = sd / sqrt(len(constants))
    steps = np.diff(times)
    for constant in constants:
        noise = rng.standard_normal(times.size)
        values = np.empty(times.size)
        values[0] = each * noise[0]
        for number, step in enumerate(steps, start=1):
            keep = exp(-float(step) / constant)
            values[number] = (
                keep * values[number - 1] + each * sqrt(1 - keep * keep) * noise[number]
            )
        total += values
    return total


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderedNote:
    """One note as rendered, with what measuring it needs."""

    position: int
    """Its position in `Score.notes`."""
    section: int
    kept: bool
    """Played as it came in."""
    part: Part
    hit_type: HitType
    grace: bool
    family: str
    piece: int
    """The drum it is written as."""
    note: Note
    """As written."""
    offset_ms: float
    """Its start's distance from its grid point."""
    strong: bool
    """Whether it was drawn as a strong alternating rider hit."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Rendered:
    song: MidiSong
    notes: tuple[RenderedNote, ...]
    """In play order (`play_key`), without the notes left out."""
    guards: GuardCounts


def render(
    song: MidiSong,
    normalized: Normalized,
    placement: Placement,
    plan: SessionPlan,
    *,
    instrument: Instrument = DRUMS,
) -> Rendered:
    """Render the song's drums by the plan, written as `placement` places them.

    Raises `ValueError` while notes wait for an `unmapped_notes` or `conversion` answer, and
    when the plan's sections don't cover the drums' bars.
    """
    if not normalized.complete:
        raise ValueError("drum notes wait for an unmapped_notes answer, so none can be rendered")
    if not placement.complete:
        raise ValueError("notes wait for a conversion answer, so none can be rendered")
    score = normalized.score
    bars = drum_bars(song, score)
    if plan.bars != bars:
        raise ValueError(f"the plan's sections cover {plan.bars} bars, and the drums {bars}")
    if plan.style not in STYLES:
        raise ValueError(f"the style {plan.style} isn't built in")
    style = STYLES[plan.style]
    parts = instrument.parts(score)
    starts = [section.start for section in plan.sections]
    section_of = [
        bisect.bisect_right(starts, score.beats[note.beat].bar) - 1 for note in score.notes
    ]

    ticks = np.unique(np.array([note.tick for note in score.notes], dtype=np.int64))
    quarters = ticks / score.ppq
    timing = drift(
        quarters,
        style.drift_sd,
        style.drift_quarters,
        drift_stream(plan.seed, DRIFT_TIMING),
    )
    energy = drift(
        quarters,
        style.energy_drift_sd,
        (style.energy_drift_quarters,),
        drift_stream(plan.seed, DRIFT_ENERGY),
    )
    at = {int(tick): number for number, tick in enumerate(ticks)}

    count = len(score.notes)
    order = sorted(
        (position for position in range(count) if placement.notes[position] is not None),
        key=lambda position: (play_key(score.notes[position]), position),
    )
    velocities = np.zeros(count)
    floors = np.ones(count)
    offsets = np.zeros(count)
    strong = np.zeros(count, dtype=np.bool_)
    kept = [False] * count
    for number, section in enumerate(plan.sections):
        controls = plan.controls_of(section, style.defaults)
        members = [position for position in order if section_of[position] == number]
        if controls.skip:
            for position in members:
                kept[position] = True
            continue
        first = score.signatures.bar_start(section.start)
        length = max(score.signatures.bar_start(section.end) - first, 1)
        notes = [score.notes[position] for position in members]
        draw = sample(
            notes,
            [parts[position] for position in members],
            [min(max((note.tick - first) / length, 0.0), 1.0) for note in notes],
            instrument.compile(controls, style, score.tempos.bpm(first)),
            section_stream(plan.seed, section.start, section.take),
        )
        for index, position in enumerate(members):
            tick = at[score.notes[position].tick]
            velocities[position] = draw.velocities[index] + energy[tick]
            floors[position] = draw.floors[index]
            offsets[position] = draw.offsets_ms[index] + timing[tick]
            strong[position] = draw.strong[index]

    held_to = windows(song, score, placement)
    slot_of = {position: number for number, position in enumerate(order)}
    by_source = {note.source_index: position for position, note in enumerate(score.notes)}
    base = _after_orders(song, score.track)
    slots: list[Slot] = []
    for number, position in enumerate(order):
        note = score.notes[position]
        placed = placement.notes[position]
        if placed is None:
            raise ValueError("a note left out was taken to be written")
        main = slot_of.get(by_source[note.grace_of]) if note.grace_of is not None else None
        # A note played as it came in, or one held to its controller events, keeps its order
        # among the drum track's messages. Any other takes its place in play order, after them.
        own = kept[position] or placed.controllers is not None
        slots.append(
            Slot(
                section=section_of[position],
                kept=kept[position],
                source=note.source,
                tick=note.tick,
                main=main,
                channel=placed.channel,
                pitch=placed.pitch,
                drum=(placed.family, placed.piece),
                soft=note.hit_type == "soft",
                velocity=placed.velocity,
                order=note.source.order if own else base + number,
                off_order=note.source.off_order if own else base + number,
                window=held_to[position],
            )
        )
    tally = Tally()
    timed = hold_timing(slots, offsets[order], score.tempos, tally)
    held = hold_velocity(slots, velocities[order], floors[order], tally)

    out: list[RenderedNote] = []
    drum_notes: list[Note] = []
    for number, (position, slot) in enumerate(zip(order, slots, strict=True)):
        note = score.notes[position]
        written_note = replace(
            note.source,
            channel=slot.channel,
            pitch=slot.pitch,
            start=int(timed.starts[number]),
            end=int(timed.ends[number]),
            velocity=int(held[number]),
            order=slot.order,
            off_order=timed.off_orders[number],
        )
        drum_notes.append(written_note)
        out.append(
            RenderedNote(
                position=position,
                section=slot.section,
                kept=slot.kept,
                part=parts[position],
                hit_type=note.hit_type,
                grace=note.grace_of is not None,
                family=slot.drum[0],
                piece=slot.drum[1],
                note=written_note,
                offset_ms=score.tempos.tick_to_ms(written_note.start)
                - score.tempos.tick_to_ms(note.tick),
                strong=bool(strong[position]),
            )
        )
    return Rendered(
        song=with_drums(song, score.track, drum_notes),
        notes=tuple(out),
        guards=tally.frozen(),
    )


def _after_orders(song: MidiSong, track: int) -> int:
    """An order after every message of the track's, for notes that take their place by play
    order."""
    orders = [note.off_order for note in song.notes if note.track == track]
    orders.extend(event.order for event in song.events if event.track == track)
    return max(orders, default=0) + 1
