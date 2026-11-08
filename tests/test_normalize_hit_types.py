from itertools import combinations, pairwise

import numpy as np
import pydantic
import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.normalize.hit_types import (
    FamilyHitTypes,
    HitTypeBounds,
    classify,
    groups,
    hit_types_request,
    type_hits,
)


def spread(rng: np.random.Generator, mean: float, sd: float, count: int) -> list[int]:
    return np.clip(np.rint(rng.normal(mean, sd, count)), 1, 127).astype(int).tolist()


def brute_force_error(values: list[int], count: int) -> float:
    """The least squared error of any split of the sorted values into `count` runs."""
    ordered = sorted(values)
    best = np.inf
    for cuts in combinations(range(1, len(ordered)), count - 1):
        bounds = [0, *cuts, len(ordered)]
        parts = [np.array(ordered[a:b], dtype=float) for a, b in pairwise(bounds)]
        best = min(best, sum(float(((part - part.mean()) ** 2).sum()) for part in parts))
    return best


@given(st.lists(st.integers(1, 127), min_size=1, max_size=9), st.integers(1, 3))
def test_groups_are_the_optimal_split(values: list[int], count: int) -> None:
    labels = groups(values, count)

    array = np.array(values, dtype=float)
    found = sum(
        float(((array[labels == g] - array[labels == g].mean()) ** 2).sum())
        for g in np.unique(labels)
    )
    distinct = len(set(values))
    assert found == pytest.approx(brute_force_error(values, min(count, distinct)), abs=1e-6)
    # Groups are numbered from the lowest, and equal velocities share one.
    order = np.argsort(array, kind="stable")
    assert np.all(np.diff(labels[order]) >= 0)


def test_ghost_notes_under_backbeats_are_soft() -> None:
    rng = np.random.default_rng(np.random.SeedSequence(1))
    ghosts, backbeats = spread(rng, 40, 6, 30), spread(rng, 112, 5, 16)

    types, reason = classify([*ghosts, *backbeats])

    assert reason == "clusters"
    assert types == ("soft",) * 30 + ("normal",) * 16


def test_louder_hits_over_the_main_level_are_accents() -> None:
    rng = np.random.default_rng(np.random.SeedSequence(2))
    hats, accents = spread(rng, 82, 3, 48), spread(rng, 116, 3, 16)

    types, reason = classify([*hats, *accents])

    assert reason == "clusters"
    assert types == ("normal",) * 48 + ("accent",) * 16


def test_three_levels_are_soft_normal_and_accent() -> None:
    types, reason = classify([30, 32, 34, 30, 90, 92, 94, 90, 92, 120, 122, 124])

    assert reason == "clusters"
    assert types == ("soft",) * 4 + ("normal",) * 5 + ("accent",) * 3


def test_the_main_level_is_the_largest_group_above_soft() -> None:
    # Many kicks at 127, a few at 95: both are the main level, and nothing is an accent.
    types, reason = classify([95, 96, 97, 95, *[127] * 30])

    assert reason == "clusters"
    assert set(types) == {"normal"}


@pytest.mark.parametrize("velocities", [[100] * 12, [96, 98, 100, 101, 104], [64]])
def test_flat_input_is_normal_at_low_confidence(velocities: list[int]) -> None:
    types, reason = classify(velocities)

    assert reason == "flat"
    assert set(types) == {"normal"}
    typed = type_hits(["snare"] * len(velocities), velocities)
    assert set(typed.confidences) == {"low"}
    assert typed.families[0].confidence == "low"


def test_a_spread_without_clear_groups_is_normal_at_low_confidence() -> None:
    rng = np.random.default_rng(np.random.SeedSequence(3))
    velocities = np.rint(rng.uniform(70, 120, 60)).astype(int).tolist()

    types, reason = classify(velocities)

    assert reason == "one_group"
    assert set(types) == {"normal"}


def test_a_lone_note_is_not_a_group() -> None:
    _, reason = classify([40, *[110] * 20])

    assert reason == "one_group"


def test_each_family_is_typed_on_its_own() -> None:
    families = ["snare", "kick", "snare", "kick", "snare", "snare"]
    velocities = [40, 120, 110, 121, 42, 112]

    typed = type_hits(families, velocities)

    assert typed.types == ("soft", "normal", "normal", "normal", "soft", "normal")
    assert typed.confidences == ("high", "low", "high", "low", "high", "high")
    assert typed.families == (
        FamilyHitTypes(
            family="snare",
            reason="clusters",
            confidence="high",
            counts={"soft": 2, "normal": 2},
            velocities={"soft": (40, 42), "normal": (110, 112)},
        ),
        FamilyHitTypes(
            family="kick",
            reason="flat",
            confidence="low",
            counts={"normal": 2},
            velocities={"normal": (120, 121)},
        ),
    )


def test_no_notes_is_no_family() -> None:
    typed = type_hits([], [])

    assert typed.types == ()
    assert typed.families == ()


def test_an_answer_gives_the_types_by_velocity() -> None:
    typed = type_hits(
        ["hat"] * 4,
        [50, 80, 100, 120],
        {"hat": HitTypeBounds(soft_below=60, accent_from=110)},
    )

    assert typed.types == ("soft", "normal", "normal", "accent")
    assert typed.confidences == ("high",) * 4
    assert typed.families[0].reason == "answer"
    assert hit_types_request(typed.families) is None


def test_bounds_must_be_in_order() -> None:
    with pytest.raises(pydantic.ValidationError):
        HitTypeBounds(soft_below=100, accent_from=90)
    with pytest.raises(pydantic.ValidationError):
        HitTypeBounds(soft_below=0)


def test_the_hit_types_are_one_request_to_confirm() -> None:
    typed = type_hits(["snare", "snare", "snare", "snare", "kick"], [40, 42, 110, 112, 120])

    request = hit_types_request(typed.families)

    assert request is not None
    assert request.kind == "hit_types"
    assert request.answer_with == ("hit_types",)
    assert request.message == (
        "Hit types read from the velocities: snare: 2 soft (velocity 40 to 42), 2 normal "
        "(velocity 110 to 112); kick: 1 normal (velocity 120). On kick the velocities show no "
        "clear groups, so every note is taken as normal. Are any of them soft notes or accents? "
        "Do the others look right?"
    )
    assert request.details == {
        "families": [
            {
                "family": "snare",
                "reason": "clusters",
                "confidence": "high",
                "counts": {"soft": 2, "normal": 2},
                "velocities": {"soft": [40, 42], "normal": [110, 112]},
            },
            {
                "family": "kick",
                "reason": "flat",
                "confidence": "low",
                "counts": {"normal": 1},
                "velocities": {"normal": [120, 120]},
            },
        ]
    }
