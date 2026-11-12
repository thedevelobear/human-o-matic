"""The guards: the limits every backend's draws are held to (ADR 0050).

Timing, in turn:
1. Each offset is cut to `MAX_OFFSET_MS` either way.
2. A grace takes its main note's offset, so a main note and its graces move as one. A grace the
   score puts on its main's tick, as on the song's first tick, where it can't go before it, is
   placed before its main by the gap it was played at, from the source notes.
3. Across a section boundary, two notes in a row on one pitch each keep to their side of it: the
   earlier at most `BOUNDARY_SHARE` of their grid gap late, the later at most that early, so
   they keep `MIN_GAP_SHARE` of the gap whatever the other section draws. On one grid point,
   the later keeps a tick or more after it.
4. Each note goes to its nearest tick, and to tick 0 when it would be before it. When a grace
   would start before tick 0, its main note goes later with it, so the grace starts at tick 0
   and keeps its gap, up to the cap: past it, the gap is shortened, and `unmet` counts it. A
   main note and its graces keep their order, a tick or more apart.
5. In each pitch's play order, a note after another of its pitch in its own section, or after a
   note played as it came in, keeps `MIN_GAP_SHARE` of their grid gap and at least a tick, by
   moving later with its main note and graces. A note before one played as it came in keeps it
   by moving earlier, and so does a note before one at a boundary, so the gap never takes that
   one past its side: each side is carried back through the section's notes before it. The gap
   is counted in milliseconds through the tempo map, as the cap is, and a main note and its
   graces move by one shift in milliseconds, so they keep one offset. So between two notes of a
   section the gap never takes a note past the cap (ADR 0073). A grace the score puts on its
   main's tick takes its main with it as far as the cap: past it, the grace goes on alone, its
   gap to its main is shortened, and `unmet` counts it. When a note can't keep both gaps, the
   one from the note before wins, and `unmet` counts it. Next to a note played as it came in,
   the cap wins over the gap, so the note stops at the cap with less of its gap, a tick or more
   from the kept note, and `unmet` counts it, not `gap`.
6. A note a controller value decides or shapes stays within its window, between the controller
   events around its source note (ADR 0053), which wins over the gap.
7. Each note keeps its source length, at least a tick, and ends by the time the next note of its
   pitch starts, or by the earliest that note could start when it is in another section.

Velocity, in turn:
1. A draw above 127 is reflected below it, and one below the note's floor above it.
2. It is rounded, and moved into its articulation's velocity range.
3. Per section and drum with soft-typed notes, they are held at least 2 below the lowest other
   note, and the others no lower than 1 below it, so soft notes stay below them.
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
from heapq import heapify, heappop, heappush
from itertools import pairwise
from math import ceil, floor

import numpy as np
from pydantic import BaseModel, ConfigDict

from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import FloatArray, IntArray, TempoMap

MAX_VELOCITY = 127.0
"""The ceiling a draw above is reflected below (Appendix A)."""
MAX_OFFSET_MS = 12.0
"""The cap on an offset from the grid, either way (Appendix A)."""
MIN_GAP_SHARE = 0.6
"""The share of its grid gap a note keeps from the note before it on its pitch, in milliseconds
(Appendix A)."""
BOUNDARY_SHARE = (1 - MIN_GAP_SHARE) / 2
"""How far into their grid gap each of two notes on one pitch across a boundary may move."""
MAX_NUDGE = 16
"""How far a velocity is searched either way for one that fits."""
_FAR = 2**62
"""Further than any shift, for a side a note is free on."""
_ROUNDING = 1e-6
"""How far, in ticks, a tick worked out through milliseconds may be off a whole tick by float
rounding and still be taken as it. At one tempo, ticks and milliseconds are in proportion, so
the gap is the same whole number of ticks it would be counted in ticks."""

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
    """Notes that would start before tick 0, moved to it, or later with their graces."""
    gap: int = 0
    """Notes moved, later after a note of their pitch, or earlier before a kept one or one at a
    boundary, to keep their gap or side. A note that can't keep both gaps keeps the one from the
    note before, and counts here and under `unmet`. One the cap stops short of a kept note's gap
    counts only under `unmet`."""
    controller: int = 0
    """Notes their controller window moved, which wins over the gap."""
    range: int = 0
    """Velocities moved into their articulation's range."""
    soft: int = 0
    """Soft notes moved below the other notes of their drum."""
    nudged: int = 0
    """Velocities moved off a repeat, or onto their class at a boundary."""
    unmet: int = 0
    """Notes a guard couldn't hold, as when a range is too narrow for it, both gaps can't be
    kept, the cap keeps a note short of a kept note's gap, or a main note short of its grace's
    gap, on tick 0 or behind a note on its grace's grid point. Each is also counted under the
    guard that moved it, if one did, but for the cap."""


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
    places = _places(slots, grid_ms, tempos)
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
    previous = _previous(slots, unit_of)
    side_low, side_high = _sides(slots, places, grid_ms, previous, tempos)
    lowest = np.full(count, -MAX_OFFSET_MS)
    for unit, held in members.items():
        if slots[unit].kept:
            continue
        floor, ceiling = max(low[held].max(), -MAX_OFFSET_MS), min(high[held].min(), MAX_OFFSET_MS)
        if floor > ceiling:
            tally.add("unmet")
            floor = ceiling = (floor + ceiling) / 2
        offset = min(max(float(offsets[unit]), floor), ceiling)
        drawn = np.rint(tempos.ms_to_ticks(places[held] + offset))
        tally.add("tick_zero", int(np.count_nonzero(drawn < 0)))
        zero = -float(places[held].min())
        """The offset that starts the unit's first note at tick 0."""
        if offset < zero:
            if zero > ceiling:
                tally.add("unmet")
            offset = max(offset, min(zero, ceiling))
        offsets[held] = offset
        lowest[held] = floor

    starts = np.rint(tempos.ms_to_ticks(places + offsets)).astype(np.int64)
    for position, slot in enumerate(slots):
        if slot.kept:
            starts[position] = slot.source.start
    for unit, held in members.items():
        if not slots[unit].kept:
            _keep_order(starts, held, places)
    earliest = np.maximum(np.floor(tempos.ms_to_ticks(places + lowest)), 0).astype(np.int64)

    kept_after = {
        earlier: later
        for sequence in _sequences([slot.key for slot in slots])
        for earlier, later in pairwise(sequence)
        if slots[later].kept and not slots[earlier].kept
    }
    """For each rendered note followed on its pitch by a note played as it came in, that note."""
    cap_low = np.ceil(tempos.ms_to_ticks(grid_ms - MAX_OFFSET_MS)).astype(np.int64)
    cap_high = np.floor(tempos.ms_to_ticks(grid_ms + MAX_OFFSET_MS)).astype(np.int64)
    """The earliest and latest ticks within the cap, for the gap to a kept note."""
    at_cap = np.rint(tempos.ms_to_ticks(grid_ms + MAX_OFFSET_MS)).astype(np.int64)
    """The tick a note drawn at the cap late goes to."""
    on_main = {
        position
        for position, slot in enumerate(slots)
        if slot.main is not None and slot.tick >= slots[slot.main].tick
    }
    """The graces the score puts on their main's tick, placed before it by their source gap."""

    # Each note moves by one shift with its main note and graces, in milliseconds, so they keep
    # their offset across a tempo change (ADR 0073). The shift is counted in the ticks of the note
    # of theirs with the shortest tick, and what bounds it wins in this order: the controller
    # window; then a tick after a kept note before it and a tick before a kept note after it, so
    # notes never reorder; then the cap, over the gap to a kept note; then the gap from the note
    # before, and the note's side of a boundary from the note before, over the gap to a kept note
    # after and its side of a boundary to the note after. Each unit is taken after the notes before
    # its own on their pitches, so a gap is counted from where that note ends up. A grace the score
    # puts on its main's tick takes its main later with it to keep its gap from the note before,
    # up to the cap: past it, the grace goes on alone, and its gap to its main is shortened.
    for unit in _unit_order(slots, members, unit_of, previous):
        held = members[unit]
        if not slots[unit].kept:
            counted = _counted_in(tempos, starts, held, unit)
            base = int(starts[counted])
            before_low = -_FAR
            """The shift that keeps the gap from the note before in the note's section, or the
            note's side of a boundary from the note before."""
            side_high_shift = _FAR
            """The shift that keeps the note's side of a boundary to the note after."""
            kept_low, kept_high = -_FAR, _FAR
            """The shifts that keep the gap from a kept note before and to a kept note after."""
            order_low, order_high = -_FAR, _FAR
            """The shifts that keep a tick from a kept note either side."""
            capped_low, capped_high = -_FAR, _FAR
            """The shifts that keep the notes within the cap."""
            held_low, held_high = -_FAR, _FAR
            """The shifts that keep the notes within their controller windows."""
            lifted_low = -_FAR
            """The shift that keeps the gap from the note before for a grace on its main's
            tick, which its main goes with as far as the cap and the bounds after allow."""
            alone: dict[int, int] = {}
            """For each grace on its main's tick, the tick that keeps its gap from the note
            before."""
            for member in held:
                slot = slots[member]
                here = int(starts[member])
                capped_low = max(capped_low, _shift_to(tempos, int(cap_low[member]), here, base))
                capped_high = min(
                    capped_high, _shift_to(tempos, int(cap_high[member]), here, base, upper=True)
                )
                if side_low[member] > -_FAR:
                    before_low = max(
                        before_low, _shift_to(tempos, int(side_low[member]), here, base)
                    )
                if side_high[member] < _FAR:
                    side_high_shift = min(
                        side_high_shift,
                        _shift_to(tempos, int(side_high[member]), here, base, upper=True),
                    )
                before = previous[member]
                if before is not None and (
                    slots[before].kept or slots[before].section == slot.section
                ):
                    gap = MIN_GAP_SHARE * float(grid_ms[member] - grid_ms[before])
                    first = _first_after(tempos, int(starts[before]), gap)
                    least = _shift_to(tempos, first, here, base)
                    if slots[before].kept:
                        kept_low = max(kept_low, least)
                        order_low = max(
                            order_low, _shift_to(tempos, int(starts[before]) + 1, here, base)
                        )
                    elif member in on_main:
                        alone[member] = first
                        lifted_low = max(lifted_low, least)
                    else:
                        before_low = max(before_low, least)
                after = kept_after.get(member)
                if after is not None:
                    gap = MIN_GAP_SHARE * float(grid_ms[after] - grid_ms[member])
                    most = _last_before(tempos, int(starts[after]), gap)
                    kept_high = min(kept_high, _shift_to(tempos, most, here, base, upper=True))
                    order_high = min(
                        order_high,
                        _shift_to(tempos, int(starts[after]) - 1, here, base, upper=True),
                    )
                if slot.window is not None:
                    held_low = max(held_low, _shift_to(tempos, slot.window[0], here, base))
                    held_high = min(
                        held_high, _shift_to(tempos, slot.window[1], here, base, upper=True)
                    )
            short = kept_low > capped_high or kept_high < capped_low
            kept_low = max(min(kept_low, capped_high), order_low)
            kept_high = min(max(kept_high, capped_low), order_high)
            gap_low, gap_high = max(before_low, kept_low), min(kept_high, side_high_shift)
            if lifted_low > -_FAR:
                ceiling = _shift_to(tempos, int(at_cap[unit]), int(starts[unit]), base, upper=True)
                gap_low = max(gap_low, min(lifted_low, ceiling, gap_high))
            unmet = short
            if gap_low > gap_high:
                unmet = True
                gapped = gap_low
            else:
                gapped = min(max(0, gap_low), gap_high)
            shift = min(max(gapped, held_low), held_high)
            if shift != gapped:
                tally.add("controller")
                if gap_low <= gap_high and not gap_low <= shift <= gap_high:
                    unmet = True
            elif shift and not short:
                tally.add("gap")
            if shift:
                moved = tempos.tick_to_ms(base + shift) - tempos.tick_to_ms(base)
                for member in held:
                    here = int(starts[member])
                    starts[member] = (
                        base + shift
                        if member == counted
                        else round(tempos.ms_to_tick(tempos.tick_to_ms(here) + moved))
                    )
                if len(held) > 1:
                    _keep_order(starts, held, places)
            short_of = [member for member, first in alone.items() if starts[member] < first]
            if short_of:
                for member in short_of:
                    starts[member] = alone[member]
                _keep_order(starts, held, places)
                unmet = True
                if not shift:
                    tally.add("gap")
            if unmet:
                tally.add("unmet")

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


def _places(slots: Sequence[Slot], grid_ms: FloatArray, tempos: TempoMap) -> FloatArray:
    """Where each note sits before its offset, in milliseconds: its grid point, or for a grace
    the score puts on its main's tick, as on the song's first tick, its main's less the gap it
    was played at."""
    places = grid_ms.copy()
    for position, slot in enumerate(slots):
        if slot.main is not None and slot.tick >= slots[slot.main].tick:
            main = slots[slot.main]
            gap = tempos.tick_to_ms(main.source.start) - tempos.tick_to_ms(slot.source.start)
            places[position] = grid_ms[slot.main] - gap
    return places


def _previous(slots: Sequence[Slot], unit_of: Sequence[int]) -> list[int | None]:
    """For each note, the note before it in play order on its pitch, passing over its own main
    note and graces, which keep their order apart."""
    previous: list[int | None] = [None] * len(slots)
    for sequence in _sequences([slot.key for slot in slots]):
        for prior, position in pairwise(sequence):
            previous[position] = previous[prior] if unit_of[prior] == unit_of[position] else prior
    return previous


def _sides(
    slots: Sequence[Slot],
    places: FloatArray,
    grid_ms: FloatArray,
    previous: Sequence[int | None],
    tempos: TempoMap,
) -> tuple[IntArray, IntArray]:
    """The earliest and latest tick of each note at a boundary, from the score alone, that the gap
    from the note before can't move it past: its side of its grid gap to the note of another
    section on its pitch, rounded to a tick, and on one grid point the later a tick or more after
    the earlier. A latest tick is carried back through the notes before it in its section, each
    by the gap it keeps to the next."""
    count = len(slots)
    late, early = np.zeros(count), np.zeros(count)
    """How far late each note may go before the next on its pitch, and how far early after the
    one before, in milliseconds, at a boundary."""
    pairs: list[tuple[int, int]] = []
    for sequence in _sequences([slot.key for slot in slots]):
        for earlier, later in pairwise(sequence):
            a, b = slots[earlier], slots[later]
            if a.kept or b.kept or a.section == b.section:
                continue
            gap = float(grid_ms[later] - grid_ms[earlier])
            pairs.append((earlier, later))
            late[earlier], early[later] = BOUNDARY_SHARE * gap, -BOUNDARY_SHARE * gap
    latest = np.rint(tempos.ms_to_ticks(places + late)).astype(np.int64)
    earliest = np.rint(tempos.ms_to_ticks(places + early)).astype(np.int64)
    side_low = np.full(count, -_FAR, dtype=np.int64)
    side_high = np.full(count, _FAR, dtype=np.int64)
    for earlier, later in pairs:
        side_high[earlier] = latest[earlier]
        side_low[later] = max(int(earliest[later]), int(latest[earlier]) + 1)
    for position in reversed(range(count)):
        before = previous[position]
        if side_high[position] == _FAR or before is None:
            continue
        if slots[before].kept or slots[before].section != slots[position].section:
            continue
        gap = MIN_GAP_SHARE * float(grid_ms[position] - grid_ms[before])
        side_high[before] = min(
            int(side_high[before]), _last_before(tempos, int(side_high[position]), gap)
        )
    return side_low, side_high


def _unit_order(
    slots: Sequence[Slot],
    members: dict[int, list[int]],
    unit_of: Sequence[int],
    previous: Sequence[int | None],
) -> list[int]:
    """The units in the order the gap is held in: each after the units of the notes before its
    own on their pitches, and otherwise by its first tick. Two notes of one pitch on one grid
    point, the later with a grace, so keep their play order. Should the notes before ever loop
    back, the first unit by tick left goes next."""

    def key(unit: int) -> tuple[int, int]:
        return min(slots[member].tick for member in members[unit]), unit

    waiting: dict[int, int] = {}
    unblocks: dict[int, list[int]] = {unit: [] for unit in members}
    for unit, held in members.items():
        needs = {unit_of[before] for member in held if (before := previous[member]) is not None}
        needs.discard(unit)
        waiting[unit] = len(needs)
        for need in needs:
            unblocks[need].append(unit)
    ready = [key(unit) for unit, count in waiting.items() if not count]
    heapify(ready)
    order: list[int] = []
    done: set[int] = set()
    while len(order) < len(members):
        if ready:
            _, unit = heappop(ready)
            if unit in done:
                continue
        else:
            unit = min((left for left in members if left not in done), key=key)
        order.append(unit)
        done.add(unit)
        for after in unblocks[unit]:
            waiting[after] -= 1
            if not waiting[after] and after not in done:
                heappush(ready, key(after))
    return order


def _keep_order(starts: IntArray, held: Sequence[int], places: FloatArray) -> None:
    """Holds a main note and its graces in the order of their places, a tick or more apart, and
    from tick 0."""
    least = 0
    for member in sorted(held, key=lambda member: (float(places[member]), member)):
        starts[member] = max(int(starts[member]), least)
        least = int(starts[member]) + 1


def _counted_in(tempos: TempoMap, starts: IntArray, held: Sequence[int], main: int) -> int:
    """The note of a unit its shift is counted in: the one whose tick is shortest where it is, so
    no note of the unit moves further than it must, and the main note on a tie."""
    counted = main
    for member in held:
        if tempos.ms_per_tick(int(starts[member])) < tempos.ms_per_tick(int(starts[counted])):
            counted = member
    return counted


def _shift_to(tempos: TempoMap, tick: int, here: int, base: int, *, upper: bool = False) -> int:
    """The shift, in the ticks of the unit's note on `base`, that takes a note of the unit from
    `here` to `tick` when the unit moves by one shift in milliseconds: the least that reaches it,
    or with `upper` the most that stays at or before it. At one tempo, it is `tick - here`."""
    if here == base:
        return tick - here
    distance = tempos.tick_to_ms(tick) - tempos.tick_to_ms(here)
    at = tempos.ms_to_tick(tempos.tick_to_ms(base) + distance)
    return (floor(at + _ROUNDING) if upper else ceil(at - _ROUNDING)) - base


def _first_after(tempos: TempoMap, tick: int, gap_ms: float) -> int:
    """The first tick `gap_ms` or more after `tick`, and a tick or more after it."""
    at = tempos.ms_to_tick(tempos.tick_to_ms(tick) + gap_ms)
    return max(tick + 1, ceil(at - _ROUNDING))


def _last_before(tempos: TempoMap, tick: int, gap_ms: float) -> int:
    """The last tick `gap_ms` or more before `tick`, and a tick or more before it."""
    at = tempos.ms_to_tick(tempos.tick_to_ms(tick) - gap_ms)
    return min(tick - 1, floor(at + _ROUNDING))


def _earliest(slot: Slot, tick: int) -> int:
    """The earliest a note of another section could start."""
    return min(tick, slot.window[0]) if slot.window is not None else tick


def reflect(values: FloatArray, floors: FloatArray, ceiling: float = MAX_VELOCITY) -> FloatArray:
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

    softened = {(slot.section, slot.drum) for slot in slots if not slot.kept and slot.soft}
    """The sections' drums that have soft notes, where the others are held above them."""
    lowest: dict[tuple[int, Drum], int] = {}
    for position, slot in enumerate(slots):
        place = (slot.section, slot.drum)
        if not slot.kept and not slot.soft and place in softened:
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
