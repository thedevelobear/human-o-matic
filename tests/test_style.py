"""The placeholder style: the plan's Appendix A and the values ADR 0051 adds to it."""

import pytest
from pydantic import ValidationError

from human_o_matic.render.style import STYLES, TIGHT, Anchors


def test_a_center_passes_through_the_anchors_and_goes_on_along_their_lines() -> None:
    kick = TIGHT.velocity["kick"]

    assert [kick.at(energy) for energy in (1.0, 0.5, 0.2)] == [122, 104, 85]
    assert kick.at(0.0) == pytest.approx(85 - (104 - 85) * 2 / 3)
    assert kick.at(1.1) == pytest.approx(122 + (122 - 104) / 5)


def test_tight_is_the_only_style_and_its_numbers_are_placeholders() -> None:
    assert list(STYLES) == ["tight"]
    assert TIGHT.placeholder
    assert TIGHT.defaults.tightness == 0.75
    assert TIGHT.velocity["fill"] == TIGHT.velocity["other"] == TIGHT.velocity["snare"]


def test_a_style_needs_a_velocity_row_for_every_role() -> None:
    rows = dict(TIGHT.velocity)
    del rows["rider"]

    with pytest.raises(ValidationError, match="no velocities for rider"):
        TIGHT.model_validate(TIGHT.model_dump() | {"velocity": rows})


def test_an_anchor_row_is_strict() -> None:
    with pytest.raises(ValidationError):
        Anchors.model_validate({"full": "122", "half": 104, "low": 85})
