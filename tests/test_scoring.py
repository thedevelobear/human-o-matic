"""Scoring detected section boundaries against labelled ones (ADR 0034)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.analyze.scoring import (
    EXIT_F1,
    EXIT_TRACKS,
    BoundaryScore,
    match_boundaries,
    score_starts,
    totals,
)


def most_matches(detected: list[int], labelled: list[int], tolerance: int) -> int:
    """The largest one-to-one matching, found by augmenting paths (Kuhn's algorithm)."""
    partner: dict[int, int] = {}

    def augment(mine: int, seen: set[int]) -> bool:
        for theirs, bar in enumerate(labelled):
            if abs(detected[mine] - bar) <= tolerance and theirs not in seen:
                seen.add(theirs)
                if theirs not in partner or augment(partner[theirs], seen):
                    partner[theirs] = mine
                    return True
        return False

    return sum(augment(mine, set()) for mine in range(len(detected)))


@pytest.mark.parametrize(
    ("detected", "labelled", "matches"),
    [
        ([8, 16], [8, 16], 2),
        ([7, 17], [8, 16], 2),
        ([6, 18], [8, 16], 0),
        # Two detections near one label count once, and one detection can't serve two labels.
        ([7, 9], [8], 1),
        ([8], [7, 9], 1),
        # Pairing 8 with 9 would leave 10 without a partner.
        ([8, 10], [9, 11], 2),
        ([], [8], 0),
    ],
)
def test_boundaries_match_one_to_one_within_a_bar(
    detected: list[int], labelled: list[int], matches: int
) -> None:
    assert match_boundaries(detected, labelled) == matches


@given(
    st.lists(st.integers(1, 40), unique=True, max_size=8),
    st.lists(st.integers(1, 40), unique=True, max_size=8),
    st.integers(0, 3),
)
def test_matching_in_order_finds_the_most_matches(
    detected: list[int], labelled: list[int], tolerance: int
) -> None:
    assert match_boundaries(detected, labelled, tolerance) == most_matches(
        detected, labelled, tolerance
    )


def test_bar_0_is_not_a_boundary() -> None:
    score = score_starts([0, 8, 12, 16], [0, 8, 16, 24])

    assert score == BoundaryScore(matches=2, detected=3, labelled=3)
    assert score.precision == score.recall == pytest.approx(2 / 3)
    assert score.f1 == pytest.approx(2 * 2 / (3 + 3))


def test_nothing_detected_scores_0() -> None:
    score = score_starts([0], [0, 8])

    assert (score.precision, score.recall, score.f1) == (0.0, 0.0, 0.0)


@given(st.integers(0, 20), st.integers(0, 20), st.integers(1, 20))
def test_f1_is_the_harmonic_mean_of_precision_and_recall(
    matches: int, extra_detected: int, extra_labelled: int
) -> None:
    score = BoundaryScore(
        matches=matches, detected=matches + extra_detected, labelled=matches + extra_labelled
    )

    if matches:
        harmonic = 2 * score.precision * score.recall / (score.precision + score.recall)
        assert score.f1 == pytest.approx(harmonic)
    else:
        assert score.f1 == 0.0


def test_the_headline_is_the_mean_of_each_tracks_f1() -> None:
    long = BoundaryScore(matches=18, detected=20, labelled=20)
    short = BoundaryScore(matches=0, detected=2, labelled=2)

    result = totals([long, short], [True, False])

    assert result.tracks == 2
    assert result.mean_f1 == pytest.approx((0.9 + 0.0) / 2)
    assert result.pooled_f1 == pytest.approx(2 * 18 / 44)
    assert result.untuned == 1
    assert result.untuned_mean_f1 == pytest.approx(0.0)


def test_the_untuned_mean_is_the_headline_when_no_track_is_tuned_and_none_when_all_are() -> None:
    scores = [BoundaryScore(matches=3, detected=4, labelled=4)] * 2

    assert totals(scores, [False, False]).untuned_mean_f1 == totals(scores, [False] * 2).mean_f1
    assert totals(scores, [True, True]).untuned_mean_f1 is None
    assert totals(scores, [True, True]).untuned == 0


def test_the_exit_needs_enough_tracks_and_a_high_enough_mean() -> None:
    good = BoundaryScore(matches=15, detected=20, labelled=20)
    missed = BoundaryScore(matches=0, detected=20, labelled=20)
    assert good.f1 > EXIT_F1 > (good.f1 * (EXIT_TRACKS - 1) + missed.f1) / EXIT_TRACKS

    assert totals([good] * EXIT_TRACKS, [False] * EXIT_TRACKS).exit_met
    assert not totals([good] * (EXIT_TRACKS - 1), [False] * (EXIT_TRACKS - 1)).exit_met
    worse = [*[good] * (EXIT_TRACKS - 1), missed]
    assert not totals(worse, [False] * EXIT_TRACKS).exit_met


def test_totals_need_a_track() -> None:
    with pytest.raises(ValueError, match="no tracks"):
        totals([], [])
