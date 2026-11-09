"""Pitch statistics for each folder of performed MIDI, read through a built-in kit.

A folder's notes can disagree with its library's map, so each folder is checked against the map
before its grooves are used. For every pitch of a folder's drum tracks this prints how many notes
it has and their share, how many files hold it, its velocities, where it falls in the bar, and
what the kit reads it as. The folder's header says how many notes the kit reads, and which pitches
it leaves unmapped.

The columns:
- `beat`: the share of the pitch's notes within a 12th of a quarter note of a beat of the bar;
- `back`: the share on beats 2 and 4 of a 4/4 bar, where a backbeat falls;
- `down`: the share on the bar's first beat;
- `gap`: the median distance to the next note of the pitch in the same file, in 16ths;
- `reads as`: the kit's articulation, several joined by `|` with `(controller)` when a controller
  value decides among them or shapes it, or `unmapped`.

Folders are found by listing `private/midi/`, and the kit that reads each comes from
`private/data/midi-folders.toml` (`midi_folders`), unless `--map` names one. Files that the
assignments put under another entry, a subfolder left out or read through another kit, are left
out of the folder's report, and its header counts them.

Run from the repository root:
    uv run python tools/infer_map.py                  every folder
    uv run python tools/infer_map.py NAME --map KIT   one folder, through a built-in kit
    uv run python tools/infer_map.py NAME --split     a report for each subfolder
"""

import argparse
import sys
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import numpy as np

from human_o_matic.decisions import DecisionRequired
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiFileError, Note, read_midi
from human_o_matic.midi.tempo import FOUR_FOUR, TimeSignatureMap, time_signature_map
from human_o_matic.midi.tracks import choose_drum_track
from midi_folders import (
    ASSIGNMENTS,
    MIDI,
    Assignment,
    AssignmentError,
    Assignments,
    folders,
    midi_files,
)

BEAT_TOLERANCE = 1 / 12
"""How far from a beat a note may be, in quarter notes, and still count as on it."""
UNMAPPED = "unmapped"
CONTROLLER = " (controller)"
EXIT_USAGE = 2
HEADER = (
    f"{'pitch':>5} {'notes':>7} {'share':>7} {'files':>5}  {'velocity min q1 med q3 max':>26} "
    f"{'beat':>5} {'back':>5} {'down':>5} {'gap':>5}  reads as"
)


@dataclass(slots=True)
class PitchStats:
    """One pitch's notes in a folder."""

    pitch: int
    velocities: list[int] = field(default_factory=list[int])
    files: set[int] = field(default_factory=set[int])
    reads: Counter[str] = field(default_factory=Counter[str])
    on_beat: int = 0
    backbeat: int = 0
    downbeat: int = 0
    gaps: list[float] = field(default_factory=list[float])
    """Distances to the next note of the pitch in the same file, in 16ths."""

    @property
    def notes(self) -> int:
        return len(self.velocities)


@dataclass(slots=True)
class FolderReport:
    """A folder's pitch statistics, and how a kit reads its notes."""

    name: str
    kit: DrumKit | None
    excluded: str | None = None
    """Why the assignments leave the folder out, when they do."""
    files: int = 0
    skipped: Counter[str] = field(default_factory=Counter[str])
    """Files that couldn't be read, by why."""
    elsewhere: Counter[str] = field(default_factory=Counter[str])
    """Files left out because another entry of the assignments covers them, by its key."""
    channels: Counter[int] = field(default_factory=Counter[int])
    """Notes per channel, 1 to 16."""
    pitches: dict[int, PitchStats] = field(default_factory=dict[int, PitchStats])

    @property
    def notes(self) -> int:
        return sum(stats.notes for stats in self.pitches.values())

    def count(self, kind: str) -> int:
        """Notes the kit reads as one articulation (`mapped`), as one a controller decides or
        shapes (`controller`), or as none (`unmapped`)."""
        return sum(
            count
            for stats in self.pitches.values()
            for reading, count in stats.reads.items()
            if _kind(reading) == kind
        )

    def unmapped(self) -> dict[int, int]:
        """Each pitch with unmapped notes, and how many."""
        return {
            pitch: stats.reads[UNMAPPED]
            for pitch, stats in sorted(self.pitches.items())
            if stats.reads[UNMAPPED]
        }


def _kind(reading: str) -> str:
    if reading == UNMAPPED:
        return "unmapped"
    return "controller" if reading.endswith(CONTROLLER) else "mapped"


def reading(kit: DrumKit, note: Note) -> str:
    """What the kit reads a note as."""
    matches = kit.read(note.pitch, note.velocity, note.channel)
    if not matches:
        return UNMAPPED
    names = "|".join(match.articulation.name for match in matches)
    if len(matches) == 1 and matches[0].binding.cc is None:
        return names
    return names + CONTROLLER


def scan(
    name: str,
    files: Iterable[tuple[Path, Assignment | None]],
    kit: DrumKit | None,
    own: Assignment | None,
    *,
    every_file: bool = False,
) -> FolderReport:
    """The report on `files`, each with what the assignments say of it. A file whose assignment
    isn't the folder's own, `own`, is counted as elsewhere, unless `every_file` is set."""
    report = FolderReport(name=name, kit=kit, excluded=own.exclude if own else None)
    for path, assignment in files:
        if not every_file and _key(assignment) != _key(own):
            report.elsewhere[_key(assignment) or "(no entry)"] += 1
            continue
        try:
            song = read_midi(path)
            drums = choose_drum_track(song).track
        except (OSError, MidiFileError) as error:
            report.skipped[f"not read: {error}"] += 1
            continue
        except DecisionRequired:
            report.skipped["the drum track is unclear"] += 1
            continue
        report.files += 1
        _add(
            report,
            report.files,
            [note for note in song.notes if note.track == drums],
            time_signature_map(song),
            song.ppq,
        )
    return report


def _key(assignment: Assignment | None) -> str | None:
    return assignment.key if assignment else None


def _add(
    report: FolderReport, file: int, notes: Sequence[Note], signatures: TimeSignatureMap, ppq: int
) -> None:
    starts: dict[int, list[int]] = {}
    for note in notes:
        stats = report.pitches.setdefault(note.pitch, PitchStats(note.pitch))
        stats.velocities.append(note.velocity)
        stats.files.add(file)
        report.channels[note.channel + 1] += 1
        if report.kit is not None:
            stats.reads[reading(report.kit, note)] += 1
        starts.setdefault(note.pitch, []).append(note.start)
        signature = signatures.signature_at(note.start)
        position = signatures.position(note.start)
        beat = round(position.beat)
        quarters = abs(position.beat - beat) * 4 / signature.denominator
        if quarters <= BEAT_TOLERANCE:
            stats.on_beat += 1
            stats.downbeat += beat % signature.numerator == 0
            stats.backbeat += signature == FOUR_FOUR and beat in (1, 3)
    sixteenth = ppq / 4
    for pitch, ticks in starts.items():
        ordered = np.sort(np.array(ticks, dtype=np.int64))
        report.pitches[pitch].gaps.extend((np.diff(ordered) / sixteenth).tolist())


def format_report(report: FolderReport) -> str:
    """The report as text: a header, then a line per pitch."""
    total = report.notes
    lines = [f"== {report.name}"]
    files = f"{report.files} files read"
    if report.skipped:
        files += f", {sum(report.skipped.values())} not: " + "; ".join(
            f"{reason} ({count})" for reason, count in sorted(report.skipped.items())
        )
    channels = ", ".join(
        f"{channel} ({count})" for channel, count in sorted(report.channels.items())
    )
    lines.append(f"{files}; {total} notes; channels {channels or 'none'}")
    for key, count in sorted(report.elsewhere.items()):
        lines.append(f"left out: {count} files under {key}, which has an entry of its own")
    if report.excluded is not None:
        lines.append(f"excluded: {report.excluded}")
    if report.kit is None:
        lines.append("no map: give --map, or assign the folder")
    elif total:
        mapped, controller = report.count("mapped"), report.count("controller")
        unmapped = report.unmapped()
        missing = sum(unmapped.values())
        lines.append(
            f"through {report.kit.ref}: {mapped} read ({_share(mapped, total)}), "
            f"{controller} by a controller value ({_share(controller, total)}), "
            f"{missing} unmapped ({_share(missing, total)})"
            + (": " + ", ".join(f"{p} ({n})" for p, n in unmapped.items()) if unmapped else "")
        )
    if total:
        lines.append(HEADER)
        lines.extend(
            _row(stats, total, report.kit is not None)
            for _, stats in sorted(report.pitches.items())
        )
    return "\n".join(lines)


def _row(stats: PitchStats, total: int, with_kit: bool) -> str:
    low, q1, median, q3, high = np.percentile(stats.velocities, [0, 25, 50, 75, 100]).tolist()
    gap = f"{float(np.median(stats.gaps)):5.1f}" if stats.gaps else f"{'-':>5}"
    reads = " / ".join(
        reading if len(stats.reads) == 1 else f"{reading} ({count})"
        for reading, count in stats.reads.most_common()
    )
    return (
        f"{stats.pitch:>5} {stats.notes:>7} {_share(stats.notes, total):>7} {len(stats.files):>5}  "
        f"{low:>10.0f} {q1:>3.0f} {median:>3.0f} {q3:>3.0f} {high:>3.0f} "
        f"{_share(stats.on_beat, stats.notes, 0):>5} {_share(stats.backbeat, stats.notes, 0):>5} "
        f"{_share(stats.downbeat, stats.notes, 0):>5} {gap}  {reads if with_kit else '-'}"
    )


def _share(part: int, whole: int, digits: int = 2) -> str:
    return f"{100 * part / whole:.{digits}f}%" if whole else "-"


def reports(
    root: Path,
    names: Sequence[str],
    assignments: Assignments,
    kit: DrumKit | None,
    *,
    split: bool = False,
) -> list[FolderReport]:
    """A report per folder named, or per folder in `root` when none is, and with `split`, per
    folder inside each instead. Raises `ValueError` for a name that isn't a folder in `root`."""
    chosen: list[PurePosixPath] = []
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not (root / path).is_dir():
            raise ValueError(f"{name!r} is not a folder in {root}")
        chosen.append(path)
    if not names:
        chosen = [PurePosixPath(folder.name) for folder in folders(root)]
    found: list[FolderReport] = []
    for path in chosen:
        parts = _parts(root, path) if split else [(path, list(midi_files(root / path)))]
        for part, files in parts:
            own = assignments.find(part)
            reading_kit = kit if kit is not None else (own.kit if own else None)
            assigned = [
                (file, assignments.find(PurePosixPath(file.relative_to(root).as_posix())))
                for file in files
            ]
            found.append(scan(str(part), assigned, reading_kit, own, every_file=kit is not None))
    return found


def _parts(root: Path, path: PurePosixPath) -> list[tuple[PurePosixPath, list[Path]]]:
    """Each folder inside a folder with its files, after the folder itself with the files
    directly in it, when it has any."""
    top = [file for file in midi_files(root / path) if file.parent == root / path]
    inside = [(path / sub.name, list(midi_files(sub))) for sub in folders(root / path)]
    return ([(path, top)] if top else []) + inside


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pitch statistics for each folder of performed MIDI, read through a kit."
    )
    parser.add_argument(
        "folders", nargs="*", help="folders in the folder of folders; every one when none is given"
    )
    parser.add_argument(
        "--map",
        metavar="LIBRARY[/KIT]",
        help="read every file through this built-in kit, instead of the assigned one",
    )
    parser.add_argument(
        "--split", action="store_true", help="a report for each folder inside the folders instead"
    )
    parser.add_argument("--root", type=Path, default=MIDI, help="the folder of folders")
    parser.add_argument(
        "--assignments",
        type=Path,
        default=ASSIGNMENTS,
        help="the file saying which kit reads which folder",
    )
    args = parser.parse_args(argv)
    try:
        kit = find_kit(args.map) if args.map else None
        assignments = Assignments.read(args.assignments)
        started = time.perf_counter()
        found = reports(args.root, args.folders, assignments, kit, split=args.split)
    except (KeyError, AssignmentError, ValueError) as error:
        print(f"error: {error.args[0] if isinstance(error, KeyError) else error}", file=sys.stderr)
        return EXIT_USAGE
    print("\n\n".join(format_report(report) for report in found))
    files = sum(report.files for report in found)
    notes = sum(report.notes for report in found)
    print(
        f"{len(found)} folders, {files} files, {notes} notes in "
        f"{time.perf_counter() - started:.1f} s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
