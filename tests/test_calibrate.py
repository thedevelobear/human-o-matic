"""`tools/calibrate.py`'s measuring, on grooves built in `tmp_path`."""

from pathlib import Path, PurePosixPath

import numpy as np
import pytest

from calibrate import (
    MIN_NOTES,
    WINDOW_BARS,
    Groove,
    alternatives,
    balanced_thirds,
    bands,
    every_pitch_kit,
    main,
    measure,
    measure_file,
    report,
    thirds,
)
from human_o_matic.maps.kit import DrumKit
from map_files import articulation, load_kit
from midi_files import MidoMessage, end, name, off, on, save, signature, tempo, track

PPQ = 480
BPM = 120.0
MS_PER_TICK = 60_000 / (BPM * PPQ)
BAR = 4 * PPQ
KICK, SNARE, HAT, ODD = 36, 38, 42, 99
SPREAD = (-9, -6, -3, 0, 3, 6, 9, -7, 1, 7)
"""Ten offsets in ticks, each a tenth of the notes, so no offset holds a fifth of them."""


def beat_notes(bars: int, first_bar: int = 1) -> list[tuple[int, int]]:
    """(tick, pitch) of a rock beat: 8th-note hats, kick on 1 and 3, snare on 2 and 4."""
    notes: list[tuple[int, int]] = []
    for bar in range(first_bar, first_bar + bars):
        for eighth in range(8):
            tick = bar * BAR + eighth * PPQ // 2
            notes.append((tick, HAT))
            if eighth in (0, 4):
                notes.append((tick, KICK))
            if eighth in (2, 6):
                notes.append((tick, SNARE))
    return notes


def write(
    path: Path,
    notes: list[tuple[int, int]],
    offsets: list[int] | None = None,
    velocities: list[int] | None = None,
    *,
    with_tempo: bool = True,
) -> Path:
    """A one-track file of the notes, each moved by its offset in ticks."""
    items: list[tuple[int, MidoMessage]] = [(0, signature(4, 4))]
    if with_tempo:
        items.append((0, tempo(BPM)))
    for index, (tick, pitch) in enumerate(notes):
        start = tick + (offsets[index] if offsets else 0)
        velocity = velocities[index] if velocities else 100
        items += [(start, on(pitch, velocity)), (start + PPQ // 8, off(pitch))]
    items.sort(key=lambda item: item[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    return save(path, track(*items, (items[-1][0], end())), ppq=PPQ)


def cycle(values: tuple[int, ...], count: int) -> list[int]:
    return [values[index % len(values)] for index in range(count)]


@pytest.fixture
def kit(tmp_path: Path) -> DrumKit:
    maps = tmp_path / "maps"
    maps.mkdir()
    return load_kit(
        maps,
        articulation("kick.hit", KICK),
        articulation("snare.center", SNARE),
        articulation("hat.closed", HAT),
    )


def measured(path: Path, kit: DrumKit) -> list[Groove]:
    result = measure_file(path, PurePosixPath("f", path.name), kit)
    assert result.problem is None
    return result.grooves


def test_a_performed_groove_has_the_spread_and_feel_of_its_offsets(
    tmp_path: Path, kit: DrumKit
) -> None:
    notes = beat_notes(4)
    offsets = cycle(SPREAD, len(notes))
    # The snare plays 4 ticks later than its offset says, the kick 2 earlier.
    offsets = [
        offset + (4 if pitch == SNARE else -2 if pitch == KICK else 0)
        for offset, (_, pitch) in zip(offsets, notes, strict=True)
    ]
    velocities = [90 + index % 23 for index in range(len(notes))]

    (groove,) = measured(write(tmp_path / "played.mid", notes, offsets, velocities), kit)

    ms = np.array(offsets) * MS_PER_TICK
    pitches = [pitch for _, pitch in notes]
    upper = [value for value, pitch in zip(ms, pitches, strict=True) if pitch != KICK]
    kicks = [value for value, pitch in zip(ms, pitches, strict=True) if pitch == KICK]
    assert groove.timing == "performed"
    assert groove.notes == len(notes) == 48
    assert groove.spread_ms == pytest.approx(float(np.std(ms)), abs=1e-6)
    assert groove.feel_ms == pytest.approx(float(np.mean(upper) - np.mean(kicks)), abs=1e-6)
    assert groove.energy is not None
    assert not groove.flat
    assert groove.on_grid <= 0.2


def test_a_quantized_groove_is_on_the_grid_and_keeps_its_velocities(
    tmp_path: Path, kit: DrumKit
) -> None:
    (groove,) = measured(write(tmp_path / "grid.mid", beat_notes(4)), kit)

    assert (groove.timing, groove.on_grid, groove.spread_ms) == ("on_grid", 1.0, None)
    assert (groove.energy, groove.dynamic_range, groove.flat) == (100.0, 0.0, True)


def test_a_quantized_groove_shifted_as_a_whole_is_on_the_grid_too(
    tmp_path: Path, kit: DrumKit
) -> None:
    notes = beat_notes(4)
    # Every note 7 ticks late, but for one in ten, so none is on the grid itself.
    offsets = cycle((7, 7, 7, 7, 7, 7, 7, 7, 7, 3), len(notes))

    (groove,) = measured(write(tmp_path / "shifted.mid", notes, offsets), kit)

    assert groove.timing == "on_grid"
    assert groove.on_grid == pytest.approx(0.9, abs=0.05)


def test_a_long_file_is_cut_into_equal_windows_of_at_most_16_bars(
    tmp_path: Path, kit: DrumKit
) -> None:
    notes = beat_notes(40, first_bar=1)
    offsets = cycle(SPREAD, len(notes))

    grooves = measured(write(tmp_path / "long.mid", notes, offsets), kit)

    assert [groove.bars for groove in grooves] == [(1, 14), (14, 28), (28, 41)]
    assert all(end - first <= WINDOW_BARS for first, end in (g.bars for g in grooves))
    assert sum(groove.notes for groove in grooves) == len(notes)
    assert all(groove.timing == "performed" for groove in grooves)


def test_a_file_without_a_tempo_has_its_velocities_measured_and_its_timing_not(
    tmp_path: Path, kit: DrumKit
) -> None:
    notes = beat_notes(4)
    path = write(tmp_path / "x.mid", notes, cycle(SPREAD, len(notes)), with_tempo=False)

    result = measure_file(path, PurePosixPath("f", "x.mid"), kit)

    (groove,) = result.grooves
    assert (result.tempo, groove.timing, groove.spread_ms) == (False, "no_tempo", None)
    assert groove.energy == 100.0


def test_a_groove_with_too_few_notes_has_no_timing(tmp_path: Path, kit: DrumKit) -> None:
    notes = beat_notes(2)
    assert len(notes) < MIN_NOTES

    (groove,) = measured(write(tmp_path / "short.mid", notes, cycle(SPREAD, len(notes))), kit)

    assert (groove.timing, groove.spread_ms) == ("too_few", None)


def test_unmapped_notes_are_left_out_and_counted(tmp_path: Path, kit: DrumKit) -> None:
    notes = [*beat_notes(4), (BAR + PPQ // 4, ODD), (2 * BAR + PPQ // 4, ODD)]
    notes.sort()
    path = write(tmp_path / "odd.mid", notes, cycle(SPREAD, len(notes)))

    result = measure_file(path, PurePosixPath("f", "odd.mid"), kit)

    assert result.unmapped == 2
    (groove,) = result.grooves
    assert (groove.notes, groove.timing) == (48, "performed")


def test_a_file_that_cannot_be_measured_says_why(tmp_path: Path, kit: DrumKit) -> None:
    (tmp_path / "broken.mid").write_bytes(b"not midi")
    two = save(
        tmp_path / "two.mid",
        track((0, tempo(BPM)), (0, on(KICK)), (PPQ, off(KICK)), (PPQ, end())),
        track((0, name("keys")), (0, on(60)), (PPQ, off(60)), (PPQ, end())),
        track((0, name("bass")), (0, on(40)), (PPQ, off(40)), (PPQ, end())),
        ppq=PPQ,
    )

    broken = measure_file(tmp_path / "broken.mid", PurePosixPath("f", "broken.mid"), kit)
    unclear = measure_file(two, PurePosixPath("f", "two.mid"), kit)

    assert str(broken.problem).startswith("not read")
    assert unclear.problem == "drum_track: needs an answer"
    assert broken.grooves == unclear.grooves == []


def test_every_pitch_kit_measures_timing_without_any_name(tmp_path: Path) -> None:
    notes = [(tick, pitch + 40) for tick, pitch in beat_notes(4)]
    path = write(tmp_path / "any.mid", notes, cycle(SPREAD, len(notes)))

    (groove,) = measured(path, every_pitch_kit())

    assert groove.timing == "performed"
    expected = float(np.std(np.array(cycle(SPREAD, 48)))) * MS_PER_TICK
    assert groove.spread_ms == pytest.approx(expected)


def groove(spread: float, folder: str = "a", pack: str = "a") -> Groove:
    return Groove(
        folder=folder,
        pack=pack,
        file=f"{folder}/x.mid",
        bars=(0, 4),
        notes=48,
        on_grid=0.1,
        timing="performed",
        spread_ms=spread,
        feel_ms=0.0,
        energy=100.0,
        dynamic_range=5.0,
        flat=False,
    )


def test_cuts_make_three_bands_and_flag_a_band_one_folder_supplies() -> None:
    grooves = [groove(float(spread), "a") for spread in range(1, 10)] + [groove(20.0, "b")]

    low, high = thirds(grooves)
    found = dict(alternatives(grooves, [(4.0, 8.0)]))
    text = report([], [])

    assert [band.name for band in bands((low, high))] == ["tight", "medium", "loose"]
    assert low < high
    assert found["given 4 and 8 ms"] == (4.0, 8.0)
    assert set(found) >= {"equal thirds", "whole milliseconds near the thirds"}
    # Counted alike, folder b's one groove weighs as much as folder a's nine.
    assert balanced_thirds(grooves, lambda g: g.folder)[1] >= 9.0
    assert "files: 0, 0 measured" in text


def test_the_report_counts_grooves_spreads_and_bands(tmp_path: Path, kit: DrumKit) -> None:
    root = tmp_path / "midi"
    notes = beat_notes(4)
    for index, shift in enumerate((1, 2, 3)):
        offsets = [value * shift for value in cycle(SPREAD, len(notes))]
        write(root / "a" / f"{index}.mid", notes, offsets)
    write(root / "a" / "grid.mid", notes)

    results = measure(root, ["a"], lambda _: kit)
    text = report(results)

    assert "files: 4, 4 measured" in text
    assert "grooves: 4 (windows of up to 16 bars); performed timing 3, on the grid 1" in text
    assert "timing spread, ms, of 3 grooves with performed timing" in text
    assert "  p5 " in text
    assert "one folder alone: a 100%" in text


def test_main_measures_the_assigned_folders_and_the_left_out_ones_apart(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "midi"
    notes = beat_notes(4)
    write(root / "a" / "x.mid", notes, cycle(SPREAD, len(notes)))
    write(root / "b" / "y.mid", notes, cycle(SPREAD, len(notes)))
    assignments = tmp_path / "folders.toml"
    assignments.write_text('schema = 1\n[folders.a]\nmap = "gm"\n[folders.b]\nexclude = "why"\n')
    options = ["measure", "--root", str(root), "--assignments", str(assignments)]

    assert main([*options, "--excluded", "--cuts", "4,8", "--on-grid", "0.3"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("== every assigned folder\nfiles: 1, 1 measured")
    assert "\n== a\n" in out
    assert "== the folders left out, timing only" in out
    assert "\n== b, left out\nfiles: 1, 1 measured" in out
    assert "cuts, given 4 and 8 ms" in out

    assignments.write_text('schema = 1\n[folders.a]\nmap = "no-such-library"\n')
    assert main(options) == 2
    with pytest.raises(SystemExit):
        main([*options, "--cuts", "8,4"])
