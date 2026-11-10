"""The styles: the placeholder of ADR 0051, and the three calibrated styles in `data/styles/`
(ADRs 0067 to 0070)."""

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from grooves import normalized, plan_for, rendered, rock, song
from human_o_matic.controls import ControlVector, SessionPlan, StyleName
from human_o_matic.render.measure import mean_velocity, timing_spread
from human_o_matic.render.style import (
    PLACEHOLDER,
    STYLE_NAMES,
    Anchors,
    StyleError,
    built_in_styles,
    load_style,
)

BANDS = {"tight": (0.0, 3.0), "medium": (3.0, 6.0), "loose": (6.0, 99.0)}
"""Each style's band of timing spread, in ms (ADR 0067)."""
KEPT = ("defaults", "feet", "rider_groove", "rider_flip", "soft_mix", "fill_hand", "fill_shift")
KEPT += ("snare_loudness", "arc_span", "energy_drift_sd", "energy_drift_quarters", "drift_sd")
KEPT += ("drift_quarters",)


def test_a_center_passes_through_the_anchors_and_goes_on_along_their_lines() -> None:
    kick = PLACEHOLDER.velocity["kick"]

    assert [kick.at(energy) for energy in (1.0, 0.5, 0.2)] == [122, 104, 85]
    assert kick.at(0.0) == pytest.approx(85 - (104 - 85) * 2 / 3)
    assert kick.at(1.1) == pytest.approx(122 + (122 - 104) / 5)


def test_the_placeholder_is_appendix_a_and_never_a_built_in_style() -> None:
    assert PLACEHOLDER.placeholder
    assert PLACEHOLDER.defaults.tightness == 0.75
    assert PLACEHOLDER.velocity["fill"] == PLACEHOLDER.velocity["other"]
    assert all(not style.placeholder for style in built_in_styles().values())


def test_a_style_needs_a_velocity_row_for_every_role() -> None:
    rows = dict(PLACEHOLDER.velocity)
    del rows["rider"]

    with pytest.raises(ValidationError, match="no velocities for rider"):
        PLACEHOLDER.model_validate(PLACEHOLDER.model_dump() | {"velocity": rows})


def test_an_anchor_row_is_strict() -> None:
    with pytest.raises(ValidationError):
        Anchors.model_validate({"full": "122", "half": 104, "low": 85})


def test_the_three_styles_load_from_their_files_and_tight_is_the_default() -> None:
    styles = built_in_styles()

    assert list(styles) == list(STYLE_NAMES) == ["tight", "medium", "loose"]
    assert all(style.name == name for name, style in styles.items())
    assert SessionPlan.model_fields["style"].default == "tight"


def test_the_styles_share_their_velocities_and_keep_what_a_performance_can_t_give() -> None:
    tight, medium, loose = (built_in_styles()[name] for name in STYLE_NAMES)
    shared = ("velocity", "metric_velocity", "noise_sd", "rider_gap", "accent", "soft", "soft_sd")
    shared += ("fill_metric", "fill_crescendo")

    for name in shared:
        assert getattr(tight, name) == getattr(medium, name) == getattr(loose, name), name
    for style in (tight, medium, loose):
        for name in KEPT:
            assert getattr(style, name) == getattr(PLACEHOLDER, name), (style.name, name)
        for role, anchors in style.velocity.items():
            assert anchors.band == PLACEHOLDER.velocity[role].band


def test_a_style_file_that_breaks_the_model_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "tight.toml"
    path.write_text('name = "tight"\nplaceholder = false\n')

    with pytest.raises(StyleError, match=r"tight\.toml"):
        load_style(path)


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_kick_and_backbeats_at_full_energy_play_118_to_127(style: StyleName) -> None:
    midi = song(rock(16))
    result = normalized(midi)
    full = ControlVector(energy=1.0)

    for seed in range(4):
        out = rendered(midi, plan_for(midi, result, controls=full, seed=seed, style=style))
        for role in ("kick", "backbeat"):
            loud = mean_velocity(out.notes, roles=(role,))
            assert loud is not None
            assert 118 <= loud <= 127, (role, loud)


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_a_style_at_its_defaults_spreads_as_its_band_s_grooves_do(style: StyleName) -> None:
    midi = song(rock(16))
    result = normalized(midi)
    spreads = []
    for seed in range(8):
        out = rendered(midi, plan_for(midi, result, seed=seed, style=style), result=result)
        spread = timing_spread(out.notes)
        assert spread is not None
        spreads.append(spread)
    low, high = BANDS[style]

    assert low <= float(np.mean(spreads)) < high, spreads
