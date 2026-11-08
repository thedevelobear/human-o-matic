import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import TempoMap, TimeSignatureMap
from human_o_matic.normalize.grid import DIVISIONS, GRIDS, Grid
from human_o_matic.normalize.quantize import GRACE_MS, LIMB_MS, UNISON_MS, Quantized, quantize
from human_o_matic.normalize.read import Hit

PPQ = 960
FOUR_FOUR = TimeSignatureMap(PPQ, [])
AT_120 = TempoMap.constant(PPQ, 120)
DRUMS: dict[int, tuple[str, str, int]] = {
    36: ("kick.hit", "kick", 1),
    38: ("snare.center", "snare", 1),
    40: ("snare.rimshot", "snare", 1),
    42: ("hat.closed", "hat", 1),
    44: ("hat.pedal", "hat", 1),
    48: ("tom.1.hit", "tom", 1),
    45: ("tom.2.hit", "tom", 2),
}


def hits_at(times: list[tuple[float, int]], tempos: TempoMap = AT_120) -> list[Hit]:
    """Hits at (milliseconds, pitch), rounded to ticks, in the order of `MidiSong.notes`."""
    placed = sorted(
        (round(tempos.ms_to_tick(ms)), number, pitch) for number, (ms, pitch) in enumerate(times)
    )
    hits: list[Hit] = []
    for index, (tick, _, pitch) in enumerate(placed):
        name, family, piece = DRUMS[pitch]
        note = Note(track=0, channel=9, pitch=pitch, start=tick, end=tick + 10, velocity=100)
        hits.append(
            Hit(
                index=index,
                note=note,
                articulation=name,
                family=family,
                piece=piece,
                confidence="high",
            )
        )
    return hits


def position(hits: list[Hit], pitch: int) -> int:
    """The position of the only hit on `pitch`."""
    (found,) = (n for n, hit in enumerate(hits) if hit.note.pitch == pitch)
    return found


def run(times: list[tuple[float, int]], tempos: TempoMap = AT_120) -> tuple[list[Hit], Quantized]:
    hits = hits_at(times, tempos)
    return hits, quantize(hits, tempos, FOUR_FOUR)


def test_a_flam_is_a_grace_linked_to_its_main() -> None:
    # A snare backbeat at 500 ms, 3 ms late, with its grace 28 ms before it.
    hits, quantized = run([(0, 36), (475, 38), (503, 38)])

    assert quantized.grace_of == (None, 2, None)
    assert quantized.ticks[2] == 960
    # The grace keeps its performed gap, 28 ms or 53.76 ticks, rounded to a tick.
    assert quantized.ticks[1] == 960 - 54
    assert quantized.offsets_ms[2] == pytest.approx(3, abs=0.3)
    assert quantized.offsets_ms[1] == pytest.approx(quantized.offsets_ms[2], abs=0.6)
    assert quantized.beat_of[1] == quantized.beat_of[2]
    assert [hit.note.start for hit in hits] == sorted(hit.note.start for hit in hits)


def test_a_drag_links_both_graces_to_the_main() -> None:
    _, quantized = run([(450, 38), (475, 38), (500, 38)])

    assert quantized.grace_of == (2, 2, None)
    assert quantized.ticks.tolist() == [960 - 96, 960 - 48, 960]


def test_a_grace_on_another_articulation_of_the_drum_is_still_a_grace() -> None:
    _, quantized = run([(480, 38), (500, 40)])

    assert quantized.grace_of == (1, None)


@pytest.mark.parametrize("gap", [GRACE_MS + 1, GRACE_MS + 10])
def test_hits_further_apart_are_not_graces(gap: float) -> None:
    _, quantized = run([(500 - gap, 38), (500, 38)])

    assert quantized.grace_of == (None, None)


def test_hits_on_different_drums_are_not_graces() -> None:
    _, quantized = run([(490, 48), (500, 45)])

    assert quantized.grace_of == (None, None)
    # They are one onset instead.
    assert quantized.ticks.tolist() == [960, 960]


def test_hits_closer_than_a_unison_are_one_stroke() -> None:
    # A hat pedal 3 ms before a hat stick hit is two limbs, not a flam.
    _, quantized = run([(497, 44), (500, 42)])

    assert quantized.grace_of == (None, None)
    assert quantized.ticks.tolist() == [960, 960]
    assert UNISON_MS > 3


def test_a_fast_roll_is_on_the_grid_not_graces() -> None:
    # 32nds at 200 BPM are 37.5 ms apart, under the grace gap, and are a grid step.
    tempos = TempoMap.constant(PPQ, 200)
    times = [(n * 37.5 + jitter, 38) for n, jitter in enumerate([0, 3, -2, 4, -3, 2, 0, -4])]

    _, quantized = run(times, tempos)

    assert quantized.grace_of == (None,) * 8
    assert quantized.ticks.tolist() == [n * 120 for n in range(8)]
    assert [beat.grid for beat in quantized.beats] == ["32nd"]


def test_near_simultaneous_limbs_share_a_grid_point() -> None:
    # 32nds on the hat at 120 BPM. A kick 22 ms and a snare 38 ms after the 32nd at 250 ms: on
    # its own the snare is nearer the next point, at 312.5 ms.
    hats = [(n * 62.5, 42) for n in range(8)]

    hits, quantized = run([*hats, (272, 36), (288, 38)])

    kick, snare = position(hits, 36), position(hits, 38)
    assert quantized.ticks[[kick, snare]].tolist() == [480, 480]
    # Each keeps its own offset.
    assert np.round(quantized.offsets_ms[[kick, snare]]).tolist() == [22, 38]


def test_the_limb_window_is_at_most_half_a_32nd() -> None:
    # At 250 BPM a 32nd is 30 ms, so 18 ms apart is two 32nds, not one onset.
    tempos = TempoMap.constant(PPQ, 250)
    hats = [(n * 30.0, 42) for n in range(8)]

    hits, quantized = run([*hats, (60, 36), (78, 38)], tempos)

    assert LIMB_MS > 18
    assert quantized.ticks[[position(hits, 36), position(hits, 38)]].tolist() == [240, 360]


def test_a_grace_before_the_first_tick_stays_at_tick_0() -> None:
    _, quantized = run([(0, 38), (20, 38), (500, 38)])

    # The main snaps back to tick 0, so its grace can't go before it.
    assert quantized.grace_of == (1, None, None)
    assert quantized.ticks.tolist()[:2] == [0, 0]


def test_quantizing_is_deterministic() -> None:
    rng = np.random.default_rng(np.random.SeedSequence(7))
    times = [(float(ms), int(rng.choice([36, 38, 42]))) for ms in rng.uniform(0, 4000, 200)]
    hits = hits_at(times)

    first, second = quantize(hits, AT_120, FOUR_FOUR), quantize(hits, AT_120, FOUR_FOUR)

    assert first.ticks.tolist() == second.ticks.tolist()
    assert first.offsets_ms.tolist() == second.offsets_ms.tolist()
    assert first.grace_of == second.grace_of
    assert first.beats == second.beats


def test_no_hits_is_an_empty_result() -> None:
    quantized = quantize([], AT_120, FOUR_FOUR)

    assert quantized.ticks.size == 0
    assert quantized.beats == ()


@given(
    st.lists(st.tuples(st.floats(0, 8000), st.sampled_from(sorted(DRUMS))), max_size=80),
    st.floats(60, 240),
)
def test_same_pitch_notes_never_reorder(times: list[tuple[float, int]], bpm: float) -> None:
    tempos = TempoMap.constant(PPQ, bpm)
    hits, quantized = run(times, tempos)

    last: dict[int, int] = {}
    for hit, tick in zip(hits, quantized.ticks.tolist(), strict=True):
        assert tick >= last.get(hit.note.pitch, 0)
        last[hit.note.pitch] = tick
    assert len(quantized.ticks) == len(hits)


@st.composite
def quantized_grooves(draw: st.DrawFn) -> tuple[list[tuple[int, int]], float]:
    """Notes on the grid, one grid per beat, as (tick, pitch), and a tempo."""
    notes: list[tuple[int, int]] = []
    for beat in range(draw(st.integers(1, 8))):
        grid: Grid = draw(st.sampled_from(GRIDS))
        steps = DIVISIONS[grid]
        points = draw(st.sets(st.integers(0, steps - 1), max_size=steps))
        for point in sorted(points):
            pitches = draw(st.sets(st.sampled_from(sorted(DRUMS)), min_size=1, max_size=3))
            notes.extend((beat * PPQ + point * PPQ // steps, pitch) for pitch in pitches)
    return notes, draw(st.floats(60, 240))


@given(quantized_grooves())
def test_quantizing_quantized_input_changes_nothing(
    groove: tuple[list[tuple[int, int]], float],
) -> None:
    notes, bpm = groove
    tempos = TempoMap.constant(PPQ, bpm)
    times = [(tempos.tick_to_ms(tick), pitch) for tick, pitch in notes]

    hits, quantized = run(times, tempos)

    assert quantized.ticks.tolist() == [hit.note.start for hit in hits]
    assert np.allclose(quantized.offsets_ms, 0, atol=1e-6)
    assert quantized.grace_of == (None,) * len(hits)
