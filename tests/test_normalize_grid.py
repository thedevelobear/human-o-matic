import numpy as np
import pytest

from human_o_matic.decisions import DecisionRequest
from human_o_matic.midi.tempo import TempoMap, TimeSignature, TimeSignatureMap
from human_o_matic.normalize.grid import (
    FAR_MS,
    GRIDS,
    MAX_LISTED,
    PENALTY_MS,
    BeatGrid,
    Grid,
    ambiguous_request,
    applies,
    beat_windows,
    snap,
    steps,
)

PPQ = 960
FOUR_FOUR = TimeSignatureMap(PPQ, [])
AT_120 = TempoMap.constant(PPQ, 120)
"""One beat is 500 ms."""
AT_60 = TempoMap.constant(PPQ, 60)
CLOSE_CALL = 0.14
"""70 ms into a beat at 120 BPM: 7.5 ms from the 32nd point and 13.3 ms from the 16th
triplet's, which is a close call."""


def snapped(
    beats: list[list[float]],
    tempos: TempoMap = AT_120,
    shift_ms: list[float] | None = None,
    answers: dict[tuple[int, int], Grid] | None = None,
) -> tuple[list[int], tuple[BeatGrid, ...]]:
    """Onsets at the given positions in each beat of 4/4, moved by `shift_ms`, snapped."""
    positions = [beat + at for beat, ats in enumerate(beats) for at in ats]
    ticks = np.array(positions) * PPQ
    ms = tempos.ticks_to_ms(ticks) + np.array(shift_ms or [0.0] * len(positions))
    windows = beat_windows(FOUR_FOUR, int(ticks.max()) + 1)
    result = snap(tempos.ms_to_ticks(ms), ms, windows, tempos, answers)
    return [int(tick) for tick in result.ticks], result.beats


def grids_of(beats: tuple[BeatGrid, ...]) -> list[Grid]:
    return [beat.grid for beat in beats]


def listed_beats(request: DecisionRequest) -> int:
    bars = request.details["bars"]
    assert isinstance(bars, list)
    count = 0
    for bar in bars:
        assert isinstance(bar, dict)
        beats = bar["beats"]
        assert isinstance(beats, list)
        count += len(beats)
    return count


def test_beats_follow_the_time_signatures() -> None:
    signatures = TimeSignatureMap(PPQ, [(0, TimeSignature(4, 4)), (2 * PPQ, TimeSignature(7, 8))])

    beats = beat_windows(signatures, 4 * PPQ)

    # Bar 0 is cut short at beat 2 by the change to 7/8, whose beats are eighths.
    assert beats.starts.tolist() == [0, 960, *(1920 + 480 * n for n in range(7))]
    assert beats.ends.tolist() == [960, 1920, *(1920 + 480 * n for n in range(1, 8))]
    assert beats.bars.tolist() == [0, 0, *[1] * 7]
    assert beats.numbers.tolist() == [0, 1, *range(7)]
    assert beats.denominators.tolist() == [4, 4, *[8] * 7]


@pytest.mark.parametrize(
    ("denominator", "expected"),
    [
        (2, {"16th": 8, "8th_triplet": 6, "16th_triplet": 12, "32nd": 16}),
        (4, {"16th": 4, "8th_triplet": 3, "16th_triplet": 6, "32nd": 8}),
        (8, {"16th": 2, "8th_triplet": None, "16th_triplet": 3, "32nd": 4}),
        (16, {"16th": 1, "8th_triplet": None, "16th_triplet": None, "32nd": 2}),
        (64, {"16th": None, "8th_triplet": None, "16th_triplet": None, "32nd": None}),
    ],
)
def test_a_grid_applies_when_it_divides_the_beat(
    denominator: int, expected: dict[Grid, int | None]
) -> None:
    assert {grid: steps(grid, denominator) for grid in GRIDS} == expected
    found = {grid for grid in GRIDS if applies(grid, denominator)}
    # Only a beat shorter than a 32nd falls back to the 32nd, with its own ends as points.
    assert found == ({"32nd"} if denominator == 64 else {g for g, n in expected.items() if n})


@pytest.mark.parametrize(
    ("positions", "grid"),
    [
        ([0, 0.25, 0.5, 0.75], "16th"),
        ([0, 1 / 3, 2 / 3], "8th_triplet"),
        ([0, 2 / 3], "8th_triplet"),
        ([0, 1 / 6, 1 / 3, 1 / 2, 2 / 3, 5 / 6], "16th_triplet"),
        ([0, 1 / 8, 0.5], "32nd"),
        ([0, 0.25, 0.375, 0.5], "32nd"),
    ],
)
def test_each_beat_takes_the_grid_that_fits(positions: list[float], grid: Grid) -> None:
    ticks, beats = snapped([positions])

    assert grids_of(beats) == [grid]
    assert ticks == [round(at * PPQ) for at in positions]
    assert not beats[0].ambiguous


def test_a_quarter_takes_the_16th() -> None:
    _, beats = snapped([[0]])

    assert grids_of(beats) == ["16th"]
    # Every grid fits it, so each scores its penalty alone.
    assert beats[0].costs == tuple(PENALTY_MS[grid] for grid in GRIDS)


@pytest.mark.parametrize("positions", [[0, 0.5], [0.5]])
def test_eighths_take_the_16th(positions: list[float]) -> None:
    _, beats = snapped([positions])

    assert grids_of(beats) == ["16th"]
    # Every grid but the 8th triplet has the 8th, 83.3 ms from that grid's nearest point.
    expected = {grid: PENALTY_MS[grid] for grid in GRIDS} | {"8th_triplet": 6 + 83.333}
    assert beats[0].costs == tuple(expected.values())


def test_grids_are_chosen_beat_by_beat() -> None:
    ticks, beats = snapped([[0, 0.25, 0.75], [0, 1 / 3, 2 / 3], [], [0, 1 / 8, 0.25]])

    # The empty beat has no grid, and the beats keep their bars and places.
    assert grids_of(beats) == ["16th", "8th_triplet", "32nd"]
    assert [(beat.bar, beat.beat) for beat in beats] == [(0, 0), (0, 1), (0, 3)]
    assert ticks == [0, 240, 720, 960, 1280, 1600, 2880, 3000, 3120]


def test_a_complex_grid_must_save_more_than_its_penalty() -> None:
    # 25 ms early on the 16th at 125 ms: the 16th triplet's point at 83.3 ms is 8.3 ms nearer,
    # less than its penalty. 30 ms early, it is 18.3 ms nearer, more than its penalty.
    early = snapped([[0, 0.25]], shift_ms=[0, -25])
    earlier = snapped([[0, 0.25]], shift_ms=[0, -30])

    assert early[0] == [0, 240]
    assert grids_of(early[1]) == ["16th"]
    assert earlier[0] == [0, 160]
    assert grids_of(earlier[1]) == ["16th_triplet"]


def test_jitter_does_not_turn_16ths_into_a_finer_grid() -> None:
    shifts = [7.0, -8.0, 9.0, -6.0]

    ticks, beats = snapped([[0, 0.25, 0.5, 0.75]], shift_ms=shifts)

    assert grids_of(beats) == ["16th"]
    assert ticks == [0, 240, 480, 720]
    # The 32nd places them the same, so it is no alternative.
    assert beats[0].alternatives == ()
    assert not beats[0].ambiguous


def test_timing_is_measured_at_the_local_tempo() -> None:
    # 20 ms late on a 16th is still a 16th at 120 BPM, but at 187.5 BPM it is 6.7 ms from the
    # 8th triplet's point, which saves more than that grid's penalty.
    tempos = TempoMap(PPQ, [0, PPQ], [500_000, 320_000])

    ticks, beats = snapped([[0, 0.25], [0, 0.25]], tempos, shift_ms=[0, 20, 0, 20])

    assert grids_of(beats) == ["16th", "8th_triplet"]
    assert ticks == [0, 240, 960, 1280]


def test_a_note_far_from_its_grid_point_makes_the_beat_ambiguous() -> None:
    ticks, beats = snapped([[0, 0.25]], AT_60, shift_ms=[0, FAR_MS + 4])

    assert ticks == [0, 240]
    assert beats[0].alternatives == ()
    assert beats[0].largest_offset_ms == pytest.approx(FAR_MS + 4, abs=0.1)
    assert beats[0].ambiguous


def test_close_scores_that_place_notes_differently_are_ambiguous() -> None:
    ticks, beats = snapped([[0, CLOSE_CALL]])

    assert ticks == [0, 120]
    assert grids_of(beats) == ["32nd"]
    assert beats[0].alternatives == ("16th_triplet",)
    assert beats[0].largest_offset_ms == pytest.approx(7.5)
    assert beats[0].ambiguous


def test_an_answer_sets_the_grid_and_settles_the_beat() -> None:
    ticks, beats = snapped([[0, CLOSE_CALL]], answers={(0, 0): "16th_triplet"})

    assert ticks == [0, 160]
    assert grids_of(beats) == ["16th_triplet"]
    assert beats[0].answered
    assert not beats[0].ambiguous


def test_an_answer_the_beat_cant_have_is_an_error() -> None:
    windows = beat_windows(TimeSignatureMap(PPQ, [(0, TimeSignature(6, 8))]), PPQ)
    ticks = np.array([0.0, 240.0])

    with pytest.raises(ValueError, match="bar 1, beat 1: a 8th_triplet grid doesn't fit"):
        snap(ticks, AT_120.ticks_to_ms(ticks), windows, AT_120, {(0, 0): "8th_triplet"})


def test_an_eighth_beat_never_takes_the_8th_triplet() -> None:
    windows = beat_windows(TimeSignatureMap(PPQ, [(0, TimeSignature(6, 8))]), 2 * PPQ)
    # In the first eighth, 0 to 480: 320 is an 8th triplet point, and a 16th triplet one.
    ticks = np.array([0.0, 320.0])

    result = snap(ticks, AT_120.ticks_to_ms(ticks), windows, AT_120)

    assert [beat.grid for beat in result.beats] == ["16th_triplet"]
    assert result.ticks.tolist() == [0, 320]
    assert result.beats[0].costs[GRIDS.index("8th_triplet")] is None


def test_a_beat_cut_short_snaps_to_its_end() -> None:
    signatures = TimeSignatureMap(PPQ, [(0, TimeSignature(4, 4)), (1200, TimeSignature(3, 4))])
    windows = beat_windows(signatures, 2 * PPQ)
    # Beat 1 of bar 0 runs from 960 to 1200, where bar 1 starts.
    ticks = np.array([1190.0])

    result = snap(ticks, AT_120.ticks_to_ms(ticks), windows, AT_120)

    assert result.ticks.tolist() == [1200]
    assert (result.beats[0].start, result.beats[0].end) == (960, 1200)


def test_ambiguous_bars_are_one_compact_request() -> None:
    # Bar 0 at 60 BPM has a note 25 ms late, and bar 1 at 120 BPM a close call.
    tempos = TempoMap(PPQ, [0, 4 * PPQ], [1_000_000, 500_000])

    _, beats = snapped(
        [[0, 0.25], [], [], [], [0, CLOSE_CALL], [0, 0.25]], tempos, shift_ms=[0, 25, 0, 0, 0, 0]
    )
    request = ambiguous_request(beats)

    assert request is not None
    assert request.kind == "ambiguous_bars"
    assert request.answer_with == ("grids",)
    assert request.details == {
        "bars": [
            {
                "bar": 0,
                "beats": [
                    {"beat": 0, "grid": "16th", "alternatives": [], "largest_offset_ms": 25.0}
                ],
            },
            {
                "bar": 1,
                "beats": [
                    {
                        "beat": 0,
                        "grid": "32nd",
                        "alternatives": ["16th_triplet"],
                        "largest_offset_ms": 7.5,
                    }
                ],
            },
        ]
    }
    assert request.message.startswith("2 bars have beats whose grid is unclear")
    assert "bar 1, beat 1: 16th, with a note 25 ms off it" in request.message
    assert "bar 2, beat 1: 32nd or 16th triplet" in request.message


def test_a_request_names_at_most_a_few_beats() -> None:
    _, beats = snapped([[0, CLOSE_CALL] for _ in range(MAX_LISTED + 3)])

    request = ambiguous_request(beats)

    assert request is not None
    assert request.message.count("32nd or 16th triplet") == MAX_LISTED
    assert "and 3 more" in request.message
    assert listed_beats(request) == MAX_LISTED + 3


def test_no_ambiguous_beats_is_no_request() -> None:
    _, beats = snapped([[0, 0.25, 0.5]])

    assert ambiguous_request(beats) is None
