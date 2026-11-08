"""Round trips of the library MIDI, read in place (ADR 0007). Skips when the files are missing."""

from contextlib import suppress
from dataclasses import replace
from pathlib import Path

import pytest

from human_o_matic.decisions import DecisionRequired
from human_o_matic.midi.io import midi_bytes, read_midi, working_ppq
from human_o_matic.midi.tempo import tempo_map, time_signature_map
from human_o_matic.midi.tracks import choose_drum_track
from midi_files import Timed, messages, scaled

# The library MIDI folders of the plan's Appendix B.
LIBRARIES = (
    Path("/Users/Shared/GetGood Drums - P V Matt Halpern Signature Pack/MIDIFiles"),
    Path("/Users/Shared/Bogren Digital - Krimh Drums/MIDIfiles"),
    Path("/Users/Shared/GetGood Drums - Modern and Massive Pack/Modern & Massive/MIDIFiles"),
    Path.home() / "Documents/SleepTokenII/MIDI Files",
    Path("/Users/Shared/SoundBlind Drums - Counterkit/MIDI"),
    Path("/Users/Shared/Drum Lab Library/MIDI Files"),
    Path("/Users/Shared/Krimh Drums Free/MIDIfiles"),
)
SAMPLE_SIZE = 50


def library_sample(size: int = SAMPLE_SIZE) -> list[Path]:
    """About `size` files, shared evenly among the libraries present and spread evenly through
    each one's sorted file list, so the same files are chosen on every run."""
    libraries = [
        files
        for root in LIBRARIES
        if root.is_dir()
        and (files := sorted(p for p in root.rglob("*") if p.suffix.lower() in (".mid", ".midi")))
    ]
    sample: list[Path] = []
    for index, files in enumerate(libraries):
        count = min(size // len(libraries) + (index < size % len(libraries)), len(files))
        step = (len(files) - 1) / (count - 1) if count > 1 else 0
        sample.extend(files[round(position * step)] for position in range(count))
    return sample


def note_offs_as_note_off(tracks: list[Timed]) -> list[Timed]:
    """A note-on at velocity 0 is written as a note-off at velocity 64, which means the same."""
    return [[(tick, _as_note_off(raw)) for tick, raw in timed] for timed in tracks]


def _as_note_off(raw: tuple[int, ...]) -> tuple[int, ...]:
    if raw[0] & 0xF0 == 0x90 and raw[2] == 0:
        return (0x80 | raw[0] & 0x0F, raw[1], 64)
    return raw


@pytest.mark.library
def test_library_files_round_trip(tmp_path: Path) -> None:
    sample = library_sample()
    if not sample:
        pytest.skip("the library MIDI is not on this machine")

    failures: list[str] = []
    for index, path in enumerate(sample):
        song = read_midi(path)
        out = tmp_path / f"{index}.mid"
        out.write_bytes(midi_bytes(song))
        factor = working_ppq(song.source_ppq) // song.source_ppq
        expected = scaled(note_offs_as_note_off(messages(path.read_bytes())), factor)
        if messages(out.read_bytes()) != expected:
            failures.append(f"{path}: messages differ")
        if replace(read_midi(out), source_ppq=song.source_ppq) != song:
            failures.append(f"{path}: song differs")
        # A missing tempo or an unclear drum track is a question, not a failure.
        with suppress(DecisionRequired):
            tempo_map(song)
        with suppress(DecisionRequired):
            choose_drum_track(song)
        time_signature_map(song)

    assert not failures, "\n".join(failures)
