"""Tick, beat and millisecond conversions, from a song's tempo and time signature maps.

Ticks are absolute, at the song's PPQ. Milliseconds count from tick 0. Bars and beats come from
the time signatures: a beat is the signature's denominator note (an eighth in 7/8), and bars and
beats count from 0.

Tempo and time signature events are read from every track, so they can sit on a different track
from the notes, as in a format 1 file's conductor track. At one tick the last event wins, in
track order and then file order, as a sequencer playing the file would apply them.
"""

import bisect
import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

import numpy as np
import numpy.typing as npt

from human_o_matic.decisions import DecisionRequest, DecisionRequired
from human_o_matic.midi.io import Event, MidiSong

META_TEMPO = 0x51
META_TIME_SIGNATURE = 0x58
MICROSECONDS_PER_MINUTE = 60_000_000
MAX_DENOMINATOR_EXPONENT = 6
"""Time signatures with a denominator over 64 are treated as malformed and left out."""

type FloatArray = npt.NDArray[np.float64]
type IntArray = npt.NDArray[np.int64]


class TempoMap:
    """Converts between ticks and milliseconds under a piecewise-constant tempo.

    The cumulative time at each tempo change is computed once, and each conversion finds its
    segment with a binary search, so a map of thousands of changes costs no more per call than
    a map of one.
    """

    __slots__ = ("_ms_at", "_ms_per_tick", "ppq", "starts", "tempos")

    def __init__(self, ppq: int, ticks: npt.ArrayLike, tempos: npt.ArrayLike) -> None:
        """A map from tempo changes: at each of `ticks`, the tempo becomes the matching entry
        of `tempos`, in microseconds per quarter note.

        Changes are sorted by tick, keeping the order of changes at one tick, and the last
        change at a tick wins. The first tempo also holds before the first change.
        """
        if ppq <= 0:
            raise ValueError(f"resolution {ppq} PPQ is not positive")
        tick_array = np.asarray(ticks, dtype=np.int64).ravel()
        tempo_array = np.asarray(tempos, dtype=np.float64).ravel()
        if tick_array.size == 0 or tick_array.shape != tempo_array.shape:
            raise ValueError("a tempo map needs one tempo for each of one or more ticks")
        if np.any(tick_array < 0):
            raise ValueError("tempo changes cannot be at negative ticks")
        if not np.all(np.isfinite(tempo_array) & (tempo_array > 0)):
            raise ValueError("tempos must be positive and finite")
        by_tick = np.argsort(tick_array, kind="stable")
        tick_array, tempo_array = tick_array[by_tick], tempo_array[by_tick]
        last_at_tick = np.append(tick_array[1:] != tick_array[:-1], True)
        starts, segment_tempos = tick_array[last_at_tick], tempo_array[last_at_tick]
        starts[0] = 0
        ms_per_tick = segment_tempos / (1000.0 * ppq)
        ms_at = np.concatenate(([0.0], np.cumsum(np.diff(starts) * ms_per_tick[:-1])))
        for array in (starts, segment_tempos, ms_per_tick, ms_at):
            array.flags.writeable = False
        self.ppq = ppq
        self.starts: IntArray = starts
        """The tick where each tempo segment starts. The first is 0."""
        self.tempos: FloatArray = segment_tempos
        """Each segment's tempo, in microseconds per quarter note."""
        self._ms_per_tick: FloatArray = ms_per_tick
        self._ms_at: FloatArray = ms_at

    @classmethod
    def constant(cls, ppq: int, bpm: float) -> Self:
        if not (math.isfinite(bpm) and bpm > 0):
            raise ValueError(f"tempo {bpm} BPM is not positive and finite")
        return cls(ppq, [0], [MICROSECONDS_PER_MINUTE / bpm])

    def __len__(self) -> int:
        return int(self.starts.size)

    def ticks_to_ms(self, ticks: npt.ArrayLike) -> FloatArray:
        """Milliseconds from tick 0 to each of `ticks`, which may be fractional or negative."""
        at = np.asarray(ticks, dtype=np.float64)
        segment = self._segments(np.searchsorted(self.starts, at, side="right"))
        return self._ms_at[segment] + (at - self.starts[segment]) * self._ms_per_tick[segment]

    def ms_to_ticks(self, ms: npt.ArrayLike) -> FloatArray:
        """The fractional tick at each of `ms`, the reverse of `ticks_to_ms`."""
        at = np.asarray(ms, dtype=np.float64)
        segment = self._segments(np.searchsorted(self._ms_at, at, side="right"))
        return self.starts[segment] + (at - self._ms_at[segment]) / self._ms_per_tick[segment]

    def tick_to_ms(self, tick: float) -> float:
        return float(self.ticks_to_ms(tick))

    def ms_to_tick(self, ms: float) -> float:
        return float(self.ms_to_ticks(ms))

    def ms_per_tick(self, tick: float) -> float:
        """The length of one tick at `tick`, in milliseconds."""
        return float(self._ms_per_tick[self._segment(tick)])

    def bpm(self, tick: float) -> float:
        """The tempo at `tick`, in quarter notes per minute."""
        return MICROSECONDS_PER_MINUTE / float(self.tempos[self._segment(tick)])

    def _segment(self, tick: float) -> int:
        return max(int(np.searchsorted(self.starts, tick, side="right")) - 1, 0)

    def _segments(self, after: npt.NDArray[np.intp]) -> npt.NDArray[np.intp]:
        # Before the first segment, the first one's tempo continues.
        return np.maximum(after - 1, 0)


@dataclass(frozen=True, slots=True)
class TimeSignature:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.numerator < 1:
            raise ValueError(f"time signature numerator {self.numerator} is not positive")
        if self.denominator < 1 or self.denominator & (self.denominator - 1):
            raise ValueError(f"time signature denominator {self.denominator} is not 2 to a power")

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"


FOUR_FOUR = TimeSignature(4, 4)


@dataclass(frozen=True, slots=True)
class BarBeat:
    bar: int
    """Counting from 0."""
    beat: float
    """Position in the bar, counting from 0, in the signature's denominator notes."""


class TimeSignatureMap:
    """Bars and beats under a list of time signature changes.

    A change that repeats the signature in force changes nothing, wherever it sits. A change to
    a different signature starts a bar at its tick, so a change in the middle of a bar ends that
    bar early. Before the first change, or with none, the signature is 4/4, as the MIDI file
    specification defines, and `assumed` says so.

    Bar arithmetic is exact in whole ticks: bar `n` of a segment starts `floor(n * N * 4 * PPQ
    / D)` ticks after the segment, for signature N/D.
    """

    __slots__ = ("_bars", "_signatures", "_starts", "assumed", "ppq")

    def __init__(self, ppq: int, changes: Iterable[tuple[int, TimeSignature]]) -> None:
        """A map from `(tick, signature)` changes, sorted by tick, keeping the order of changes
        at one tick. The last change at a tick wins."""
        if ppq <= 0:
            raise ValueError(f"resolution {ppq} PPQ is not positive")
        self.ppq = ppq
        starts, bars, signatures = [0], [0], [FOUR_FOUR]
        assumed = True
        for tick, signature in sorted(changes, key=lambda change: change[0]):
            if tick < 0:
                raise ValueError("time signature changes cannot be at negative ticks")
            if tick == 0:
                assumed = False
            if tick == starts[-1]:
                signatures[-1] = signature
                if len(signatures) > 1 and signatures[-2] == signature:
                    del starts[-1], bars[-1], signatures[-1]
            elif signature != signatures[-1]:
                bars.append(bars[-1] + self._bars_before(tick - starts[-1], signatures[-1]))
                starts.append(tick)
                signatures.append(signature)
        self.assumed = assumed
        """True when no time signature is set at tick 0, so 4/4 is assumed until the first."""
        self._starts = tuple(starts)
        self._bars = tuple(bars)
        self._signatures = tuple(signatures)

    @property
    def changes(self) -> tuple[tuple[int, int, TimeSignature], ...]:
        """Each signature in force as `(tick, bar, signature)`, starting at tick 0, bar 0."""
        return tuple(zip(self._starts, self._bars, self._signatures, strict=True))

    def signature_at(self, tick: int) -> TimeSignature:
        return self._signatures[self._by_tick(tick)]

    def bar_at(self, tick: int) -> int:
        """The bar that `tick` is in."""
        segment = self._by_tick(tick)
        signature = self._signatures[segment]
        offset = tick - self._starts[segment]
        bar_ticks, denominator = self._bar_ratio(signature)
        # The last bar n whose start, floor(n * bar_ticks / denominator), is at or before offset.
        return self._bars[segment] + ((offset + 1) * denominator - 1) // bar_ticks

    def bar_start(self, bar: int) -> int:
        """The tick where `bar` starts."""
        segment = max(bisect.bisect_right(self._bars, bar) - 1, 0)
        bar_ticks, denominator = self._bar_ratio(self._signatures[segment])
        return self._starts[segment] + (bar - self._bars[segment]) * bar_ticks // denominator

    def position(self, tick: int) -> BarBeat:
        """The bar and beat of `tick`."""
        bar = self.bar_at(tick)
        signature = self._signatures[self._by_tick(tick)]
        beat_ticks = 4 * self.ppq / signature.denominator
        return BarBeat(bar, (tick - self.bar_start(bar)) / beat_ticks)

    def tick_at(self, bar: int, beat: float = 0.0) -> int:
        """The tick of `beat` in `bar`, the reverse of `position`, rounded to a whole tick."""
        segment = max(bisect.bisect_right(self._bars, bar) - 1, 0)
        beat_ticks = 4 * self.ppq / self._signatures[segment].denominator
        return self.bar_start(bar) + round(beat * beat_ticks)

    def bar_starts(self, end: int) -> IntArray:
        """The tick of every bar line from tick 0 up to, but not including, `end`."""
        lines: list[IntArray] = []
        for segment, start in enumerate(self._starts):
            if start >= end:
                break
            stop = self._starts[segment + 1] if segment + 1 < len(self._starts) else end
            stop = min(stop, end)
            bar_ticks, denominator = self._bar_ratio(self._signatures[segment])
            count = self._bars_before(stop - start, self._signatures[segment])
            numbers = np.arange(count, dtype=np.int64)
            lines.append(start + numbers * bar_ticks // denominator)
        return np.concatenate(lines) if lines else np.zeros(0, dtype=np.int64)

    def _by_tick(self, tick: int) -> int:
        return max(bisect.bisect_right(self._starts, tick) - 1, 0)

    def _bar_ratio(self, signature: TimeSignature) -> tuple[int, int]:
        """A bar's length in ticks as the ratio `bar_ticks / denominator`, kept exact."""
        return signature.numerator * 4 * self.ppq, signature.denominator

    def _bars_before(self, ticks: int, signature: TimeSignature) -> int:
        """How many bars of `signature` start within the first `ticks` ticks of a segment. A
        partial bar counts."""
        bar_ticks, denominator = self._bar_ratio(signature)
        return (ticks * denominator - 1) // bar_ticks + 1 if ticks > 0 else 0


def tempo_map(song: MidiSong, *, bpm: float | None = None) -> TempoMap:
    """The song's tempo map, or a constant `bpm` when given, which replaces the file's tempo.

    Raises `DecisionRequired` when the file has no tempo event and no `bpm` is given: the
    tempo is never assumed.
    """
    if bpm is not None:
        return TempoMap.constant(song.ppq, bpm)
    ticks: list[int] = []
    tempos: list[int] = []
    for event in _in_playback_order(song.events, META_TEMPO):
        tempo = int.from_bytes(event.data[:3], "big") if len(event.data) >= 3 else 0
        if tempo > 0:
            ticks.append(event.tick)
            tempos.append(tempo)
    if not ticks:
        raise DecisionRequired(
            DecisionRequest(
                kind="tempo",
                message="This file has no tempo, so its timing can't be measured. "
                "What is the song's tempo in BPM?",
                answer_with=("bpm",),
            )
        )
    return TempoMap(song.ppq, ticks, tempos)


def time_signature_map(song: MidiSong) -> TimeSignatureMap:
    """The song's time signature map. Malformed signatures are left out of it."""
    changes = [
        (event.tick, TimeSignature(event.data[0], 2 ** event.data[1]))
        for event in _in_playback_order(song.events, META_TIME_SIGNATURE)
        if len(event.data) >= 2 and event.data[0] and event.data[1] <= MAX_DENOMINATOR_EXPONENT
    ]
    return TimeSignatureMap(song.ppq, changes)


def _in_playback_order(events: Iterable[Event], meta_type: int) -> list[Event]:
    chosen = [event for event in events if event.meta_type == meta_type]
    chosen.sort(key=lambda event: (event.tick, event.track, event.order))
    return chosen
