"""The grid of each beat, chosen among four candidates by timing error and complexity.

A beat is the time signature's denominator note, as in the tempo module, so a quarter in 4/4 and
an eighth in 7/8. The candidates divide a quarter note into 4 (16th), 3 (8th triplet), 6 (16th
triplet) or 8 (32nd). One applies to a beat when it divides the beat into whole steps: all four
in a beat of a quarter or longer, the 16th, 16th triplet and 32nd in an eighth, and the 16th and
32nd in a sixteenth. A quarter is a point of every grid, and an 8th of every grid but the 8th
triplet, so a beat of them takes the 16th, the simplest. Each grid's points run from the beat's
start to its end, which is the next beat's start, and a beat cut short by a time signature
change keeps its points up to where it ends.

Each beat with notes is scored for each grid that applies: the sum over its onsets of the
distance in milliseconds from the onset to the grid's nearest point, at the local tempo, plus
the grid's penalty. The lowest score wins, and a tie goes to the simpler grid. The penalty
makes a complex grid save that many milliseconds of timing error before it is chosen, so jitter
alone doesn't turn 16ths into 32nds. A beat with one onset is scored the same way, and one with
none has no grid.

An onset belongs to the beat its point is in (ADR 0086). It is first scored in the beat it was
played in, and one put on that beat's end, the next beat's start, as an onset played just before
a beat is, or one whose time comes back from milliseconds a hair under the beat's first tick,
then belongs to the next beat, and both beats are scored again. That moves no point: the start is
a point of every grid, and with the onset gone the grid that put it there stays the best of the
beat it was played in, since its distance to the end is the most it adds to any grid.

A beat is ambiguous when another grid scores within `AMBIGUITY_MS` of the best and would put an
onset on a different tick, or when an onset is more than `FAR_MS` from its point on the best
grid. The best grid is still used, and the beat says it was a guess.

An answer can give any beat with notes its grid, ambiguous or not. One for a beat without notes,
or for a beat the song doesn't have, is an error.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

import numpy as np
import numpy.typing as npt

from human_o_matic.decisions import DecisionRequest
from human_o_matic.midi.tempo import TempoMap, TimeSignatureMap
from human_o_matic.normalize.answers import AnswerError

type Grid = Literal["16th", "8th_triplet", "16th_triplet", "32nd"]
type FloatArray = npt.NDArray[np.float64]
type IntArray = npt.NDArray[np.int64]

GRIDS: tuple[Grid, ...] = ("16th", "8th_triplet", "16th_triplet", "32nd")
"""The candidates, simplest first. A tie goes to the earlier one."""
DIVISIONS: Mapping[Grid, int] = {"16th": 4, "8th_triplet": 3, "16th_triplet": 6, "32nd": 8}
"""Steps per quarter note."""
PENALTY_MS: Mapping[Grid, float] = {
    "16th": 0.0,
    "8th_triplet": 6.0,
    "16th_triplet": 10.0,
    "32nd": 10.0,
}
"""The milliseconds of timing error, summed over a beat's onsets, that a grid must save over the
16th to be chosen, as a cost of its complexity."""
AMBIGUITY_MS = 6.0
"""A grid that scores within this of the best, and places an onset differently, makes the beat
ambiguous. It is the smallest penalty, so a choice that close is the penalty's call."""
FAR_MS = 20.0
"""An onset further than this from its point on the chosen grid makes the beat ambiguous."""
MAX_LISTED = 8
"""The message of an `ambiguous_bars` request names at most this many beats."""


@dataclass(frozen=True, slots=True)
class Beats:
    """Every beat from tick 0 until the bar after the last note, in order."""

    starts: IntArray
    ends: IntArray
    """The next beat's start, or the bar's end for its last beat."""
    bars: IntArray
    """The bar of each beat, counting from 0."""
    numbers: IntArray
    """Each beat's place in its bar, counting from 0."""
    denominators: IntArray
    """The time signature's denominator, which sets the beat's length and its candidates."""

    def __len__(self) -> int:
        return int(self.starts.size)


def beat_windows(signatures: TimeSignatureMap, end: int) -> Beats:
    """The beats of every bar that starts before `end`."""
    starts: list[int] = []
    bars: list[int] = []
    numbers: list[int] = []
    denominators: list[int] = []
    ends: list[int] = []
    lines = [int(line) for line in signatures.bar_starts(max(end, 1))]
    lines.append(signatures.bar_start(len(lines)))
    for bar, (start, stop) in enumerate(pairwise(lines)):
        signature = signatures.signature_at(start)
        length = 4 * signatures.ppq / signature.denominator
        beat_starts = [
            start + round(number * length)
            for number in range(signature.numerator)
            if start + round(number * length) < stop
        ]
        for number, beat_start in enumerate(beat_starts):
            starts.append(beat_start)
            ends.append(beat_starts[number + 1] if number + 1 < len(beat_starts) else stop)
            bars.append(bar)
            numbers.append(number)
            denominators.append(signature.denominator)
    return Beats(
        starts=np.array(starts, dtype=np.int64),
        ends=np.array(ends, dtype=np.int64),
        bars=np.array(bars, dtype=np.int64),
        numbers=np.array(numbers, dtype=np.int64),
        denominators=np.array(denominators, dtype=np.int64),
    )


def steps(grid: Grid, denominator: int) -> int | None:
    """How many steps of `grid` a beat of `denominator` notes holds, or None when the grid
    doesn't divide it into whole steps."""
    quarters_times_steps = DIVISIONS[grid] * 4
    if quarters_times_steps % denominator:
        return None
    return quarters_times_steps // denominator


def applies(grid: Grid, denominator: int) -> bool:
    """Whether `grid` is a candidate in a beat of `denominator` notes. In a beat shorter than a
    32nd, which no grid divides, the 32nd applies with the beat's start and end as its points."""
    if grid == "32nd" and all(steps(other, denominator) is None for other in GRIDS):
        return True
    return steps(grid, denominator) is not None


@dataclass(frozen=True, slots=True, kw_only=True)
class BeatGrid:
    """The grid chosen for one beat with notes, and how sure the choice is."""

    bar: int
    beat: int
    """The beat's place in its bar, counting from 0."""
    start: int
    end: int
    grid: Grid
    costs: tuple[float | None, ...]
    """Each grid's score in milliseconds, in the order of `GRIDS`, and None where it doesn't
    apply."""
    alternatives: tuple[Grid, ...]
    """Other grids that score within `AMBIGUITY_MS` of this one and place an onset differently."""
    largest_offset_ms: float
    """The furthest any onset is from its point on the chosen grid."""
    answered: bool = False
    """The grid was given in the answer to an earlier request, so it is not a guess."""

    @property
    def ambiguous(self) -> bool:
        return not self.answered and (bool(self.alternatives) or self.largest_offset_ms > FAR_MS)


@dataclass(frozen=True, slots=True, kw_only=True)
class Snapped:
    """Onsets placed on the grids of their beats."""

    beats: tuple[BeatGrid, ...]
    """The beats that have onsets, in order."""
    ticks: IntArray
    """Each onset's grid point."""
    beat_of: IntArray
    """Each onset's beat, as a position in `beats`."""


def snap(
    ticks: FloatArray,
    ms: FloatArray,
    beats: Beats,
    tempos: TempoMap,
    answers: Mapping[tuple[int, int], Grid] | None = None,
) -> Snapped:
    """Choose each beat's grid and put each onset on its nearest point.

    `ticks` and `ms` are the onsets' performed times, which may be fractional ticks. `answers`
    gives the grid of a beat by its bar and place in the bar, both from 0, which any beat with
    notes may take. Raises `AnswerError` for an answer to a beat with no notes or one the song
    doesn't have, and for a grid the beat can't have.
    """
    given = answers or {}
    played = np.searchsorted(beats.starts, ticks, side="right") - 1
    snapped = _snap_in(played, ticks, ms, beats, tempos, given)
    heard = np.searchsorted(beats.starts, snapped.ticks, side="right") - 1
    if not np.array_equal(heard, played):
        snapped = _snap_in(heard, ticks, ms, beats, tempos, given)
    _check_answered(given, beats, np.unique(heard))
    return snapped


def _snap_in(
    which: IntArray,
    ticks: FloatArray,
    ms: FloatArray,
    beats: Beats,
    tempos: TempoMap,
    given: Mapping[tuple[int, int], Grid],
) -> Snapped:
    """`snap` with each onset taken to belong to the beat `which` gives it. An onset before its
    beat's start goes to the start, whatever the grid."""
    used, beat_of = np.unique(which, return_inverse=True)
    starts = beats.starts[used].astype(np.float64)
    ends = beats.ends[used].astype(np.float64)
    denominators = beats.denominators[used]
    lengths = 4 * tempos.ppq / denominators.astype(np.float64)

    points = np.empty((len(GRIDS), ticks.size))
    errors = np.empty((len(GRIDS), ticks.size))
    costs = np.full((len(GRIDS), used.size), np.inf)
    for g, grid in enumerate(GRIDS):
        count = np.array(
            [steps(grid, int(d)) or (1 if applies(grid, int(d)) else 0) for d in denominators]
        )
        valid = count > 0
        # A grid that doesn't apply is measured as if it did, and its cost is set to infinity.
        step = (lengths / np.maximum(count, 1))[beat_of]
        start, end = starts[beat_of], ends[beat_of]
        low = np.minimum(np.maximum(start + np.floor((ticks - start) / step) * step, start), end)
        high = np.minimum(low + step, end)
        low_error = np.abs(ms - tempos.ticks_to_ms(low))
        high_error = np.abs(ms - tempos.ticks_to_ms(high))
        closer = high_error < low_error
        points[g] = np.where(closer, high, low)
        errors[g] = np.where(closer, high_error, low_error)
        summed = np.zeros(used.size)
        np.add.at(summed, beat_of, errors[g])
        costs[g] = np.where(valid, summed + PENALTY_MS[grid], np.inf)

    best = np.argmin(costs, axis=0)
    answered = np.zeros(used.size, dtype=bool)
    for position, beat in enumerate(used):
        key = (int(beats.bars[beat]), int(beats.numbers[beat]))
        if key in given:
            grid = given[key]
            if not applies(grid, int(beats.denominators[beat])):
                raise AnswerError(
                    "grids",
                    key,
                    f"bar {key[0] + 1}, beat {key[1] + 1}: a {grid} grid doesn't fit a beat of "
                    f"1/{beats.denominators[beat]}",
                )
            best[position] = GRIDS.index(grid)
            answered[position] = True

    rounded = np.rint(points).astype(np.int64)
    chosen = rounded[best[beat_of], np.arange(ticks.size)]
    chosen_errors = errors[best[beat_of], np.arange(ticks.size)]
    largest = np.zeros(used.size)
    np.maximum.at(largest, beat_of, chosen_errors)
    differs = rounded != chosen[np.newaxis, :]
    moved = np.zeros((len(GRIDS), used.size), dtype=bool)
    for g in range(len(GRIDS)):
        np.logical_or.at(moved[g], beat_of, differs[g])

    grids: list[BeatGrid] = []
    for position, beat in enumerate(used):
        top = costs[best[position], position]
        alternatives: tuple[Grid, ...] = tuple(
            GRIDS[g]
            for g in range(len(GRIDS))
            if g != best[position]
            and np.isfinite(costs[g, position])
            and costs[g, position] - top < AMBIGUITY_MS
            and moved[g, position]
        )
        grids.append(
            BeatGrid(
                bar=int(beats.bars[beat]),
                beat=int(beats.numbers[beat]),
                start=int(beats.starts[beat]),
                end=int(beats.ends[beat]),
                grid=GRIDS[int(best[position])],
                costs=tuple(
                    round(float(cost), 3) if np.isfinite(cost) else None
                    for cost in costs[:, position]
                ),
                alternatives=alternatives,
                largest_offset_ms=round(float(largest[position]), 3),
                answered=bool(answered[position]),
            )
        )
    return Snapped(beats=tuple(grids), ticks=chosen, beat_of=beat_of.astype(np.int64))


def no_grid(bar: int, beat: int) -> AnswerError:
    """The error for a grid given to a beat with no notes, counted from 0."""
    return AnswerError(
        "grids", (bar, beat), f"bar {bar + 1}, beat {beat + 1} has no notes, so it has no grid"
    )


def _check_answered(answers: Mapping[tuple[int, int], Grid], beats: Beats, used: IntArray) -> None:
    """Raises `AnswerError` for an answer to a beat without notes, the beats in `used`, or to
    one the song doesn't have."""
    with_notes = set(zip(beats.bars[used].tolist(), beats.numbers[used].tolist(), strict=True))
    last = int(beats.bars[used].max()) if used.size else -1
    for bar, beat in sorted(answers):
        if (bar, beat) in with_notes:
            continue
        where = f"bar {bar + 1}, beat {beat + 1}"
        count = int(np.count_nonzero(beats.bars == bar))
        if bar > last:
            raise AnswerError(
                "grids", (bar, beat), f"{where} is after the last bar with drums, bar {last + 1}"
            )
        if beat >= count:
            beats_in_bar = f"{count} beat{'' if count == 1 else 's'}"
            raise AnswerError(
                "grids", (bar, beat), f"{where} isn't in the song: bar {bar + 1} has {beats_in_bar}"
            )
        raise no_grid(bar, beat)


def ambiguous_request(beats: Sequence[BeatGrid]) -> DecisionRequest | None:
    """An `ambiguous_bars` request for the beats whose grid is a guess, or None when there are
    none. Bars and beats count from 0 in the details and from 1 in the message."""
    unclear = [beat for beat in beats if beat.ambiguous]
    if not unclear:
        return None
    bars: dict[int, list[BeatGrid]] = {}
    for beat in unclear:
        bars.setdefault(beat.bar, []).append(beat)
    listed = "; ".join(_describe(beat) for beat in unclear[:MAX_LISTED])
    if len(unclear) > MAX_LISTED:
        listed += f"; and {len(unclear) - MAX_LISTED} more"
    count = f"{len(bars)} bar{'s' if len(bars) > 1 else ''}"
    have = "have" if len(bars) > 1 else "has"
    return DecisionRequest(
        kind="ambiguous_bars",
        message=f"{count} {have} beats whose grid is unclear, so the best guess is used for "
        f"now ({listed}). Which grid is each of these beats on?",
        answer_with=("grids",),
        details={
            "bars": [
                {
                    "bar": bar,
                    "beats": [
                        {
                            "beat": beat.beat,
                            "grid": beat.grid,
                            "alternatives": list(beat.alternatives),
                            "largest_offset_ms": beat.largest_offset_ms,
                        }
                        for beat in held
                    ],
                }
                for bar, held in bars.items()
            ]
        },
    )


def _describe(beat: BeatGrid) -> str:
    """For example "bar 33, beat 2: 16th or 8th triplet", counted from 1."""
    where = f"bar {beat.bar + 1}, beat {beat.beat + 1}: {_spoken(beat.grid)}"
    if beat.alternatives:
        return f"{where} or {' or '.join(_spoken(grid) for grid in beat.alternatives)}"
    return f"{where}, with a note {beat.largest_offset_ms:.0f} ms off it"


def _spoken(grid: Grid) -> str:
    return grid.replace("_", " ")
