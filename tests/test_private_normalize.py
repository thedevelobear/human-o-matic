"""Known jitter added to the performed MIDI in `private/midi/` that is already on a grid, and its
grid positions recovered. The folder is never committed (ADR 0007), and the test skips when it
is missing or holds no such file."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from human_o_matic.decisions import DecisionRequired
from human_o_matic.midi.io import MidiSong, read_midi
from human_o_matic.midi.tempo import TempoMap, tempo_map
from human_o_matic.midi.tracks import choose_drum_track
from human_o_matic.normalize.pipeline import normalize
from map_files import articulation, load_kit

PRIVATE_MIDI = Path(__file__).resolve().parents[1] / "private" / "midi"
ON_GRID = 0.99
"""A file is on a grid when this share of its drum notes is on a 32nd or 16th triplet point."""
JITTER_SD_MS = 4.0
MAX_JITTER_MS = 12.0
FALLBACK_BPM = 120.0
"""The tempo of a file that has none, which only sets how far the jitter moves its ticks."""


def midi_files() -> list[Path]:
    folders = sorted(PRIVATE_MIDI.iterdir()) if PRIVATE_MIDI.is_dir() else []
    return [
        path
        for folder in folders
        if folder.is_dir()
        # A link is resolved first, since a glob doesn't follow one to a directory.
        for path in sorted(folder.resolve().rglob("*"))
        if path.suffix.lower() in (".mid", ".midi")
    ]


def on_grid(ticks: np.ndarray, ppq: int) -> np.ndarray:
    return (ticks % (ppq // 8) == 0) | (ticks % (ppq // 6) == 0)


def jittered(song: MidiSong, track: int, tempos: TempoMap, seed: int) -> MidiSong:
    """The song with each stroke of its drum track, a pitch at a tick, moved by jitter."""
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    strokes: dict[tuple[int, int], int] = {}
    for note in song.notes:
        if note.track == track:
            strokes.setdefault((note.start, note.pitch), len(strokes))
    jitter = np.clip(rng.normal(0, JITTER_SD_MS, len(strokes)), -MAX_JITTER_MS, MAX_JITTER_MS)
    starts = np.array([start for start, _ in strokes], dtype=np.int64)
    moved = np.maximum(np.rint(tempos.ms_to_ticks(tempos.ticks_to_ms(starts) + jitter)), 0)
    to = dict(zip(strokes, moved.astype(int).tolist(), strict=True))
    notes = [
        replace(note, start=(start := to[note.start, note.pitch]), end=start + 1)
        if note.track == track
        else note
        for note in song.notes
    ]
    notes.sort(key=lambda note: (note.start, note.track, note.order))
    return replace(song, notes=tuple(notes))


@pytest.mark.private
def test_jittered_files_on_a_grid_come_back_to_it(tmp_path: Path) -> None:
    # Every pitch is a drum of its own, so the test needs no library's map.
    kit = load_kit(
        tmp_path, *(articulation(f"sample.{pitch + 1}.hit", pitch) for pitch in range(128))
    )
    found = total = files = 0
    for path in midi_files():
        song = read_midi(path)
        track = choose_drum_track(song).track
        drums = [note for note in song.notes if note.track == track]
        ticks = np.array([note.start for note in drums], dtype=np.int64)
        if not drums or on_grid(ticks, song.ppq).mean() < ON_GRID:
            continue
        try:
            bpm = None
            tempos = tempo_map(song)
        except DecisionRequired:
            bpm = FALLBACK_BPM
            tempos = tempo_map(song, bpm=bpm)
        files += 1
        was = {(note.track, note.order): note.start for note in drums}
        moved = jittered(song, track, tempos, seed=files)
        for note in normalize(moved, kit, track=track, bpm=bpm).score.notes:
            start = was[note.source.track, note.source.order]
            if on_grid(np.array([start]), song.ppq)[0]:
                total += 1
                found += note.tick == start
    if not files:
        pytest.skip("no MIDI on a grid in private/midi/")

    assert found / total >= 0.99
