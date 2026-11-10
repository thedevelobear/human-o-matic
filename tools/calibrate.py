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
counted, as are notes on the pitches its folder's assignment leaves out (ADR 0057), ambiguous beats
keep the quantizer's best guess, and a file without a tempo has its velocities measured and its
timing not. A file that can't be read, or whose drum track is unclear, is counted with why. Timing
is measured only on a groove with at least `MIN_NOTES` notes, and not on one held to the grid (ADR
0060): more than `ON_GRID` of its notes at one offset from the grid, exactly on it or all shifted
alike, more than a performance recorded at 480 PPQ or finer puts at one tick by chance. Such a
groove was quantized, in whole or in part, and would pass for a tight drummer.

`measure` prints, for every folder pooled and then for each one, how many files and grooves were
measured and why any weren't, the distribution of timing spread of the grooves with performed
timing, and the bands that cuts at its thirds, at whole milliseconds near them, and at thirds that
count each folder, or each pack, the same would make, with how many folders and packs feed each
band. With
`--excluded` it also measures the timing of the folders the assignments leave out, apart from the
rest, through a kit in which every pitch is a drum of its own, since an offset from the grid needs
no name. Nothing is written: the numbers name folders, so they stay on the screen (ADR 0007).

Run from the repository root:
    uv run python tools/calibrate.py measure
    uv run python tools/calibrate.py measure --excluded --cuts 4,7
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
"""A groove with more than this share of its notes at one offset from the grid, in ticks, is held
to it, and its timing is left out. A performance at 480 PPQ puts this many at one tick only when
its notes spread by under about 2 ticks."""
NO_TEMPO_BPM = 120.0
"""The tempo a file without one is normalized at, for its velocities only. Its timing is left
out, since its milliseconds would be made up."""
NEAR_ONE_FOLDER = 0.9
"""A band is flagged when one folder supplies at least this much of its grooves (ADR 0044)."""
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
    it. Packs tell apart sources inside one folder."""
    file: str
    """Its path under the folder of folders."""
    bars: tuple[int, int]
    """Its first bar and the bar after its last, counted from 0."""
    notes: int
    """Its notes, graces left out."""
    on_grid: float
    """The share of those notes at the groove's most common offset from the grid, in ticks: on
    it, or all shifted alike."""
    timing: Timing
    spread_ms: float | None
    feel_ms: float | None
    energy: float | None
    dynamic_range: float | None
    flat: bool
    """Every drum's normal-typed notes have at most two velocities, as programmed parts do."""


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


def measure_file(
    path: Path, relative: PurePosixPath, source: Source, on_grid: float = ON_GRID
) -> FileResult:
    """A file's grooves, or why it couldn't be measured. `on_grid` is the share of notes exactly
    on the grid above which a groove's timing is left out."""
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
        result.grooves.append(_groove(chosen, result, pack, (first, end), on_grid))
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


def _groove(
    chosen: Sequence[tuple[ScoreNote, Part]],
    result: FileResult,
    pack: str,
    bars: tuple[int, int],
    threshold: float,
) -> Groove:
    mains = [(note, part) for note, part in chosen if note.grace_of is None]
    offsets = np.array([note.offset_ms for note, _ in mains], dtype=np.float64)
    on_grid = _held(note.source.start - note.tick for note, _ in mains) / max(len(mains), 1)
    timing: Timing
    if len(mains) < MIN_NOTES:
        timing = "too_few"
    elif not result.tempo:
        timing = "no_tempo"
    elif on_grid > threshold:
        timing = "on_grid"
    else:
        timing = "performed"
    performed = timing == "performed"
    return Groove(
        folder=result.folder,
        pack=pack,
        file=result.path,
        bars=bars,
        notes=len(mains),
        on_grid=on_grid,
        timing=timing,
        spread_ms=float(np.std(offsets)) if performed else None,
        feel_ms=_feel(mains) if performed else None,
        energy=_energy([note for note, _ in chosen]),
        dynamic_range=_dynamic_range([note for note, _ in chosen]),
        flat=_flat([note for note, _ in chosen]),
    )


def _held(offsets: Iterable[int]) -> int:
    """How many notes share the most common offset from the grid, in ticks."""
    counts = Counter(offsets)
    return counts.most_common(1)[0][1] if counts else 0


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


def _flat(notes: Sequence[ScoreNote]) -> bool:
    drums = _by_drum(notes)
    return bool(drums) and all(len(set(velocities)) <= 2 for velocities in drums)


def measure(
    root: Path,
    names: Iterable[str],
    source_of: Callable[[PurePosixPath], Source | None],
    on_grid: float = ON_GRID,
) -> list[FileResult]:
    """Every file of the named folders, each read as `source_of` says for its path, or left out
    when it gives nothing."""
    results: list[FileResult] = []
    for name in names:
        for path in midi_files(root / name):
            relative = PurePosixPath(path.relative_to(root).as_posix())
            source = source_of(relative)
            if source is not None:
                results.append(measure_file(path, relative, source, on_grid))
    return results


@dataclass(frozen=True, slots=True)
class Band:
    name: str
    low: float | None
    high: float | None
    """The band holds spreads from `low` up to, but not including, `high`."""

    def holds(self, spread: float) -> bool:
        above = self.low is None or spread >= self.low
        return above and (self.high is None or spread < self.high)


BAND_NAMES = ("tight", "medium", "loose")


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
    """The thirds with each source, such as a folder or a pack, counted the same, however many
    grooves it has."""
    by_source = Counter(source(groove) for groove in grooves)
    spreads = np.array([_spread(groove) for groove in grooves], dtype=np.float64)
    weights = np.array([1 / by_source[source(groove)] for groove in grooves], dtype=np.float64)
    order = np.argsort(spreads)
    cumulative = np.cumsum(weights[order]) / weights.sum()
    picks = [float(spreads[order][np.searchsorted(cumulative, share)]) for share in (1 / 3, 2 / 3)]
    return picks[0], picks[1]


def _folder(groove: Groove) -> str:
    return groove.folder


def _pack(groove: Groove) -> str:
    return groove.pack


def _spread(groove: Groove) -> float:
    assert groove.spread_ms is not None
    return groove.spread_ms


def alternatives(
    grooves: Sequence[Groove], extra: Sequence[tuple[float, float]] = ()
) -> list[tuple[str, tuple[float, float]]]:
    """The cuts to show: the thirds, whole milliseconds near them, the thirds that count each
    folder the same, and each pack, and any given."""
    if len(grooves) < 3:
        return [(f"given {a:g} and {b:g} ms", (a, b)) for a, b in extra]
    low, high = thirds(grooves)
    whole = max(round(low), 1)
    found = [
        ("equal thirds", (low, high)),
        ("whole milliseconds near the thirds", (float(whole), float(max(round(high), whole + 1)))),
        ("thirds counting each folder the same", balanced_thirds(grooves, _folder)),
        ("thirds counting each pack the same", balanced_thirds(grooves, _pack)),
    ]
    return found + [(f"given {a:g} and {b:g} ms", (a, b)) for a, b in extra]


def report(results: Sequence[FileResult], cuts: Sequence[tuple[float, float]] = ()) -> str:
    """What `measure` prints for some files: counts, the timing spread, the bands."""
    grooves = [groove for result in results for groove in result.grooves]
    performed = [groove for groove in grooves if groove.timing == "performed"]
    lines = _counts(results, grooves)
    lines += _spreads(performed)
    lines += _velocities(grooves)
    for title, pair in alternatives(performed, cuts):
        lines += _bands(title, pair, performed)
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
        "beats: "
        f"{sum(result.ambiguous_beats > 0 for result in measured)} files",
    ]
    kinds = Counter(groove.timing for groove in grooves)
    lines.append(
        f"grooves: {len(grooves)} (windows of up to {WINDOW_BARS} bars); performed timing "
        f"{kinds['performed']}, on the grid {kinds['on_grid']}, no tempo {kinds['no_tempo']}, "
        f"fewer than {MIN_NOTES} notes {kinds['too_few']}"
    )
    tested = [groove for groove in grooves if groove.timing in ("performed", "on_grid")]
    if tested:
        shares = np.array([groove.on_grid for groove in tested], dtype=np.float64)
        counts, _ = np.histogram(shares, bins=10, range=(0.0, 1.0))
        lines.append(
            "  share of notes at one offset from the grid, grooves with a tempo, by tenths: "
            + " ".join(str(int(count)) for count in counts)
        )
    return lines


def _spreads(performed: Sequence[Groove]) -> list[str]:
    if not performed:
        return ["timing spread: no groove with performed timing"]
    spreads = np.array([_spread(groove) for groove in performed], dtype=np.float64)
    values = np.percentile(spreads, PERCENTILES).tolist()
    lines = [
        f"timing spread, ms, of {len(performed)} grooves with performed timing "
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
    feel = [groove.feel_ms for groove in performed if groove.feel_ms is not None]
    if feel:
        q1, median, q3 = np.percentile(feel, [25, 50, 75]).tolist()
        lines.append(
            f"  feel, snare and riders less kicks, ms: median {median:.2f}, "
            f"quartiles {q1:.2f} to {q3:.2f}"
        )
    return lines


def _velocities(grooves: Sequence[Groove]) -> list[str]:
    lines: list[str] = []
    for kind, label in (("performed", "performed timing"), ("on_grid", "on the grid")):
        chosen = [groove for groove in grooves if groove.timing == kind]
        energy = [groove.energy for groove in chosen if groove.energy is not None]
        spread = [groove.dynamic_range for groove in chosen if groove.dynamic_range is not None]
        if not energy or not spread:
            continue
        flat = sum(groove.flat for groove in chosen)
        lines.append(
            f"velocities, grooves with {label}: energy median {np.median(energy):.1f}, dynamic "
            f"range median {np.median(spread):.1f}, flat (each drum at most 2 velocities) "
            f"{flat} of {len(chosen)}"
        )
    return lines


def _bands(title: str, cuts: tuple[float, float], performed: Sequence[Groove]) -> list[str]:
    lines = [f"cuts, {title}: {cuts[0]:.2f} and {cuts[1]:.2f} ms"]
    for band in bands(cuts):
        mine = [groove for groove in performed if band.holds(_spread(groove))]
        by_folder = Counter(groove.folder for groove in mine)
        packs = Counter(groove.pack for groove in mine)
        median = f"{np.median([_spread(groove) for groove in mine]):.2f}" if mine else "-"
        largest = (
            f", largest pack {100 * packs.most_common(1)[0][1] / len(mine):.0f}%" if mine else ""
        )
        flag = ""
        if mine and by_folder.most_common(1)[0][1] >= NEAR_ONE_FOLDER * len(mine):
            folder, count = by_folder.most_common(1)[0]
            flag = f"  <- {'one folder alone' if count == len(mine) else 'nearly one folder'}: "
            flag += f"{folder} {100 * count / len(mine):.0f}%"
        lines.append(
            f"  {band.name:<6} {len(mine):>6} grooves, {len(by_folder)} folders, {len(packs)} packs"
            f"{largest}, median spread {median} ms{flag}"
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
        "--on-grid",
        type=float,
        default=ON_GRID,
        metavar="SHARE",
        help="leave out the timing of a groove with more than this share of its notes at one "
        f"offset from the grid (default {ON_GRID})",
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

    results = measure(args.root, names, assigned, args.on_grid)
    print("== every assigned folder")
    print(report(results, args.cuts))
    for name in names:
        mine = [result for result in results if result.folder == name]
        if mine:
            print(f"\n== {name}")
            print(report(mine, args.cuts))
    if args.excluded:
        neutral = Source(every_pitch_kit())

        def left_out(relative: PurePosixPath) -> Source | None:
            found = assignments.find(relative)
            return neutral if found is not None and found.kit is None else None

        apart = measure(args.root, names, left_out, args.on_grid)
        print("\n== the folders left out, timing only, every pitch a drum of its own")
        print(report(apart, args.cuts))
        for name in names:
            mine = [result for result in apart if result.folder == name]
            if mine:
                print(f"\n== {name}, left out")
                print(report(mine, args.cuts))
    print(f"measured in {time.perf_counter() - started:.1f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
