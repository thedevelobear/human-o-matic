"""The guards: the limits every backend's draws are held to (ADR 0050).

Timing, in turn:
1. Each offset is cut to `MAX_OFFSET_MS` either way.
2. A grace takes its main note's offset, so a main note and its graces move as one.
3. Across a section boundary, two notes in a row on one pitch each keep to their side of it: the
   earlier at most `BOUNDARY_SHARE` of their grid gap late, the later at most that early, so
   they keep `MIN_GAP_SHARE` of the gap whatever the other section draws.
4. Each note goes to its nearest tick, and to tick 0 when it would be before it.
5. In time order, a note after another of its pitch in its own section, or after a note played as
   it came in, keeps `MIN_GAP_SHARE` of their grid gap and at least a tick, by moving later with
   its main note and graces. A note before one played as it came in keeps it by moving no later.
6. A note a controller value decides or shapes stays within its window, between the controller
   events around its source note (ADR 0053), which wins over the gap.
7. Each note keeps its source length, at least a tick, and ends by the time the next note of its
   pitch starts, or by the earliest that note could start when it is in another section.

Velocity, in turn:
1. A draw above 127 is reflected below it, and one below the note's floor above it.
2. It is rounded, and moved into its articulation's velocity range.
3. Per section and drum, soft-typed notes are held at least 2 below the lowest other note, and
   the others no lower than 1 below it, so soft notes stay below them.
4. In play order, no note takes the velocity of the note before it on its pitch, or before it
   on its drum, when that note is in its section or played as it came in, nor that of a note
   after it played as it came in. A note next to a note of another rendered section, on its
   pitch or its drum, takes a velocity of a class instead: modulo 4, the bit worth 2 is its
   place among its pitch's notes modulo 2, and the bit worth 1 its place among its drum's, so
   the two never match whatever the other section draws. The nudge is to the nearest velocity
   that fits, +1 before -1.
A velocity range too narrow for a rule wins over it, and the count says so.

Notes played as they came in (`skip`) keep their ticks, lengths and velocities, the velocity
moved into the target's range, and the guards work around them.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from math import ceil

import numpy as np
from pydantic import BaseModel, ConfigDict

from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import FloatArray, IntArray, TempoMap

MAX_OFFSET_MS = 12.0
"""The cap on an offset from the grid, either way (Appendix A)."""
MIN_GAP_SHARE = 0.6
"""The share of its grid gap a note keeps from the note before it on its pitch (Appendix A)."""
BOUNDARY_SHARE = (1 - MIN_GAP_SHARE) / 2
"""How far into their grid gap each of two notes on one pitch across a boundary may move."""
MAX_NUDGE = 16
"""How far a velocity is searched either way for one that fits."""

type Drum = tuple[str, int]
type Key = tuple[int, int]
"""A channel and a pitch."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Slot:
    """One note going through the guards, in play order (`render/parts.py`)."""

    section: int
    kept: bool
    """Played as it came in."""
    source: Note
    tick: int
    """Its grid point, the score's tick."""
    main: int | None
    """For a grace, the position of its main note among the slots."""
    channel: int
    pitch: int
    drum: Drum
    """The family and piece it is written as."""
    soft: bool
    velocity: tuple[int, int]
    """The velocities its articulation takes."""
    order: int
    """Its note-on's order among the track's messages at one tick (`midi/io.py`)."""
    off_order: int
    window: tuple[int, int] | None = None
    """For a note a controller value decides or shapes, the earliest and latest tick its note-on
    may take."""

    @property
    def key(self) -> Key:
        return self.channel, self.pitch


class GuardCounts(BaseModel):
    """How many notes each guard moved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capped: int = 0
    """Offsets cut to the cap."""
    tick_zero: int = 0
    """Notes moved to tick 0 from before it."""
    gap: int = 0
    """Notes moved later to keep their gap from the note before them on their pitch."""
    controller: int = 0
    """Notes held to the controller value set for them."""
    range: int = 0
    """Velocities moved into their articulation's range."""
    soft: int = 0
    """Soft notes moved below the other notes of their drum."""
    nudged: int = 0
    """Velocities moved off a repeat, or onto their class at a boundary."""
    unmet: int = 0
    """Notes a guard couldn't hold, as when a range is too narrow for it."""


@dataclass(slots=True)
class Tally:
    """The counts, as the guards add to them."""

    counts: dict[str, int] = field(default_factory=dict[str, int])

    def add(self, name: str, count: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + count

    def frozen(self) -> GuardCounts:
        return GuardCounts.model_validate(self.counts)


@dataclass(frozen=True, slots=True, kw_only=True)
class Timed:
    starts: IntArray
    ends: IntArray
    off_orders: tuple[int, ...]
    """Each note-off's order, lower than the next note-on's of its pitch where they meet."""


def _sequences(keys: Sequence[object]) -> Iterator[list[int]]:
    """The positions of each key's slots, in order."""
    found: dict[object, list[int]] = {}
    for position, key in enumerate(keys):
        found.setdefault(key, []).append(position)
    yield from found.values()


def hold_timing(
    slots: Sequence[Slot], offsets_ms: FloatArray, tempos: TempoMap, tally: Tally
) -> Timed:
    """The ticks and ends of the slots, from each note's offset from its grid point."""
    count = len(slots)
    grid_ms = tempos.ticks_to_ms(np.array([slot.tick for slot in slots], dtype=np.int64))
    rendered = np.array([not slot.kept for slot in slots], dtype=np.bool_)
    mains = np.array([slot.main is None for slot in slots], dtype=np.bool_)
    offsets = np.asarray(offsets_ms, dtype=np.float64).copy()
    tally.add("capped", int(np.count_nonzero(rendered & mains & (np.abs(offsets) > MAX_OFFSET_MS))))
    offsets = np.clip(offsets, -MAX_OFFSET_MS, MAX_OFFSET_MS)

    low = np.full(count, -MAX_OFFSET_MS)
    high = np.full(count, MAX_OFFSET_MS)
    for sequence in _sequences([slot.key for slot in slots]):
        for earlier, later in pairwise(sequence):
            a, b = slots[earlier], slots[later]
            if a.kept or b.kept or a.section == b.section:
                continue
            gap = float(grid_ms[later] - grid_ms[earlier])
            high[earlier] = min(high[earlier], BOUNDARY_SHARE * gap)
            low[later] = max(low[later], -BOUNDARY_SHARE * gap)
    unit_of = [position if slot.main is None else slot.main for position, slot in enumerate(slots)]
    members: dict[int, list[int]] = {}
    for position, unit in enumerate(unit_of):
        members.setdefault(unit, []).append(position)
    lowest = np.full(count, -MAX_OFFSET_MS)
    for unit, held in members.items():
        if slots[unit].kept:
            continue
        floor, ceiling = max(low[held].max(), -MAX_OFFSET_MS), min(high[held].min(), MAX_OFFSET_MS)
        if floor > ceiling:
            tally.add("unmet")
            floor = ceiling = (floor + ceiling) / 2
        offsets[held] = min(max(float(offsets[unit]), floor), ceiling)
        lowest[held] = floor

    starts = np.rint(tempos.ms_to_ticks(grid_ms + offsets)).astype(np.int64)
    for position, slot in enumerate(slots):
        if slot.kept:
            starts[position] = slot.source.start
    before = rendered & (starts < 0)
    tally.add("tick_zero", int(np.count_nonzero(before)))
    starts[before] = 0
    earliest = np.maximum(np.floor(tempos.ms_to_ticks(grid_ms + lowest)), 0).astype(np.int64)

    latest = np.full(count, np.iinfo(np.int64).max, dtype=np.int64)
    """The latest tick each note may take before a note of its pitch played as it came in."""
    for sequence in _sequences([slot.key for slot in slots]):
        for earlier, later in pairwise(sequence):
            if slots[later].kept and not slots[earlier].kept:
                grid = slots[later].tick - slots[earlier].tick
                latest[earlier] = starts[later] - max(1, ceil(MIN_GAP_SHARE * grid))

    last: dict[Key, int] = {}
    order = sorted(members, key=lambda unit: (min(slots[m].tick for m in members[unit]), unit))
    for unit in order:
        held = members[unit]
        if not slots[unit].kept:
            need = 0
            least_shift, most_shift = -(2**62), 2**62
            bounded = False
            for member in held:
                slot = slots[member]
                previous = last.get(slot.key)
                if previous is not None and (
                    slots[previous].kept or slots[previous].section == slot.section
                ):
                    grid = slot.tick - slots[previous].tick
                    least = int(starts[previous]) + max(1, ceil(MIN_GAP_SHARE * grid))
                    need = max(need, least - int(starts[member]))
                most_shift = min(most_shift, int(latest[member] - starts[member]))
                if slot.window is not None:
                    bounded = True
                    least_shift = max(least_shift, slot.window[0] - int(starts[member]))
                    most_shift = min(most_shift, slot.window[1] - int(starts[member]))
            shift = need
            if shift > most_shift:
                tally.add("unmet")
                shift = most_shift
            if bounded and shift < least_shift:
                shift = least_shift
            if bounded and shift != need:
                tally.add("controller")
            elif need > 0:
                tally.add("gap")
            starts[held] += shift
        for member in held:
            last[slots[member].key] = member

    ends = np.zeros(count, dtype=np.int64)
    off_orders = [slot.off_order for slot in slots]
    for sequence in _sequences([slot.key for slot in slots]):
        for number, position in enumerate(sequence):
            slot = slots[position]
            if slot.kept:
                ends[position] = slot.source.end
                continue
            end = int(starts[position]) + max(slot.source.end - slot.source.start, 1)
            if number + 1 < len(sequence):
                after = sequence[number + 1]
                limit = (
                    int(starts[after])
                    if slots[after].kept or slots[after].section == slot.section
                    else _earliest(slots[after], int(earliest[after]))
                )
                if end >= limit:
                    end = limit
                    off_orders[position] = min(off_orders[position], slots[after].order)
            ends[position] = max(end, int(starts[position]) + 1)
    return Timed(starts=starts, ends=ends, off_orders=tuple(off_orders))


def _earliest(slot: Slot, tick: int) -> int:
    """The earliest a note of another section could start."""
    return min(tick, slot.window[0]) if slot.window is not None else tick


def reflect(values: FloatArray, floors: FloatArray, ceiling: float = 127.0) -> FloatArray:
    """Each value reflected back inside its floor and the ceiling."""
    out = np.asarray(values, dtype=np.float64).copy()
    for _ in range(4):
        out = np.where(out > ceiling, 2 * ceiling - out, out)
        out = np.where(out < floors, 2 * floors - out, out)
    return np.clip(out, floors, ceiling)


def _candidates(want: int, low: int, high: int) -> Iterator[int]:
    """Velocities from `want` outwards, +1 before -1, within `low` to `high`."""
    for step in range(MAX_NUDGE + 1):
        for value in (want + step, want - step) if step else (want,):
            if low <= value <= high:
                yield value


def hold_velocity(
    slots: Sequence[Slot], velocities: FloatArray, floors: FloatArray, tally: Tally
) -> IntArray:
    """The velocities of the slots, from each note's draw and its floor."""
    reflected = reflect(velocities, np.maximum(np.asarray(floors, dtype=np.float64), 1.0))
    out = np.rint(reflected).astype(np.int64)
    for position, slot in enumerate(slots):
        low, high = slot.velocity
        value = slot.source.velocity if slot.kept else int(out[position])
        moved = min(max(value, low), high)
        tally.add("range", int(moved != value))
        out[position] = moved

    lowest: dict[tuple[int, Drum], int] = {}
    for position, slot in enumerate(slots):
        if not slot.kept and not slot.soft:
            place = (slot.section, slot.drum)
            lowest[place] = min(lowest.get(place, 128), int(out[position]))
    bounds: list[tuple[int, int]] = []
    for position, slot in enumerate(slots):
        low, high = max(slot.velocity[0], 1), slot.velocity[1]
        least = lowest.get((slot.section, slot.drum))
        if not slot.kept and least is not None:
            if slot.soft:
                if out[position] > least - 2:
                    tally.add("soft")
                high = min(high, least - 2)
            else:
                low = max(low, least - 1)
        if low > high:
            tally.add("unmet")
            low, high = max(slot.velocity[0], 1), slot.velocity[1]
        out[position] = min(max(int(out[position]), low), high)
        bounds.append((low, high))

    pitch_bit = _boundary_bits(slots, [slot.key for slot in slots])
    drum_bit = _boundary_bits(slots, [slot.drum for slot in slots])
    kept_after = _kept_after(slots, [slot.key for slot in slots])
    kept_after.update(
        (position, kept_after.get(position, ()) + after)
        for position, after in _kept_after(slots, [slot.drum for slot in slots]).items()
    )
    previous_pitch: dict[Key, int] = {}
    previous_drum: dict[Drum, int] = {}
    for position, slot in enumerate(slots):
        if not slot.kept:
            avoid = {
                int(out[before])
                for before in (previous_pitch.get(slot.key), previous_drum.get(slot.drum))
                if before is not None
                and (slots[before].kept or slots[before].section == slot.section)
            }
            avoid.update(int(out[after]) for after in kept_after.get(position, ()))
            want = int(out[position])
            found = next(
                (
                    value
                    for value in _candidates(want, *bounds[position])
                    if value not in avoid
                    and _fits(value, pitch_bit.get(position), drum_bit.get(position))
                ),
                None,
            )
            if found is None:
                tally.add("unmet")
            elif found != want:
                tally.add("nudged")
                out[position] = found
        previous_pitch[slot.key] = position
        previous_drum[slot.drum] = position
    return out


def _boundary_bits(slots: Sequence[Slot], keys: Sequence[object]) -> dict[int, int]:
    """For each rendered note next to a rendered note of another section among the notes of
    its key, its place among them modulo 2."""
    bits: dict[int, int] = {}
    for sequence in _sequences(keys):
        for number, position in enumerate(sequence):
            slot = slots[position]
            if slot.kept:
                continue
            for neighbour in (number - 1, number + 1):
                if 0 <= neighbour < len(sequence):
                    other = slots[sequence[neighbour]]
                    if not other.kept and other.section != slot.section:
                        bits[position] = number % 2
    return bits


def _kept_after(slots: Sequence[Slot], keys: Sequence[object]) -> dict[int, tuple[int, ...]]:
    """For each rendered note followed among the notes of its key by one played as it came in,
    that note."""
    after: dict[int, tuple[int, ...]] = {}
    for sequence in _sequences(keys):
        for earlier, later in pairwise(sequence):
            if slots[later].kept and not slots[earlier].kept:
                after[earlier] = (later,)
    return after


def _fits(value: int, pitch_bit: int | None, drum_bit: int | None) -> bool:
    """Whether a velocity is of the class its boundary bits ask for."""
    return (pitch_bit is None or (value >> 1) & 1 == pitch_bit) and (
        drum_bit is None or value & 1 == drum_bit
    )
