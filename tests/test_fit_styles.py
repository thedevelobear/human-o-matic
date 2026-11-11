"""`tools/fit_styles.py`: the style fits, on grooves whose aggregates are built here."""

import json
import math
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

import calibrate
from calibrate import Detail, FileResult, Groove, _fit
from fit_styles import (
    MIN_GROOVES,
    QUARTERS,
    STYLE_NAMES,
    Fit,
    Measured,
    contradictions,
    drift_variance,
    fit,
    ranks,
    style_toml,
    table,
)
from human_o_matic.render.parts import ROLES
from human_o_matic.render.style import PLACEHOLDER, Anchors, Style

OFFSETS = {role: 2.0 * number for number, role in enumerate(ROLES)}
"""How much louder each role plays than the groove's kick, in the grooves built here."""


def velocity_groove(energy: float, pack: str = "a/p") -> Groove:
    """A groove held to the grid whose roles play about `energy`."""
    return Groove(
        folder="a",
        pack=pack,
        file="a/x.mid",
        bars=(0, 4),
        notes=48,
        at_one_offset=1.0,
        spike=math.inf,
        steps=0.0,
        timing="on_grid",
        far=0.0,
        ambiguous=0.0,
        spread_ms=None,
        feel_ms=None,
        energy=energy,
        dynamic_range=4.0,
        flat=False,
        detail=Detail(
            roles={role: (energy + OFFSETS[role], 8) for role in ROLES},
            metric={("kick", 0): (energy + 1, 4), ("kick", 2): (energy - 1, 4)},
            noise=4.0,
            rider_gap=6.0,
            rider_noise=6.0,
            alternating_noise=5.0,
            accent=20.0,
            soft=30.0 + energy / 10,
            soft_sd=5.0,
            fill_metric={0: 3.0, 1: 1.0, 2: -1.0, 3: -2.0},
            fill_rise=2.0,
        ),
    )


FEELS = (0.0, 1.0, 1.0, 1.0, 3.0)
"""Feel in ms, skewed late as Appendix A's is."""


def timing_groove(
    spread: float, jitter: float, bpm: float, pack: str, far: float = 0.0, feel: float = 1.0
) -> Groove:
    """A performed groove of this spread whose hits each move by `jitter` ms."""
    return replace(
        velocity_groove(100.0, pack),
        timing="performed",
        spread_ms=spread,
        feel_ms=feel,
        far=far,
        detail=Detail(
            shared_var=9.0 + drift_variance(PLACEHOLDER.drift_sd, PLACEHOLDER.drift_quarters),
            jitter_var=jitter**2,
            limbs={"snare": 1.0, "rider": 0.5},
            bpm=bpm,
        ),
    )


def grooves() -> list[Groove]:
    found = [velocity_groove(66 + 0.6 * step, f"a/p{step % 3}") for step in range(100)]
    for spread, jitter in ((2.0, 1.0), (4.0, 2.0), (8.0, 3.0)):
        for number in range(40):
            bpm = 120.0 if number % 2 else 170.0
            feel = FEELS[number % len(FEELS)]
            pack = f"a/p{number // 2 % 2}"
            found.append(timing_groove(spread, jitter, bpm, pack, feel=feel))
    # The grid doesn't fit this one, so its jitter stays out of `tight`.
    found.append(timing_groove(2.0, 50.0, 120.0, "a/p0", far=0.5))
    return found


@pytest.fixture(scope="module")
def fitted() -> Fit:
    return fit([FileResult(path="a/x.mid", folder="a", grooves=grooves())])


def test_ranks_run_from_0_to_1_and_ties_share_their_middle() -> None:
    assert ranks([10.0, 20.0, 20.0, 30.0]) == [0.0, 0.5, 0.5, 1.0]


def test_velocities_are_shared_and_rise_through_the_anchors(fitted: Fit) -> None:
    tight, medium, loose = (fitted.styles[name] for name in STYLE_NAMES)

    assert tight.velocity == medium.velocity == loose.velocity
    kick = tight.velocity["kick"]
    assert kick.low < kick.half < kick.full
    # Each role keeps its offset from the kick, and its band is the placeholder's.
    for role in ROLES:
        assert tight.velocity[role].full - kick.full == pytest.approx(OFFSETS[role], abs=0.02)
        assert tight.velocity[role].band == PLACEHOLDER.velocity[role].band
    assert tight.metric_velocity["kick"] == (1.0, 0.0, -1.0, 0.0)
    assert (tight.noise_sd, tight.soft_sd) == (
        pytest.approx(math.sqrt(16 - drift_variance(2.0, (64.0,))), abs=0.01),
        5.0,
    )
    assert tight.fill_metric == (3.0, 1.0, -1.0, -2.0)


def test_timing_comes_from_each_band_s_grooves_by_tempo(fitted: Fit) -> None:
    for name, jitter in zip(STYLE_NAMES, (1.0, 2.0, 3.0), strict=True):
        style = fitted.styles[name]
        assert style.tempo_cuts == (150.0,)
        for timing in style.timing:
            # At the default tightness, 0.75, each hit's own spread is the bands' median.
            loose, tight = timing.jitter_sd
            assert loose + (tight - loose) * 0.75 == pytest.approx(jitter, abs=0.01)
            assert timing.shared_sd * 0.75 == pytest.approx(3.0, abs=0.01)
            assert (timing.limb_ms["snare"], timing.limb_ms["rider"]) == (1.0, 0.5)
    assert fitted.timing == {"tight": (40, 1, 2), "medium": (40, 1, 2), "loose": (40, 1, 2)}
    assert fitted.tempo == dict.fromkeys(STYLE_NAMES, (20, 20))


def test_what_a_performance_can_t_give_keeps_the_placeholder_exactly(fitted: Fit) -> None:
    for style in fitted.styles.values():
        assert not style.placeholder
        assert style.defaults == PLACEHOLDER.defaults
        for name in ("feet", "rider_flip", "rider_groove", "soft_mix", "fill_hand", "drift_sd"):
            assert getattr(style, name) == getattr(PLACEHOLDER, name), name
    assert "| rider_flip | 0.775 | kept | kept | kept |" in table(fitted)


def test_the_rider_gap_accent_and_crescendo_keep_the_placeholder_though_grooves_give_them(
    fitted: Fit,
) -> None:
    # The grooves built here measure a rider gap of 6, an accent contrast of 20 and a rise of 2.
    for style in fitted.styles.values():
        assert (style.rider_gap, style.accent, style.fill_crescendo) == (
            PLACEHOLDER.rider_gap,
            PLACEHOLDER.accent,
            PLACEHOLDER.fill_crescendo,
        )
    text = table(fitted)
    for row in ("rider_gap | [4.0, 14.0]", "accent | [2.0, 6.0]", "fill_crescendo | 11.0"):
        assert f"| {row} | kept | kept | kept |" in text


def test_the_riders_keep_appendix_a_s_noise_below_the_fitted_noise(fitted: Fit) -> None:
    for style in fitted.styles.values():
        assert style.rider_noise_sd == PLACEHOLDER.rider_noise_sd == 2.5
        assert style.rider_noise_sd < style.noise_sd
    assert "| rider_noise_sd | 2.5 | kept | kept | kept |" in table(fitted)


def test_the_fit_measures_the_riders_noise_it_keeps_less_the_energy_drift(
    fitted: Fit,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    within = drift_variance(2.0, (64.0,))
    # The velocity grooves built here measure a rider noise of 6 and 5, and the others none.
    assert fitted.rider_noise == Measured(round(math.sqrt(36 - within), 2), 100)
    assert fitted.alternating_noise == Measured(round(math.sqrt(25 - within), 2), 100)
    monkeypatch.setattr(calibrate, "data_dir", lambda: tmp_path)

    _fit([FileResult(path="a/x.mid", folder="a", grooves=grooves())], check=False)

    assert (
        f"rider_noise_sd kept at the placeholder's 2.5 (ADR 0076); the grooves give "
        f"{fitted.rider_noise.value} over 100 grooves, and {fitted.alternating_noise.value} on "
        "the alternating quarter-note hits alone over 100"
    ) in capsys.readouterr().out


def test_a_style_file_reads_back_as_the_style(fitted: Fit) -> None:
    for style in (PLACEHOLDER, *fitted.styles.values()):
        text = style_toml(style)

        assert Style.model_validate_json(json.dumps(tomllib.loads(text))) == style
        assert text.startswith(f"# The `{style.name}` style")


def test_too_few_grooves_keep_the_placeholder() -> None:
    few = [velocity_groove(60 + step, "a/p") for step in range(MIN_GROOVES - 1)]
    few.append(timing_groove(2.0, 1.0, 120.0, "a/p"))
    few += [timing_groove(4.0, 2.0, 120.0, "a/p"), timing_groove(8.0, 3.0, 120.0, "a/p")]

    found = fit([FileResult(path="a/x.mid", folder="a", grooves=few)])

    style = found.styles["tight"]
    assert style.velocity["kick"].full == PLACEHOLDER.velocity["kick"].full
    assert "velocity.kick.full: kept" in found.fallbacks
    assert any("takes the style's pooled timing" in fallback for fallback in found.fallbacks)


def test_contradictions_name_what_runs_against_appendix_a(fitted: Fit) -> None:
    assert contradictions(fitted) == []
    tight = fitted.styles["tight"]
    late = tight.timing[0].model_copy(
        update={"limb_ms": {"snare": -1.0, "rider": 0.5, "other": 0.0}}
    )
    wrong = tight.model_copy(
        update={
            "velocity": tight.velocity | {"kick": Anchors(full=100, half=110, low=90, band=6)},
            "feel_ms": (1.0, 2.0),
            "timing": (late, tight.timing[1]),
            "fill_crescendo": 0.0,
        }
    )

    problems = contradictions(replace(fitted, styles=fitted.styles | {"tight": wrong}))

    assert any("kick's velocity falls" in problem for problem in problems)
    assert any("kick at energy 1.0 is 100" in problem for problem in problems)
    assert any("pushed side" in problem for problem in problems)
    assert any("the snare plays early" in problem for problem in problems)
    assert any("crescendo doesn't rise" in problem for problem in problems)


def test_an_accepted_contradiction_is_printed_and_the_check_still_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # As in the performed grooves: `medium` pushes further than it lays back, and `loose`'s riders
    # play early at fast tempos.
    found: list[Groove] = []
    for groove in grooves():
        if groove.spread_ms == 4.0 and groove.feel_ms is not None:
            groove = replace(groove, feel_ms=-groove.feel_ms)
        if groove.spread_ms == 8.0 and groove.detail.bpm >= 150:
            groove = replace(
                groove, detail=replace(groove.detail, limbs={"snare": 1.0, "rider": -1.0})
            )
        found.append(groove)
    results = [FileResult(path="a/x.mid", folder="a", grooves=found)]
    monkeypatch.setattr(calibrate, "data_dir", lambda: tmp_path)

    assert _fit(results, check=False) == 0
    assert _fit(results, check=True) == 0

    text = capsys.readouterr().out
    assert "contradicts: medium: feel's pushed side, 2.0, isn't under its laid-back 1.0" in text
    assert "contradicts: loose, tempo band 1: the rider plays early, -1.0 ms" in text


def test_the_drift_within_a_groove_is_the_engine_s_own() -> None:
    assert QUARTERS == 64
    within = drift_variance(PLACEHOLDER.drift_sd, PLACEHOLDER.drift_quarters)
    assert 0 < within < PLACEHOLDER.drift_sd**2
    assert drift_variance(PLACEHOLDER.drift_sd, PLACEHOLDER.drift_quarters) == within
