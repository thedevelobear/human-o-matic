"""Rendering a score: each section drawn from its own stream, the song's drifts, the guards, and
the drum track written back with the rendered notes (ADRs 0048 to 0050).

Randomness comes only from `numpy.random.Generator`s built from a `SeedSequence` of the plan's
seed (ADR 0049). Each section draws from its own stream, keyed by its first bar and its take, so
rendering one section again leaves the others' draws as they were. The song's slow drifts in
timing and velocity have streams of their own, drawn once at every tick of the score, so they
change only with the seed. The same song, answers, plan and seed always give the same file.

A creative section (ADR 0091) asks its instrument for notes to add after its own draw, with a
stream of its own keyed like its section's, which picks what to add and draws the added notes'
velocities and offsets with the section's parameters (ADR 0093). The song's drifts reach them at
their ticks, read between the score's ticks. Only what changes no other section is added
(`render/creative.py`, ADR 0094), so with creative mode off nothing is drawn or added, and a
section turned creative leaves every other section's notes as they were.
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
from human_o_matic.midi.io import DEFAULT_RELEASE, MidiSong, Note
from human_o_matic.midi.tempo import FloatArray
from human_o_matic.normalize.hit_types import HitType
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.backends.parametric import sample
from human_o_matic.render.compiler import Params
from human_o_matic.render.controllers import windows
from human_o_matic.render.creative import (
    Addition,
    Admitted,
    Candidate,
    CreativeReport,
    Neighbours,
    SectionView,
    admit,
)
from human_o_matic.render.guards import GuardCounts, Slot, Tally, hold_timing, hold_velocity
from human_o_matic.render.output import with_drums
from human_o_matic.render.parts import Part, play_key
from human_o_matic.render.style import built_in_styles
from human_o_matic.render.target import Placement

STREAM_DRIFT = 0
STREAM_SECTION = 1
STREAM_CREATIVE = 2
DRIFT_TIMING = 0
DRIFT_ENERGY = 1


def section_stream(seed: int, start: int, take: int) -> np.random.Generator:
    """The stream of the section whose first bar is `start`, for one take."""
    return np.random.default_rng(
        np.random.SeedSequence(seed, spawn_key=(STREAM_SECTION, start, take))
    )


def creative_stream(seed: int, start: int, take: int) -> np.random.Generator:
    """The stream a creative section's additions draw from: what it adds and how they play
    (ADR 0093). It is spawned beside the section's own, so drawing from it moves no other
    stream."""
    return np.random.default_rng(
        np.random.SeedSequence(seed, spawn_key=(STREAM_CREATIVE, start, take))
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
    """Its position in `Score.notes`, or for a note a creative section added, past them, in the
    order the sections added them."""
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
    tick: int
    """Its grid point: the score's tick, or the tick a creative section added it on."""
    added: Addition | None = None
    """What a creative section made of it: a note it added, or `rimshot` for a note of its own it
    wrote as one."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Rendered:
    song: MidiSong
    notes: tuple[RenderedNote, ...]
    """In play order (`play_key`), without the notes left out."""
    guards: GuardCounts
    creative: tuple[CreativeReport | None, ...] = ()
    """For each section, what creative mode added and couldn't, or None when it is off."""


@dataclass(frozen=True, slots=True, kw_only=True)
class _Added:
    """A note a creative section added, as drawn."""

    section: int
    candidate: Candidate
    end_by: int | None
    velocity: float
    floor: float
    offset_ms: float


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
    style = built_in_styles()[plan.style]
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
    creative: list[tuple[int, Params, dict[int, float]]] = []
    """Each creative section's number, parameters and onsets' shared values."""
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
        params = instrument.compile(controls, style, score.tempos.bpm(first))
        draw = sample(
            notes,
            [parts[position] for position in members],
            [min(max((note.tick - first) / length, 0.0), 1.0) for note in notes],
            params,
            section_stream(plan.seed, section.start, section.take),
        )
        for index, position in enumerate(members):
            tick = at[score.notes[position].tick]
            velocities[position] = draw.velocities[index] + energy[tick]
            floors[position] = draw.floors[index]
            offsets[position] = draw.offsets_ms[index] + timing[tick]
            strong[position] = draw.strong[index]
        if controls.creative:
            creative.append((number, params, draw.shared))

    held_to = windows(song, score, placement)
    reports: list[CreativeReport | None] = [None] * len(plan.sections)
    added: list[_Added] = []
    rewritten: dict[int, Candidate] = {}
    if creative:
        around = Neighbours.build(
            score,
            placement,
            order,
            section_of,
            kept,
            held_to,
            [score.signatures.bar_start(section.start) for section in plan.sections],
        )
        for number, params, shared in creative:
            section = plan.sections[number]
            rng = creative_stream(plan.seed, section.start, section.take)
            view = SectionView(
                score=score,
                parts=parts,
                placement=placement,
                members=tuple(p for p in order if section_of[p] == number),
                start=section.start,
                end=section.end,
                leads_on=number + 1 < len(plan.sections)
                and any(section_of[p] == number + 1 for p in order),
            )
            admitted = admit(number, instrument.additions(view, rng), around)
            reports[number] = admitted.report
            rewritten.update(admitted.rewritten)
            added += _drawn(admitted, number, view, params, shared, rng, quarters, timing, energy)

    items = sorted(
        [((play_key(score.notes[position]), 0, position), position) for position in order]
        + [((_added_key(each.candidate), 1, index), -1 - index) for index, each in enumerate(added)]
    )
    """The notes in play order, a score note by its position and an added note by -1 less its
    index in `added`."""
    slot_of = {item: number for number, (_, item) in enumerate(items)}
    played_at = {position: number for number, position in enumerate(order)}
    """Each score note's place in play order, from which a rendered note takes its order."""
    by_source = {note.source_index: position for position, note in enumerate(score.notes)}
    base = _after_orders(song, score.track)
    later = base + count
    """The order of every added note: after all the others, so it moves none of theirs."""
    slots: list[Slot] = []
    item_offsets: list[float] = []
    item_velocities: list[float] = []
    item_floors: list[float] = []
    for _, item in items:
        if item < 0:
            each = added[-1 - item]
            candidate = each.candidate
            placed = candidate.placed
            grace = candidate.grace_of
            slots.append(
                Slot(
                    section=each.section,
                    kept=False,
                    source=Note(
                        track=score.track,
                        channel=placed.channel,
                        pitch=placed.pitch,
                        start=candidate.tick,
                        end=candidate.tick + candidate.length,
                        velocity=1,
                        release=DEFAULT_RELEASE,
                        order=later,
                        off_order=later,
                    ),
                    tick=candidate.tick,
                    main=slot_of[by_source[grace]] if grace is not None else None,
                    channel=placed.channel,
                    pitch=placed.pitch,
                    drum=(placed.family, placed.piece),
                    soft=candidate.hit_type == "soft",
                    velocity=placed.velocity,
                    order=later,
                    off_order=later,
                    added=True,
                    end_by=each.end_by,
                )
            )
            item_offsets.append(each.offset_ms)
            item_velocities.append(each.velocity)
            item_floors.append(each.floor)
            continue
        position = item
        note = score.notes[position]
        placed = placement.notes[position]
        if placed is None:
            raise ValueError("a note left out was taken to be written")
        was = None
        if position in rewritten:
            was = (placed.channel, placed.pitch)
            placed = rewritten[position].placed
        main = slot_of.get(by_source[note.grace_of]) if note.grace_of is not None else None
        # A note played as it came in, or one held to its controller events, keeps its order
        # among the drum track's messages. Any other takes its place in play order, after them.
        own = kept[position] or placed.controllers is not None
        played = None if own else base + played_at[position]
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
                order=note.source.order if played is None else played,
                off_order=note.source.off_order if played is None else played,
                window=held_to[position],
                was=was,
            )
        )
        item_offsets.append(float(offsets[position]))
        item_velocities.append(float(velocities[position]))
        item_floors.append(float(floors[position]))
    tally = Tally()
    timed = hold_timing(slots, np.array(item_offsets), score.tempos, tally)
    held = hold_velocity(slots, np.array(item_velocities), np.array(item_floors), tally)

    out: list[RenderedNote] = []
    drum_notes: list[Note] = []
    for number, ((_, item), slot) in enumerate(zip(items, slots, strict=True)):
        written_note = replace(
            slot.source,
            channel=slot.channel,
            pitch=slot.pitch,
            start=int(timed.starts[number]),
            end=int(timed.ends[number]),
            velocity=int(held[number]),
            order=slot.order,
            off_order=timed.off_orders[number],
        )
        drum_notes.append(written_note)
        offset = score.tempos.tick_to_ms(written_note.start) - score.tempos.tick_to_ms(slot.tick)
        if item < 0:
            candidate = added[-1 - item].candidate
            out.append(
                RenderedNote(
                    position=count - 1 - item,
                    section=slot.section,
                    kept=False,
                    part=candidate.part,
                    hit_type=candidate.hit_type,
                    grace=candidate.grace_of is not None,
                    family=slot.drum[0],
                    piece=slot.drum[1],
                    note=written_note,
                    offset_ms=offset,
                    strong=False,
                    tick=candidate.tick,
                    added=candidate.kind,
                )
            )
            continue
        note = score.notes[item]
        out.append(
            RenderedNote(
                position=item,
                section=slot.section,
                kept=slot.kept,
                part=parts[item],
                hit_type=note.hit_type,
                grace=note.grace_of is not None,
                family=slot.drum[0],
                piece=slot.drum[1],
                note=written_note,
                offset_ms=offset,
                strong=bool(strong[item]),
                tick=note.tick,
                added="rimshot" if item in rewritten else None,
            )
        )
    return Rendered(
        song=with_drums(song, score.track, drum_notes),
        notes=tuple(out),
        guards=tally.frozen(),
        creative=tuple(reports),
    )


def _added_key(candidate: Candidate) -> tuple[int, str, int, str, int, int]:
    """Where an added note goes in play order, as `play_key` orders the score's notes."""
    placed = candidate.placed
    return (
        candidate.tick,
        placed.family,
        placed.piece,
        placed.articulation,
        placed.channel,
        placed.pitch,
    )


def _drawn(
    admitted: Admitted,
    number: int,
    view: SectionView,
    params: Params,
    shared: dict[int, float],
    rng: np.random.Generator,
    quarters: FloatArray,
    timing: FloatArray,
    energy: FloatArray,
) -> list[_Added]:
    """A creative section's added notes, drawn in play order from its stream with its parameters,
    each onset it already plays keeping that onset's shared offset, and the song's drifts read at
    their ticks between the score's."""
    chosen = sorted(admitted.added, key=lambda each: _added_key(each[0]))
    if not chosen:
        return []
    first, end = view.first_tick, view.end_tick
    length = max(end - first, 1)
    candidates = [candidate for candidate, _ in chosen]
    draw = sample(
        candidates,
        [candidate.part for candidate in candidates],
        [min(max((candidate.tick - first) / length, 0.0), 1.0) for candidate in candidates],
        params,
        rng,
        shared=shared,
    )
    ppq = view.score.ppq
    out: list[_Added] = []
    for index, (candidate, end_by) in enumerate(chosen):
        at = candidate.tick / ppq
        out.append(
            _Added(
                section=number,
                candidate=candidate,
                end_by=end_by,
                velocity=float(draw.velocities[index]) + float(np.interp(at, quarters, energy)),
                floor=float(draw.floors[index]),
                offset_ms=float(draw.offsets_ms[index]) + float(np.interp(at, quarters, timing)),
            )
        )
    return out


def _after_orders(song: MidiSong, track: int) -> int:
    """An order after every message of the track's, for notes that take their place by play
    order."""
    orders = [note.off_order for note in song.notes if note.track == track]
    orders.extend(event.order for event in song.events if event.track == track)
    return max(orders, default=0) + 1
