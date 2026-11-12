"""The controls and plans: their ranges, their layers and their JSON."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from human_o_matic.controls import (
    MAX_SEED,
    Arc,
    Clamped,
    ControlInput,
    Controls,
    ControlVector,
    SectionPlan,
    SessionPlan,
    clamp,
)

DEFAULTS = Controls(
    energy=0.5,
    groove=0.5,
    dynamic_range=0.5,
    tightness=0.75,
    feel=0.0,
    arc="steady",
    fill_intensity=0.5,
    ghost_level=0.5,
    skip=False,
)


def section(start: int, bars: int, **controls: object) -> SectionPlan:
    return SectionPlan(
        start=start, bars=bars, group="A", controls=ControlVector.model_validate(controls)
    )


def test_a_section_s_controls_win_over_the_song_s_and_the_song_s_over_the_defaults() -> None:
    verse = section(0, 8, energy=0.4, arc="build")
    plan = SessionPlan(seed=7, controls=ControlVector(energy=0.9, feel=0.2), sections=(verse,))

    resolved = plan.controls_of(verse, DEFAULTS)

    assert resolved == DEFAULTS.model_copy(update={"energy": 0.4, "feel": 0.2, "arc": "build"})


@pytest.mark.parametrize(
    "text",
    [
        '{"energy": 1.5}',
        '{"energy": -0.1}',
        '{"feel": 2}',
        '{"energy": "0.5"}',
        '{"skip": 1}',
        '{"arc": "rise"}',
        '{"tempo": 120}',
    ],
)
def test_a_control_out_of_range_of_the_wrong_type_or_unknown_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        ControlVector.model_validate_json(text)


def test_sections_start_at_bar_0_and_each_where_the_one_before_ends() -> None:
    SessionPlan(seed=0, sections=(section(0, 4), section(4, 8)))
    with pytest.raises(ValidationError, match="should start at bar 0"):
        SessionPlan(seed=0, sections=(section(1, 4),))
    with pytest.raises(ValidationError, match="should start at bar 4"):
        SessionPlan(seed=0, sections=(section(0, 4), section(5, 8)))
    with pytest.raises(ValidationError):
        SessionPlan(seed=0, sections=())


@pytest.mark.parametrize("seed", [-1, MAX_SEED + 1])
def test_a_seed_is_from_0_to_the_largest_integer_json_keeps_exact(seed: int) -> None:
    with pytest.raises(ValidationError):
        SessionPlan(seed=seed, sections=(section(0, 4),))


_units = st.none() | st.floats(0, 1)
ARCS: tuple[Arc, ...] = ("steady", "build", "drop")


@st.composite
def _vectors(draw: st.DrawFn) -> ControlVector:
    return ControlVector(
        energy=draw(_units),
        groove=draw(_units),
        dynamic_range=draw(_units),
        tightness=draw(_units),
        feel=draw(st.none() | st.floats(-1, 1)),
        arc=draw(st.none() | st.sampled_from(ARCS)),
        fill_intensity=draw(_units),
        ghost_level=draw(_units),
        skip=draw(st.none() | st.booleans()),
    )


@given(_vectors(), st.lists(st.tuples(st.integers(1, 32), _vectors()), min_size=1, max_size=6))
def test_a_plan_s_json_reads_back_equal_without_its_unset_controls(
    song: ControlVector, sections: list[tuple[int, ControlVector]]
) -> None:
    plans: list[SectionPlan] = []
    start = 0
    for bars, controls in sections:
        plans.append(SectionPlan(start=start, bars=bars, group="A", controls=controls, take=1))
        start += bars
    plan = SessionPlan(seed=MAX_SEED, controls=song, sections=tuple(plans))

    data = plan.model_dump(mode="json", exclude_none=True)

    assert SessionPlan.model_validate_json(plan.model_dump_json(exclude_none=True)) == plan
    assert "skip" not in data["controls"] or song.skip is not None
    assert all(value is not None for value in data["controls"].values())


def test_a_number_outside_its_range_is_clamped_and_said() -> None:
    given = ControlInput.model_validate({"energy": 1.3, "feel": -2, "groove": 0.4, "arc": "build"})

    vector, moved = clamp(given)

    assert vector == ControlVector(energy=1.0, feel=-1.0, groove=0.4, arc="build")
    assert moved == (
        Clamped(control="energy", given=1.3, used=1.0),
        Clamped(control="feel", given=-2.0, used=-1.0),
    )


@pytest.mark.parametrize(
    "text", ['{"energy": "0.5"}', '{"skip": 1}', '{"arc": "rise"}', '{"tempo": 120}']
)
def test_an_input_of_the_wrong_type_or_unknown_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        ControlInput.model_validate_json(text)


def test_a_patch_replaces_what_it_gives_unsets_its_nulls_and_keeps_the_rest() -> None:
    held = ControlVector(energy=0.8, groove=0.3, feel=0.2)
    patch, _ = clamp(ControlInput.model_validate({"energy": 0.9, "groove": None}))

    assert held.patched(patch) == ControlVector(energy=0.9, feel=0.2)
    assert held.patched(clamp(ControlInput())[0]) == held


@given(_vectors(), _vectors())
def test_a_patch_of_set_controls_is_the_patch_over_the_held(
    held: ControlVector, given: ControlVector
) -> None:
    patch, moved = clamp(ControlInput.model_validate(given.model_dump(exclude_none=True)))

    assert moved == ()
    assert held.patched(patch) == given.over(held)
