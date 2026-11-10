"""Calibration from the performed MIDI in `private/midi/`. This version measures; fitting follows.

Every file of a folder that `private/data/midi-folders.toml` assigns a kit is read through that
kit with `normalize()`, as the app reads a song, and cut into grooves (ADR 0059): a file of up to
`WINDOW_BARS` bars is one groove, and a longer one is cut into equal windows of at most that. Each
groove gets the statistics the engine is tested on (`render/measure.py`, ADR 0061):
- **energy:** the mean velocity of its normal-typed notes;
- **dynamic range:** the mean, over drums with two or more, of the spread of their normal-typed
  notes' velocities;
- **timing spread:** the spread of its notes' offsets from the grid, graces left out, in ms;
- **feel:** the mean offset of its snare and rider hits less that of its kicks, in ms.

What a file leaves open is measured around (ADR 0059): notes its kit doesn't map are left out and
counted, as are notes on the pitches its folder's assignment leaves out (ADR 0057), ambiguous
beats keep the quantizer's best guess, and a file without a tempo has its velocities measured and
its timing not. A file that can't be read, or whose drum track is unclear, is counted with why.

Timing is measured only on a groove with at least `MIN_NOTES` notes, graces left out, and not on
one held to the grid (ADR 0060): one whose notes pile up at one offset from the grid, more than
`ON_GRID` of them there and more than `SPIKE` times as many as one step either side, as
quantizing all or some of its drums leaves them; or whose notes spread by under `MIN_STEPS`
steps, as quantized notes with a tick or so of jitter do. A step is the smallest gap between the
groove's offsets, a tick unless the file was saved at a finer resolution than it was played at.

Grooves the grid doesn't fit are left out of the timing fits (ADR 0064). `--misfit SHARE` leaves
out a groove with more than that share of its notes over 20 ms from their grid point; it is off
until its threshold is set. A pack, a folder's first-level subfolder, is a source (ADR 0063), so a
band is flagged when one pack supplies most of it. Velocities are fitted once for every style
(ADR 0065), on every groove whose velocities aren't flat.

`measure` prints, for every folder pooled and then for each one, how many files and grooves were
measured and why any weren't, the distribution of timing spread of the grooves with performed
timing, the grooves the shared velocity fit would draw on, the bands that cuts at the thirds, at
whole milliseconds near them, and at thirds that count each pack the same would make, and each
pack's counts. With `--excluded` it also measures the timing of the folders the assignments leave
out, apart from the rest, through a kit in which every pitch is a drum of its own, since an
offset from the grid needs no name. Nothing is written: the numbers name folders, so they stay on
the screen (ADR 0007).

Run from the repository root:
    uv run python tools/calibrate.py measure
    uv run python tools/calibrate.py measure --misfit 0.05 --excluded --cuts 4,8
"""

import argparse
import math
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Literal

import numpy as np

from human_o_matic.decisions import DecisionRequired
from human_o_matic.instruments.drums import drum_parts
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_vocabulary
from human_o_matic.maps.schema import Library
from human_o_matic.midi.io import MidiFileError, read_midi
from human_o_matic.midi.tempo import tempo_map
from human_o_matic.midi.tracks import choose_drum_track
from human_o_matic.normalize.grid import FAR_MS
from human_o_matic.normalize.pipeline import normalize
from human_o_matic.normalize.score import Score, ScoreNote
from human_o_matic.render.parts import Part
from midi_folders import ASSIGNMENTS, MIDI, AssignmentError, Assignments, folders, midi_files

WINDOW_BARS = 16
"""The most bars a groove spans. The engine's 3.1 ms at the defaults is measured over 16 bars
(ADR 0051), and slow drift shows more over longer stretches."""
MIN_NOTES = 32
"""The fewest notes, graces left out, whose offsets give a groove a timing spread."""
ON_GRID = 0.2
"""More than this share of a groove's notes at one offset from the grid, with a spike there, holds
it to the grid."""
SPIKE = 2.0
"""A pile at one offset is a spike when it holds more than this many times as many notes as the
offsets one step either side, on average. A smooth spread, however narrow, holds about as many
there."""
MIN_STEPS = 1.5
"""A groove whose offsets spread by less than this many steps is held to the grid: quantized
notes with a tick or so of jitter, tighter than any drummer at 480 PPQ."""
NO_TEMPO_BPM = 120.0
"""The tempo a file without one is normalized at, for its velocities only. Its timing is left
out, since its milliseconds would be made up."""
FLAT_NOTES = 4
"""A drum needs this many normal-typed notes in a groove to tell flat velocities from varied."""
NEAR_ONE_PACK = 0.9
"""A band is flagged when one pack supplies at least this much of its grooves (ADR 0063)."""
PERCENTILES = (5, 10, 25, 33, 50, 67, 75, 90, 95)
HISTOGRAM_MS = 15
"""The histogram has a bin per millisecond up to this, and one for everything above."""
EXIT_USAGE = 2

type Timing = Literal["performed", "on_grid", "no_tempo", "too_few"]
"""Whether a groove's timing is measured, or why not."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Groove:
    """One groove's statistics."""

    folder: str
    pack: str
    """The folder and the subfolder the file is in, or the folder alone for a file directly in
    it. A pack is a source (ADR 0063)."""
    file: str
    """Its path under the folder of folders."""
    bars: tuple[int, int]
    """Its first bar and the bar after its last, counted from 0."""
    notes: int
    """Its notes, graces left out."""
    at_one_offset: float
    """The share of those notes at the groove's most common offset from the grid, in ticks."""
    spike: float
    """How many times as many notes are at that offset as one step either side, on average."""
    steps: float
    """The spread of the notes' offsets, in steps."""
    timing: Timing
    far: float
    """The share of its notes more than 20 ms from their grid point."""
    ambiguous: float
    """The share of its beats whose grid is a guess."""
    spread_ms: float | None
    feel_ms: float | None
    energy: float | None
    dynamic_range: float | None
    flat: bool | None
    """Every drum with `FLAT_NOTES` normal-typed notes or more has at most two velocities, as a
    programmed part does; None when no drum has that many."""

    def misfit(self, share: float | None) -> bool:
        """Whether the grid doesn't fit it: more than `share` of its notes far from the grid."""
        return share is not None and self.far > share


@dataclass(slots=True)
class FileResult:
    path: str
    folder: str
    grooves: list[Groove] = field(default_factory=list[Groove])
    problem: str | None = None
    """Why the file wasn't measured."""
    unmapped: int = 0
    """Notes its kit doesn't map, left out of every statistic."""
    left_out: int = 0
    """Notes on pitches its folder's assignment leaves out, left out of every statistic."""
    ambiguous_beats: int = 0
    tempo: bool = True


@dataclass(frozen=True, slots=True)
class Source:
    """How a file is read: through a kit, with some pitches left out."""

    kit: DrumKit
    leave_out: frozenset[int] = frozenset()


def every_pitch_kit() -> DrumKit:
    """A kit in which every pitch is a drum of its own, `sample.1.hit` for note 0 and so on, for
    measuring timing without trusting any names. It is built here, never loaded from a file."""
    library = Library.model_validate(
        {
            "schema": 1,
            "id": "every-pitch",
            "name": "Every pitch a drum of its own",
            "kits": [
                {
                    "id": "default",
                    "name": "Every pitch",
                    "articulations": [
                        {
                            "name": f"sample.{pitch + 1}.hit",
                            "notes": [pitch],
                            "source": "inferred",
                            "confidence": "low",
                        }
                        for pitch in range(128)
                    ],
                }
            ],
        }
    )
    return DrumKit(library, library.kits[0], built_in_vocabulary())


def measure_file(path: Path, relative: PurePosixPath, source: Source) -> FileResult:
    """A file's grooves, or why it couldn't be measured."""
    folder = relative.parts[0]
    result = FileResult(path=str(relative), folder=folder)
    try:
        song = read_midi(path)
        drums = choose_drum_track(song).track
    except (OSError, MidiFileError) as error:
        result.problem = f"not read: {error}"
        return result
    except DecisionRequired as asked:
        result.problem = f"{asked.request.kind}: needs an answer"
        return result
    if source.leave_out:
        kept = tuple(
            note for note in song.notes if note.track != drums or note.pitch not in source.leave_out
        )
        result.left_out = len(song.notes) - len(kept)
        song = replace(song, notes=kept)
    try:
        tempo_map(song)
    except DecisionRequired:
        result.tempo = False
    try:
        normalized = normalize(
            song, source.kit, track=drums, bpm=None if result.tempo else NO_TEMPO_BPM
        )
    except DecisionRequired as asked:
        result.problem = f"{asked.request.kind}: needs an answer"
        return result
    except MidiFileError as error:
        result.problem = f"not read: {error}"
        return result
    score = normalized.score
    result.unmapped = len(normalized.pending)
    result.ambiguous_beats = len(score.ambiguous)
    pack = "/".join(relative.parts[:2]) if len(relative.parts) > 2 else folder
    parts = drum_parts(score)
    for first, end in windows(score):
        chosen = [
            (note, part)
            for note, part in zip(score.notes, parts, strict=True)
            if first <= score.signatures.bar_at(note.tick) < end
        ]
        beats = [beat for beat in score.beats if first <= beat.bar < end]
        ambiguous = sum(beat.ambiguous for beat in beats) / max(len(beats), 1)
        result.grooves.append(_groove(chosen, result, pack, (first, end), ambiguous))
    return result


def windows(score: Score) -> list[tuple[int, int]]:
    """The grooves of a score, as bar ranges: one for up to `WINDOW_BARS` bars, and otherwise
    the fewest equal windows of at most that many, from its first bar with notes to its last."""
    if not score.notes:
        return []
    bars = [score.signatures.bar_at(note.tick) for note in score.notes]
    first, last = min(bars), max(bars)
    count = last - first + 1
    pieces = math.ceil(count / WINDOW_BARS)
    edges = [first + round(index * count / pieces) for index in range(pieces + 1)]
    return list(pairwise(edges))


@dataclass(frozen=True, slots=True)
class GridTest:
    """How a groove's offsets from the grid sit, in ticks (ADR 0060)."""

    at_one_offset: float
    spike: float
    steps: float

    @property
    def held(self) -> bool:
        piled = self.at_one_offset > ON_GRID and self.spike > SPIKE
        return piled or self.steps < MIN_STEPS


def grid_test(offsets: Sequence[int]) -> GridTest:
    """The test of ADR 0060 on a groove's offsets from their grid points, in ticks."""
    if not offsets:
        return GridTest(at_one_offset=0.0, spike=0.0, steps=0.0)
    counts = Counter(offsets)
    mode, top = counts.most_common(1)[0]
    step = 0
    for offset in counts:
        step = math.gcd(step, offset - mode)
    if step == 0:
        return GridTest(at_one_offset=1.0, spike=math.inf, steps=0.0)
    side = (counts[mode - step] + counts[mode + step]) / 2
    return GridTest(
        at_one_offset=top / len(offsets),
        spike=top / side if side else math.inf,
        steps=float(np.std(np.array(offsets, dtype=np.float64))) / step,
    )


def _groove(
    chosen: Sequence[tuple[ScoreNote, Part]],
    result: FileResult,
    pack: str,
    bars: tuple[int, int],
    ambiguous: float,
) -> Groove:
    mains = [(note, part) for note, part in chosen if note.grace_of is None]
    offsets = np.array([note.offset_ms for note, _ in mains], dtype=np.float64)
    test = grid_test([note.source.start - note.tick for note, _ in mains])
    timing: Timing
    if len(mains) < MIN_NOTES:
        timing = "too_few"
    elif not result.tempo:
        timing = "no_tempo"
    elif test.held:
        timing = "on_grid"
    else:
        timing = "performed"
    performed = timing == "performed"
    notes = [note for note, _ in chosen]
    return Groove(
        folder=result.folder,
        pack=pack,
        file=result.path,
        bars=bars,
        notes=len(mains),
        at_one_offset=test.at_one_offset,
        spike=test.spike,
        steps=test.steps,
        timing=timing,
        far=float(np.mean(np.abs(offsets) > FAR_MS)) if len(offsets) else 0.0,
        ambiguous=ambiguous,
        spread_ms=float(np.std(offsets)) if performed else None,
        feel_ms=_feel(mains) if performed else None,
        energy=_energy(notes),
        dynamic_range=_dynamic_range(notes),
        flat=_flat(notes),
    )


def _feel(mains: Sequence[tuple[ScoreNote, Part]]) -> float | None:
    """The mean offset of the snare and the riders less that of the kicks: how far behind the
    feet they play, which a whole performance shifted against its grid doesn't change."""
    upper = [note.offset_ms for note, part in mains if part.limb in ("snare", "rider")]
    kicks = [note.offset_ms for note, part in mains if part.role in ("kick", "double_kick")]
    if not upper or not kicks:
        return None
    return float(np.mean(upper) - np.mean(kicks))


def _energy(notes: Sequence[ScoreNote]) -> float | None:
    velocities = [note.source.velocity for note in notes if note.hit_type == "normal"]
    return float(np.mean(velocities)) if velocities else None


def _by_drum(notes: Sequence[ScoreNote]) -> list[list[int]]:
    drums: dict[tuple[str, int], list[int]] = {}
    for note in notes:
        if note.hit_type == "normal":
            drums.setdefault((note.family, note.piece), []).append(note.source.velocity)
    return list(drums.values())


def _dynamic_range(notes: Sequence[ScoreNote]) -> float | None:
    spreads = [float(np.std(velocities)) for velocities in _by_drum(notes) if len(velocities) > 1]
    return float(np.mean(spreads)) if spreads else None


def _flat(notes: Sequence[ScoreNote]) -> bool | None:
    drums = [velocities for velocities in _by_drum(notes) if len(velocities) >= FLAT_NOTES]
    if not drums:
        return None
    return all(len(set(velocities)) <= 2 for velocities in drums)


def measure(
    root: Path, names: Iterable[str], source_of: Callable[[PurePosixPath], Source | None]
) -> list[FileResult]:
    """Every file of the named folders, each read as `source_of` says for its path, or left out
    when it gives nothing."""
    results: list[FileResult] = []
    for name in names:
        for path in midi_files(root / name):
            relative = PurePosixPath(path.relative_to(root).as_posix())
            source = source_of(relative)
            if source is not None:
                results.append(measure_file(path, relative, source))
    return results


def timed(grooves: Iterable[Groove], misfit: float | None = None) -> list[Groove]:
    """The grooves the timing fits draw on: those with performed timing that the grid fits."""
    return [g for g in grooves if g.timing == "performed" and not g.misfit(misfit)]


def velocity_grooves(grooves: Iterable[Groove]) -> list[Groove]:
    """The grooves the shared velocity fit draws on: every one whose velocities aren't flat,
    whatever its timing (ADR 0065)."""
    return [groove for groove in grooves if groove.flat is False]


@dataclass(frozen=True, slots=True)
class Band:
    name: str
    low: float | None
    high: float | None
    """The band holds spreads from `low` up to, but not including, `high`."""

    def holds(self, spread: float) -> bool:
        above = self.low is None or spread >= self.low
        return above and (self.high is None or spread < self.high)


def bands(cuts: Sequence[float]) -> list[Band]:
    """The three bands two cuts make."""
    low, high = cuts
    return [Band("tight", None, low), Band("medium", low, high), Band("loose", high, None)]


def thirds(grooves: Sequence[Groove]) -> tuple[float, float]:
    spreads = np.array([_spread(groove) for groove in grooves], dtype=np.float64)
    low, high = np.percentile(spreads, [100 / 3, 200 / 3]).tolist()
    return low, high


def balanced_thirds(
    grooves: Sequence[Groove], source: Callable[[Groove], str]
) -> tuple[float, float]:
    """The thirds with each source, such as a pack, counted the same, however many grooves it
    has."""
    by_source = Counter(source(groove) for groove in grooves)
    spreads = np.array([_spread(groove) for groove in grooves], dtype=np.float64)
    weights = np.array([1 / by_source[source(groove)] for groove in grooves], dtype=np.float64)
    order = np.argsort(spreads)
    cumulative = np.cumsum(weights[order]) / weights.sum()
    picks = [float(spreads[order][np.searchsorted(cumulative, share)]) for share in (1 / 3, 2 / 3)]
    return picks[0], picks[1]


def _pack(groove: Groove) -> str:
    return groove.pack


def _spread(groove: Groove) -> float:
    assert groove.spread_ms is not None
    return groove.spread_ms


def alternatives(
    grooves: Sequence[Groove], extra: Sequence[tuple[float, float]] = ()
) -> list[tuple[str, tuple[float, float]]]:
    """The cuts to show: the thirds, whole milliseconds near them, the thirds that count each
    pack the same, and any given."""
    given = [(f"given {a:g} and {b:g} ms", (a, b)) for a, b in extra]
    if len(grooves) < 3:
        return given
    low, high = thirds(grooves)
    whole = max(round(low), 1)
    return [
        ("equal thirds", (low, high)),
        ("whole milliseconds near the thirds", (float(whole), float(max(round(high), whole + 1)))),
        ("thirds counting each pack the same", balanced_thirds(grooves, _pack)),
        *given,
    ]


def report(
    results: Sequence[FileResult],
    cuts: Sequence[tuple[float, float]] = (),
    misfit: float | None = None,
) -> str:
    """What `measure` prints for some files: counts, the timing spread, the shared velocity fit,
    the bands, and each pack."""
    grooves = [groove for result in results for groove in result.grooves]
    performed = [groove for groove in grooves if groove.timing == "performed"]
    fitted = timed(grooves, misfit)
    lines = _counts(results, grooves)
    if misfit is not None:
        lines += _misfits(performed, misfit)
    lines += _spreads(fitted)
    lines += _velocities(grooves)
    title = "" if misfit is None else ", the grooves the grid doesn't fit left out"
    for name, pair in alternatives(fitted, cuts):
        lines += _bands(f"{name}{title}", pair, fitted)
    if misfit is not None:
        lines.append("beside, with the grooves the grid doesn't fit kept in:")
        for name, pair in alternatives(performed, cuts):
            lines += _bands(name, pair, performed)
    lines += _packs(grooves, misfit)
    return "\n".join(lines)


def _counts(results: Sequence[FileResult], grooves: Sequence[Groove]) -> list[str]:
    problems = Counter(result.problem for result in results if result.problem)
    measured = [result for result in results if result.problem is None]
    lines = [
        f"files: {len(results)}, {len(measured)} measured"
        + (
            ", not: " + "; ".join(f"{why} ({n})" for why, n in sorted(problems.items()))
            if problems
            else ""
        ),
        f"  without a tempo: {sum(not result.tempo for result in measured)}; with unmapped notes:"
        f" {sum(result.unmapped > 0 for result in measured)} files, "
        f"{sum(result.unmapped for result in measured)} notes left out; notes on pitches the "
        f"assignments leave out: {sum(result.left_out for result in measured)}; with ambiguous "
        f"beats: {sum(result.ambiguous_beats > 0 for result in measured)} files",
    ]
    kinds = Counter(groove.timing for groove in grooves)
    held = [groove for groove in grooves if groove.timing == "on_grid"]
    piled = sum(groove.at_one_offset > ON_GRID and groove.spike > SPIKE for groove in held)
    lines.append(
        f"grooves: {len(grooves)} (windows of up to {WINDOW_BARS} bars); performed timing "
        f"{kinds['performed']}, held to the grid {kinds['on_grid']} ({piled} piled at one "
        f"offset, {len(held) - piled} only spread under {MIN_STEPS:g} steps), no tempo "
        f"{kinds['no_tempo']}, fewer than {MIN_NOTES} notes {kinds['too_few']}"
    )
    tested = [groove for groove in grooves if groove.timing in ("performed", "on_grid")]
    if tested:
        shares = np.array([groove.at_one_offset for groove in tested], dtype=np.float64)
        counts, _ = np.histogram(shares, bins=10, range=(0.0, 1.0))
        lines.append(
            "  share of notes at one offset from the grid, grooves with a tempo, by tenths: "
            + " ".join(str(int(count)) for count in counts)
        )
    return lines


def _misfits(performed: Sequence[Groove], misfit: float) -> list[str]:
    left = [groove for groove in performed if groove.misfit(misfit)]
    packs = Counter(groove.pack for groove in left)
    return [
        f"the grid doesn't fit {len(left)} of {len(performed)} performed grooves (more than "
        f"{misfit:g} of their notes over {FAR_MS:g} ms from their grid point), from {len(packs)} "
        "packs: " + ", ".join(f"{pack} {count}" for pack, count in packs.most_common())
    ]


def _spreads(grooves: Sequence[Groove]) -> list[str]:
    if not grooves:
        return ["timing spread: no groove for the timing fits"]
    spreads = np.array([_spread(groove) for groove in grooves], dtype=np.float64)
    values = np.percentile(spreads, PERCENTILES).tolist()
    lines = [
        f"timing spread, ms, of the {len(grooves)} grooves for the timing fits "
        "(Appendix A's tight style: 3 to 4 ms; ADR 0051: 3.1 ms over 16 bars at the defaults):",
        "  " + "  ".join(f"p{p} {value:.2f}" for p, value in zip(PERCENTILES, values, strict=True)),
    ]
    counts, _ = np.histogram(
        np.minimum(spreads, HISTOGRAM_MS), bins=HISTOGRAM_MS + 1, range=(0, HISTOGRAM_MS + 1)
    )
    top = max(int(counts.max()), 1)
    for start, count in enumerate(counts.tolist()):
        label = f"{start:>2}-{start + 1:<2}" if start < HISTOGRAM_MS else f"{HISTOGRAM_MS}+   "
        lines.append(f"  {label} {count:>6} {'#' * round(40 * count / top)}")
    feel = [groove.feel_ms for groove in grooves if groove.feel_ms is not None]
    if feel:
        q1, median, q3 = np.percentile(feel, [25, 50, 75]).tolist()
        lines.append(
            f"  feel, snare and riders less kicks, ms: median {median:.2f}, "
            f"quartiles {q1:.2f} to {q3:.2f}"
        )
    return lines


def _velocities(grooves: Sequence[Groove]) -> list[str]:
    lines: list[str] = []
    for kind, label in (("performed", "performed timing"), ("on_grid", "timing held to the grid")):
        chosen = [groove for groove in grooves if groove.timing == kind]
        energy = [groove.energy for groove in chosen if groove.energy is not None]
        spread = [groove.dynamic_range for groove in chosen if groove.dynamic_range is not None]
        if energy and spread:
            lines.append(
                f"velocities, grooves with {label}: energy median {np.median(energy):.1f}, "
                f"dynamic range median {np.median(spread):.1f}, flat "
                f"{sum(groove.flat is True for groove in chosen)} of {len(chosen)}"
            )
    shared = velocity_grooves(grooves)
    by_timing = Counter(groove.timing for groove in shared)
    lines.append(
        f"shared velocity fit: {len(shared)} grooves, from {len({g.folder for g in shared})} "
        f"folders and {len({g.pack for g in shared})} packs ("
        + ", ".join(f"{kind} {count}" for kind, count in sorted(by_timing.items()))
        + f"); left out: {sum(g.flat is True for g in grooves)} flat (every drum with "
        f"{FLAT_NOTES} or more normal notes at 2 velocities or fewer), "
        f"{sum(g.flat is None for g in grooves)} with no drum that has {FLAT_NOTES} normal notes"
    )
    return lines


def _bands(title: str, cuts: tuple[float, float], grooves: Sequence[Groove]) -> list[str]:
    lines = [f"cuts, {title}: {cuts[0]:.2f} and {cuts[1]:.2f} ms"]
    for band in bands(cuts):
        mine = [groove for groove in grooves if band.holds(_spread(groove))]
        folders_in = {groove.folder for groove in mine}
        packs = Counter(groove.pack for groove in mine)
        if not mine:
            lines.append(f"  {band.name:<6}      0 grooves")
            continue
        pack, count = packs.most_common(1)[0]
        median = float(np.median([_spread(groove) for groove in mine]))
        flag = ""
        if count >= NEAR_ONE_PACK * len(mine):
            flag = f"  <- {'one pack alone' if count == len(mine) else 'nearly one pack'}: {pack}"
        lines.append(
            f"  {band.name:<6} {len(mine):>6} grooves, {len(folders_in)} folders, {len(packs)} "
            f"packs, largest pack {100 * count / len(mine):.0f}%, median spread {median:.2f} ms"
            + flag
        )
    return lines


def _packs(grooves: Sequence[Groove], misfit: float | None) -> list[str]:
    lines = [
        "packs: grooves, performed, held, no tempo, too few"
        + (", misfit" if misfit is not None else "")
        + "; timing spread p25, median, p75 of the timing fits' grooves"
    ]
    for pack in sorted({groove.pack for groove in grooves}):
        mine = [groove for groove in grooves if groove.pack == pack]
        kinds = Counter(groove.timing for groove in mine)
        spreads = [_spread(groove) for groove in timed(mine, misfit)]
        quartiles = (
            " ".join(f"{value:.2f}" for value in np.percentile(spreads, [25, 50, 75]).tolist())
            if spreads
            else "-"
        )
        misfits = sum(groove.timing == "performed" and groove.misfit(misfit) for groove in mine)
        lines.append(
            f"  {pack}: {len(mine)}, {kinds['performed']}, {kinds['on_grid']}, "
            f"{kinds['no_tempo']}, {kinds['too_few']}"
            + (f", {misfits}" if misfit is not None else "")
            + f"; {quartiles}"
        )
    return lines


def _cuts(text: str) -> tuple[float, float]:
    try:
        low, high = (float(part) for part in text.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not two cuts in ms, as 4,7") from error
    if not 0 < low < high:
        raise argparse.ArgumentTypeError(f"{text!r}: the cuts must rise from above 0")
    return low, high


def _share(text: str) -> float:
    try:
        share = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not a share from 0 to 1") from error
    if not 0 <= share <= 1:
        raise argparse.ArgumentTypeError(f"{text!r} is not a share from 0 to 1")
    return share


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibration from the performed MIDI.")
    commands = parser.add_subparsers(dest="command", required=True)
    measuring = commands.add_parser(
        "measure", help="measure every groove, and print the timing spread and proposed bands"
    )
    measuring.add_argument("--root", type=Path, default=MIDI, help="the folder of folders")
    measuring.add_argument(
        "--assignments", type=Path, default=ASSIGNMENTS, help="which kit reads which folder"
    )
    measuring.add_argument(
        "--cuts",
        type=_cuts,
        action="append",
        default=[],
        metavar="LOW,HIGH",
        help="also show the bands these cuts in ms make; may be given more than once",
    )
    measuring.add_argument(
        "--misfit",
        type=_share,
        metavar="SHARE",
        help=f"leave out of the timing fits a groove with more than this share of its notes over "
        f"{FAR_MS:g} ms from their grid point, and show the bands without and with them "
        "(off until its threshold is set)",
    )
    measuring.add_argument(
        "--excluded",
        action="store_true",
        help="also measure the timing of the folders left out, apart, without their names",
    )
    args = parser.parse_args(argv)
    try:
        assignments = Assignments.read(args.assignments)
    except AssignmentError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    started = time.perf_counter()
    names = [folder.name for folder in folders(args.root)]

    def assigned(relative: PurePosixPath) -> Source | None:
        found = assignments.find(relative)
        if found is None or found.kit is None:
            return None
        return Source(found.kit, found.leave_out)

    results = measure(args.root, names, assigned)
    print("== every assigned folder")
    print(report(results, args.cuts, args.misfit))
    for name in names:
        mine = [result for result in results if result.folder == name]
        if mine:
            print(f"\n== {name}")
            print(report(mine, args.cuts, args.misfit))
    if args.excluded:
        neutral = Source(every_pitch_kit())

        def left_out(relative: PurePosixPath) -> Source | None:
            found = assignments.find(relative)
            return neutral if found is not None and found.kit is None else None

        apart = measure(args.root, names, left_out)
        print("\n== the folders left out, timing only, every pitch a drum of its own")
        print(report(apart, args.cuts, args.misfit))
        for name in names:
            mine = [result for result in apart if result.folder == name]
            if mine:
                print(f"\n== {name}, left out")
                print(report(mine, args.cuts, args.misfit))
    print(f"measured in {time.perf_counter() - started:.1f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
