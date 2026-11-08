"""Normalizing a song end to end, with MIDI files built in code and the shipped General MIDI map.

The exit test of M1 adds known jitter to quantized grooves and recovers their grid positions.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from human_o_matic.decisions import DecisionRequired
from human_o_matic.maps.convert import DROP
from human_o_matic.maps.loader import built_in_maps
from human_o_matic.midi.io import MidiSong, read_midi
from human_o_matic.midi.tempo import TempoMap
from human_o_matic.normalize.grid import GRIDS, Grid
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.pipeline import normalize
from midi_files import MidoMessage, end, name, off, on, save, tempo, track

GM = built_in_maps().kit("gm")
PPQ = 960
KICK, SNARE, HAT, TOM_1, TOM_2 = 36, 38, 42, 50, 48
MAX_JITTER_MS = 12.0
"""The plan's cap on timing offsets."""


def drum_file(path: Path, notes: list[tuple[int, int, int]], bpm: float | None = 120) -> MidiSong:
    """A one-track file of (tick, pitch, velocity) notes on channel 10, at 960 PPQ, read back."""
    items: list[tuple[int, int, MidoMessage]] = [(0, 0, name("Drums"))]
    if bpm is not None:
        items.append((0, 0, tempo(bpm)))
    for tick, pitch, velocity in notes:
        items.extend([(tick, 2, on(pitch, velocity)), (tick + 10, 1, off(pitch))])
    items.sort(key=lambda item: (item[0], item[1]))
    messages = [(tick, message) for tick, _, message in items]
    return read_midi(save(path / "drums.mid", track(*messages, (messages[-1][0], end())), ppq=PPQ))


def test_every_drum_note_is_in_the_score_once(tmp_path: Path) -> None:
    notes = [(beat * PPQ, KICK if beat % 2 == 0 else SNARE, 110) for beat in range(8)]
    notes += [(eighth * PPQ // 2, HAT, 90) for eighth in range(16)]
    song = drum_file(tmp_path, notes)

    result = normalize(song, GM)
    score = result.score

    assert result.complete
    assert sorted(note.source_index for note in score.notes) == list(range(len(song.notes)))
    assert all(note.source == song.notes[note.source_index] for note in score.notes)
    assert [(n.tick, n.source_index) for n in score.notes] == sorted(
        (n.tick, n.source_index) for n in score.notes
    )
    assert {note.articulation for note in score.notes} == {
        "kick.hit",
        "snare.center",
        "hat.closed",
    }
    assert (score.kit, score.track) == ("gm/default", 0)
    assert score.position(score.notes[-1].tick).bar == 1


def test_the_score_keeps_bars_beats_and_grids(tmp_path: Path) -> None:
    triplets = [(4 * PPQ + n * PPQ // 3, HAT, 100) for n in range(3)]
    song = drum_file(tmp_path, [(0, KICK, 100), (PPQ // 4, HAT, 100), *triplets])

    score = normalize(song, GM).score

    assert [(beat.bar, beat.beat, beat.grid) for beat in score.beats] == [
        (0, 0, "16th"),
        (1, 0, "8th_triplet"),
    ]
    assert [note.grid for note in score.notes] == ["16th", "16th", *["8th_triplet"] * 3]
    assert [score.beats[note.beat].bar for note in score.notes] == [0, 0, 1, 1, 1]


def test_a_flam_stays_linked_in_the_score(tmp_path: Path) -> None:
    # At 120 BPM a tick is 0.52 ms: the grace is 25 ms early and the main 2 ms late.
    song = drum_file(tmp_path, [(0, KICK, 110), (PPQ - 48, SNARE, 40), (PPQ + 4, SNARE, 120)])

    score = normalize(song, GM).score

    kick, grace, main = score.notes
    assert grace.grace_of == main.source_index
    assert main.grace_of is None
    assert (grace.tick, main.tick) == (PPQ - 52, PPQ)
    assert grace.grid == main.grid
    assert score.graces(main) == (grace,)
    assert score.graces(kick) == ()


def test_the_requests_come_with_the_score_in_order(tmp_path: Path) -> None:
    # An unmapped note, a beat that could be 16ths or 8th triplets, and one velocity.
    notes = [(0, 99, 100), (0, KICK, 100), (PPQ + 340, SNARE, 100), (2 * PPQ, KICK, 100)]
    song = drum_file(tmp_path, notes)

    result = normalize(song, GM)

    assert [request.kind for request in result.decisions] == [
        "unmapped_notes",
        "ambiguous_bars",
        "hit_types",
    ]
    assert not result.complete
    assert [song.notes[index].pitch for index in result.pending] == [99]
    assert len(result.score.notes) == 3
    assert result.score.ambiguous == (result.score.beats[1],)


def test_answers_settle_the_requests(tmp_path: Path) -> None:
    notes = [(0, 99, 100), (0, KICK, 100), (PPQ + 340, SNARE, 40), (2 * PPQ, SNARE, 110)]
    song = drum_file(tmp_path, notes)
    grids: dict[tuple[int, int], Grid] = {(0, 1): "8th_triplet"}
    hit_types = {"kick": HitTypeBounds(), "snare": HitTypeBounds(soft_below=64)}

    result = normalize(song, GM, unmapped={99: DROP}, grids=grids, hit_types=hit_types)

    assert result.decisions == ()
    assert result.complete
    assert result.dropped == (0,)
    snare = [(note.tick, note.hit_type) for note in result.score.notes if note.family == "snare"]
    assert snare == [(PPQ + 320, "soft"), (2 * PPQ, "normal")]
    assert {note.hit_type_confidence for note in result.score.notes} == {"high"}


def test_notes_read_through_low_confidence_names_are_counted(tmp_path: Path) -> None:
    kit = built_in_maps().kit("ezdrummer-3")
    song = drum_file(tmp_path, [(0, KICK, 100), (PPQ, SNARE, 100), (2 * PPQ, SNARE, 100)])

    result = normalize(song, kit)

    counted = {entry.articulation: entry.count for entry in result.low_confidence}
    expected: dict[str, int] = {}
    for note in result.score.notes:
        if kit.articulation(note.articulation).confidence == "low":
            expected[note.articulation] = expected.get(note.articulation, 0) + 1
    assert counted == expected
    assert counted


def test_a_missing_tempo_is_asked_for_and_a_given_one_is_used(tmp_path: Path) -> None:
    song = drum_file(tmp_path, [(0, KICK, 100)], bpm=None)

    with pytest.raises(DecisionRequired) as raised:
        normalize(song, GM)

    assert raised.value.request.kind == "tempo"
    assert normalize(song, GM, bpm=100).score.tempos.bpm(0) == pytest.approx(100)


def test_normalizing_is_deterministic(tmp_path: Path) -> None:
    rng = np.random.default_rng(np.random.SeedSequence(11))
    notes = [
        (int(tick), int(rng.choice([KICK, SNARE, HAT, TOM_1])), int(rng.integers(20, 128)))
        for tick in rng.integers(0, 32 * PPQ, 400)
    ]
    song = drum_file(tmp_path, notes)

    first, second = normalize(song, GM), normalize(song, GM)

    assert first.score.notes == second.score.notes
    assert first.score.beats == second.score.beats
    assert first.decisions == second.decisions


# The exit test: known jitter added to quantized grooves, and their grid positions recovered.


@dataclass(frozen=True)
class Groove:
    song: MidiSong
    grid_ticks: dict[int, int]
    """The quantized tick of each note, by the place of its note-on in the track."""


def beat(grid: Grid, number: int, rng: np.random.Generator) -> list[tuple[float, int]]:
    """One beat of a groove on `grid`, as (place in the beat, pitch), each pair once."""
    backbeat = SNARE if number % 2 else KICK
    match grid:
        case "16th":
            notes = [(k / 4, HAT) for k in range(4)] + [(0, backbeat)]
            if rng.random() < 0.5:
                notes.append((int(rng.integers(1, 4)) / 4, KICK))
        case "8th_triplet":
            notes = [(0, HAT), (2 / 3, HAT), (0, backbeat)]
            if rng.random() < 0.5:
                notes.append((1 / 3, HAT))
            if rng.random() < 0.5:
                notes.append((2 / 3, KICK))
        case "16th_triplet":
            fill = [SNARE, TOM_1, TOM_2][int(rng.integers(3))]
            notes = [(k / 6, fill if k % 2 == 0 or rng.random() < 0.7 else SNARE) for k in range(6)]
            notes.append((0, KICK))
        case "32nd":
            notes = [(0, HAT), (0.5, HAT), (0, KICK), (1 / 8, KICK)]
            if rng.random() < 0.5:
                notes += [(0.5, KICK), (5 / 8, KICK)]
            notes.append((0, SNARE) if number % 2 else (0.75, SNARE))
    return sorted(set(notes))


def jittered_groove(
    path: Path, bpms: list[float], jitter_sd: float, seed: int, bars: int = 32
) -> Groove:
    """Bars of 4/4 whose beats each take a random grid, at tempos that change evenly through the
    song, with each note moved by jitter from a normal spread, capped at the plan's 12 ms."""
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    change_every = bars // len(bpms) * 4 * PPQ
    starts = [n * change_every for n in range(len(bpms))]
    tempos = TempoMap(PPQ, starts, [60_000_000 / bpm for bpm in bpms])
    quantized = [
        (number * PPQ + round(at * PPQ), pitch)
        for number in range(bars * 4)
        for at, pitch in beat(GRIDS[int(rng.integers(len(GRIDS)))], number % 4, rng)
    ]
    jitter = np.clip(rng.normal(0, jitter_sd, len(quantized)), -MAX_JITTER_MS, MAX_JITTER_MS)
    ticks = np.array([tick for tick, _ in quantized])
    played = np.maximum(np.rint(tempos.ms_to_ticks(tempos.ticks_to_ms(ticks) + jitter)), 0)

    # (tick, rank, message, quantized tick of a note-on): tempos, then note-offs, then note-ons.
    items: list[tuple[int, int, MidoMessage, int | None]] = [
        (start, 0, tempo(bpm), None) for start, bpm in zip(starts, bpms, strict=True)
    ]
    for (grid_tick, pitch), start in zip(quantized, played.astype(int).tolist(), strict=True):
        items.extend([(start, 2, on(pitch), grid_tick), (start + 10, 1, off(pitch), None)])
    items.sort(key=lambda item: (item[0], item[1]))
    messages = [(tick, message) for tick, _, message, _ in items]
    data = track(*messages, (messages[-1][0], end()))
    song = read_midi(save(path / f"groove-{seed}.mid", data, ppq=PPQ))
    # A note's `order` is its note-on's place in the track.
    grid_ticks = {order: item[3] for order, item in enumerate(items) if item[3] is not None}
    return Groove(song=song, grid_ticks=grid_ticks)


def recovered(path: Path, bpms: list[float], jitter_sd: float, seeds: int) -> tuple[int, int]:
    """How many notes are back on their grid positions, of how many."""
    found = total = 0
    for seed in range(seeds):
        groove = jittered_groove(path, bpms, jitter_sd, seed)
        for note in normalize(groove.song, GM).score.notes:
            total += 1
            found += note.tick == groove.grid_ticks[note.source.order]
    return found, total


@pytest.mark.parametrize(
    "bpms",
    [[60], [90], [120], [160], [200], [240], [70, 140, 100, 180]],
    ids=lambda bpms: "-".join(f"{bpm:g}" for bpm in bpms) + "bpm",
)
def test_jittered_grooves_come_back_to_their_grid(tmp_path: Path, bpms: list[float]) -> None:
    # Jitter with a spread of 4 ms, the plan's default tightness, capped at 12 ms.
    found, total = recovered(tmp_path, bpms, jitter_sd=4.0, seeds=4)

    assert total > 2500
    assert found / total >= 0.99


@pytest.mark.parametrize("bpm", [60, 120, 160])
def test_looser_grooves_come_back_at_moderate_tempos(tmp_path: Path, bpm: float) -> None:
    # A spread of 6 ms, a loose drummer. Above about 160 BPM a 32nd and a 16th triplet point are
    # too close to tell apart beat by beat at this spread, and recovery falls below 99%.
    found, total = recovered(tmp_path, [bpm], jitter_sd=6.0, seeds=4)

    assert found / total >= 0.99
