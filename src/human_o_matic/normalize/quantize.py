"""Quantizing the hits: graces, limbs on one grid point, and each beat's grid.

A drum is a family and piece, such as `snare` or `tom.2`, whatever the articulation. In turn:
1. **Graces.** Two hits in a row on one drum from `UNISON_MS` to under `GRACE_MS` apart are a
   grace and its main, as in a flam, unless the gap is within `GRID_GAP_MS` of a grid step at
   the local tempo, as in a fast roll or double kick, which are notes of the grid. Several in a
   row, as in a drag, are all graces of the last. Hits on one drum under `UNISON_MS` apart are
   one stroke, such as a hat pedal under a stick hit, and share a grid point.
2. **Onsets.** The other hits are gathered into onsets, in time order: a hit joins the onset
   when it is within the limb window of the onset's first hit and on a drum the onset doesn't
   have yet, apart from a stroke on one drum. The window is `LIMB_MS`, or half a 32nd at the
   local tempo when that is shorter, so two drums one 32nd apart stay apart. An onset's time is
   the mean of its hits'.
3. **Grids.** Each beat's grid is chosen from its onsets, and each onset goes to its nearest
   point (`grid.snap`) and belongs to the beat that point is in, so one played just before a
   beat belongs to it (ADR 0086). Every hit of an onset takes its tick, its beat and its own
   offset.
4. **Graces placed.** A grace goes before its main's tick by its performed gap, rounded to a
   tick and at least one tick, and takes its main's beat.
Finally, a note never ends up before an earlier note of its pitch and channel.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from human_o_matic.midi.tempo import FloatArray, IntArray, TempoMap, TimeSignatureMap
from human_o_matic.normalize.grid import (
    DIVISIONS,
    GRIDS,
    BeatGrid,
    Grid,
    beat_windows,
    no_grid,
    snap,
)
from human_o_matic.normalize.read import Hit

GRACE_MS = 45.0
"""Two hits on one drum closer than this are a grace and its main."""
UNISON_MS = 5.0
"""Two hits on one drum closer than this are one stroke, not a grace."""
GRID_GAP_MS = 15.0
"""A gap within this of a grid step at the local tempo is two notes of the grid, not a grace."""
LIMB_MS = 20.0
"""Hits on different drums within this of an onset's first hit are one onset."""

type Drum = tuple[str, int]


@dataclass(frozen=True, slots=True, kw_only=True)
class Quantized:
    """Where each hit goes, in the order of the hits given."""

    ticks: IntArray
    offsets_ms: FloatArray
    """Each hit's performed time minus its tick's, in milliseconds."""
    beat_of: IntArray
    """Each hit's beat, as a position in `beats`. A grace has its main's."""
    grace_of: tuple[int | None, ...]
    """For a grace, the position of its main among the hits."""
    beats: tuple[BeatGrid, ...]


def drum(hit: Hit) -> Drum:
    return hit.family, hit.piece


def quantize(
    hits: Sequence[Hit],
    tempos: TempoMap,
    signatures: TimeSignatureMap,
    grids: Mapping[tuple[int, int], Grid] | None = None,
) -> Quantized:
    """Quantize hits given in the order of `MidiSong.notes`. `grids` gives the grid of a beat by
    its bar and place in the bar. Raises `AnswerError` for a grid the beat can't have, or given
    to a beat without notes."""
    if not hits:
        if grids:
            raise no_grid(*min(grids))
        empty = np.zeros(0, dtype=np.int64)
        return Quantized(ticks=empty, offsets_ms=np.zeros(0), beat_of=empty, grace_of=(), beats=())
    starts = np.array([hit.note.start for hit in hits], dtype=np.int64)
    ms = tempos.ticks_to_ms(starts)
    grace_of = _graces(hits, starts, ms, tempos)

    onset_of, onset_ms = _onsets(hits, starts, ms, grace_of, tempos)
    onset_ticks = tempos.ms_to_ticks(onset_ms)
    # The beats run to the end of the bar after the last hit's, so a hit played just before
    # that bar's first beat has a beat to belong to.
    beats = beat_windows(
        signatures, signatures.bar_start(signatures.bar_at(int(starts.max())) + 1) + 1
    )
    snapped = snap(onset_ticks, onset_ms, beats, tempos, grids)

    ticks = np.zeros(len(hits), dtype=np.int64)
    beat_of = np.zeros(len(hits), dtype=np.int64)
    mains = onset_of >= 0
    ticks[mains] = snapped.ticks[onset_of[mains]]
    beat_of[mains] = snapped.beat_of[onset_of[mains]]
    for position, main in enumerate(grace_of):
        if main is None:
            continue
        gap_ms = ms[main] - ms[position]
        placed = round(tempos.ms_to_tick(tempos.tick_to_ms(int(ticks[main])) - gap_ms))
        ticks[position] = max(min(placed, int(ticks[main]) - 1), 0)
        beat_of[position] = beat_of[main]

    # Same-pitch notes never reorder.
    last: dict[tuple[int, int], int] = {}
    for position, hit in enumerate(hits):
        key = (hit.note.channel, hit.note.pitch)
        ticks[position] = max(int(ticks[position]), last.get(key, 0))
        last[key] = int(ticks[position])

    return Quantized(
        ticks=ticks,
        offsets_ms=ms - tempos.ticks_to_ms(ticks),
        beat_of=beat_of,
        grace_of=grace_of,
        beats=snapped.beats,
    )


def _grid_like(gap_ms: float, tick: int, tempos: TempoMap) -> bool:
    """Whether a gap is a grid step at the local tempo, give or take `GRID_GAP_MS`."""
    quarter_ms = tempos.ms_per_tick(tick) * tempos.ppq
    return any(abs(gap_ms - quarter_ms / DIVISIONS[grid]) <= GRID_GAP_MS for grid in GRIDS)


def _graces(
    hits: Sequence[Hit], starts: IntArray, ms: FloatArray, tempos: TempoMap
) -> tuple[int | None, ...]:
    """For each hit that is a grace, the position of its main."""
    by_drum: dict[Drum, list[int]] = {}
    for position, hit in enumerate(hits):
        by_drum.setdefault(drum(hit), []).append(position)
    main_of: list[int | None] = [None] * len(hits)
    for positions in by_drum.values():
        # Backwards, so a run of graces all point at the main that ends it.
        for earlier, later in reversed(list(pairwise(positions))):
            gap = float(ms[later] - ms[earlier])
            if UNISON_MS <= gap < GRACE_MS and not _grid_like(gap, int(starts[later]), tempos):
                main_of[earlier] = main_of[later] if main_of[later] is not None else later
    return tuple(main_of)


def _onsets(
    hits: Sequence[Hit],
    starts: IntArray,
    ms: FloatArray,
    grace_of: Sequence[int | None],
    tempos: TempoMap,
) -> tuple[IntArray, FloatArray]:
    """Each hit's onset, -1 for a grace, and each onset's time in milliseconds."""
    onset_of = np.full(len(hits), -1, dtype=np.int64)
    order = sorted(
        (position for position, main in enumerate(grace_of) if main is None),
        key=lambda position: (float(ms[position]), position),
    )
    count = 0
    first = window = 0.0
    members: dict[Drum, float] = {}
    """The time of each drum's first hit in the current onset."""
    for position in order:
        at, key = float(ms[position]), drum(hits[position])
        same = members.get(key)
        if not (count and at - first <= window and (same is None or at - same < UNISON_MS)):
            count += 1
            first = at
            half_32nd = tempos.ms_per_tick(int(starts[position])) * tempos.ppq / 16
            window = min(LIMB_MS, half_32nd)
            members = {}
        onset_of[position] = count - 1
        members.setdefault(key, at)
    mains = onset_of >= 0
    sums = np.bincount(onset_of[mains], weights=ms[mains], minlength=count)
    sizes = np.bincount(onset_of[mains], minlength=count)
    return onset_of, sums / sizes
