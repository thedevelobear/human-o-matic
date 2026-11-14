"""Styles: the numbers a performance is drawn from, before the controls shape them.

A style gives each role's velocity center at energy 1.0, 0.5 and 0.2, what a note adds by its
metric level, and the spreads, gaps and offsets the compiler scales by the controls
(`compiler.py`), its timing by tempo band. It also gives the controls' defaults, which a
section's and the song's controls override.

The built-in styles, `tight`, `medium` and `loose`, are fitted by calibration and read from
`data/styles/` (ADRs 0044, 0069, 0070), each checked as it loads. `PLACEHOLDER` is the plan's
Appendix A, with the values it leaves out set as ADR 0051 records: the fit keeps its values where
a performance can't give one (ADR 0068), and it is never rendered. Every time in the style is in
milliseconds, and every length in quarter notes.
"""

import bisect
import json
import tomllib
from functools import cache
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from human_o_matic.controls import Controls, StyleName
from human_o_matic.render.parts import LIMBS, METRIC_LEVELS, ROLES, Limb, Role
from human_o_matic.resources import data_dir

_FROZEN = ConfigDict(frozen=True, extra="forbid", strict=True)


class Anchors(BaseModel):
    """A role's velocity center at energy 1.0, 0.5 and 0.2, and its band."""

    model_config = _FROZEN

    full: float
    """At energy 1.0."""
    half: float
    """At energy 0.5."""
    low: float
    """At energy 0.2."""
    band: float | None = None
    """How far below the center the role's velocities reach before they are reflected, or None
    for no floor but velocity 1."""

    def at(self, energy: float) -> float:
        """The center at `energy`, on straight lines through the anchors. Below 0.2 the line from
        0.2 to 0.5 goes on, and above 1.0, which only an arc reaches, the line from 0.5 to 1.0."""
        if energy <= 0.5:
            return self.low + (self.half - self.low) * (energy - 0.2) / 0.3
        return self.half + (self.full - self.half) * (energy - 0.5) / 0.5


class Timing(BaseModel):
    """The timing of one tempo band."""

    model_config = _FROZEN

    shared_sd: float
    """The spread of the offset all hits of one onset share, at `tightness` 0.5."""
    jitter_sd: tuple[float, float]
    """The spread of each hit's own offset at `tightness` 0 and 1."""
    jitter_clip: float
    """Each hit's own offset is cut to this either way."""
    limb_ms: dict[Limb, float]
    """Each limb's mean offset."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if any(limb not in self.limb_ms for limb in LIMBS):
            raise ValueError("limb_ms has an offset for every limb")
        return self


class Style(BaseModel):
    """The numbers of one style."""

    model_config = _FROZEN

    name: StyleName
    placeholder: bool
    """Whether the numbers are placeholders that calibration hasn't replaced yet."""
    defaults: Controls
    velocity: dict[Role, Anchors]
    """Each role's velocity centers."""
    metric_velocity: dict[Role, tuple[float, ...]]
    """What a note of each role adds to its center on a quarter note, an 8th, a 16th and
    elsewhere, counted from the bar. A fill note takes `fill_metric` instead."""
    noise_sd: float
    """The spread of a note's velocity about its center, at `dynamic_range` 0.5, riders and
    soft-typed notes aside."""
    rider_noise_sd: float
    """The same for a rider hit not typed soft, smaller so its strong and weak hits stay apart
    (ADR 0076)."""
    feet: float
    """How much louder the right foot is than the center in double kick, and the left quieter."""
    rider_gap: tuple[float, float]
    """The gap between a rider's strong and weak hits at `dynamic_range` 0 and 1."""
    rider_groove: tuple[float, float]
    """The gap is scaled by the first plus the second times `groove`."""
    rider_flip: float
    """How often one alternating rider hit is strong and the next weak, or the other way."""
    accent: tuple[float, float]
    """An accent-typed note is louder than its center by the first plus the second times the
    energy, scaled by 0.5 plus `groove`."""
    soft: tuple[float, float]
    """A soft-typed note's center is the first plus the second times a mix of the controls."""
    soft_mix: tuple[float, float, float]
    """The weights of `ghost_level`, the energy and `groove` in that mix."""
    soft_sd: float
    fill_metric: tuple[float, ...]
    """What a fill note adds on a quarter note, an 8th, a 16th, and elsewhere."""
    fill_hand: float
    """What a fill's hands add and take away by turns."""
    fill_shift: float
    """A fill's notes are louder than the snare's center by this times `fill_intensity` less
    0.5."""
    fill_crescendo: float
    """The crescendo at a fill's end, times `fill_intensity`, over the fill's last 4 quarters at
    most (`instruments/drums.py`)."""
    snare_loudness: float
    """How much louder snare notes are at `feel` +1, and in proportion when laid back less."""
    arc_span: float
    """How far an arc's energy rises or falls either side of the section's own."""
    energy_drift_sd: float
    """The spread of the song's slow drift in velocity."""
    energy_drift_quarters: float
    """Its time constant."""
    drift_sd: float
    """The spread of the song's slow drift in timing, its processes together."""
    drift_quarters: tuple[float, ...]
    """Their time constants."""
    tempo_cuts: tuple[float, ...]
    """The tempos, in BPM, between the tempo bands, rising."""
    timing: tuple[Timing, ...]
    """Each tempo band's timing, from the slowest: one more than the cuts."""
    feel_ms: tuple[float, float]
    """The snare's and riders' offset at `feel` +1, laid back, and how early at -1, pushed."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        missing = [role for role in ROLES if role not in self.velocity]
        if missing:
            raise ValueError(f"the style has no velocities for {', '.join(missing)}")
        if len(self.fill_metric) != METRIC_LEVELS:
            raise ValueError(f"fill_metric has {METRIC_LEVELS} values, one per metric level")
        for role in ROLES:
            if len(self.metric_velocity.get(role, ())) != METRIC_LEVELS:
                raise ValueError(f"metric_velocity has {METRIC_LEVELS} values for {role}")
        if len(self.timing) != len(self.tempo_cuts) + 1:
            raise ValueError("the style has one timing more than it has tempo cuts")
        if list(self.tempo_cuts) != sorted(set(self.tempo_cuts)):
            raise ValueError("the tempo cuts rise")
        return self

    def timing_at(self, bpm: float) -> Timing:
        """The timing of the tempo band `bpm` falls in. A cut belongs to the faster band."""
        return self.timing[bisect.bisect_right(self.tempo_cuts, bpm)]


_SNARE = Anchors(full=106, half=88, low=68)
"""The plan's other normal snare, which fills and the roles without a row of their own take."""

PLACEHOLDER = Style(
    name="tight",
    placeholder=True,
    defaults=Controls(
        energy=0.5,
        groove=0.5,
        dynamic_range=0.5,
        tightness=0.75,
        feel=0.0,
        arc="steady",
        fill_intensity=0.5,
        ghost_level=0.5,
        skip=False,
        creative=False,
        ramp=0,
    ),
    velocity={
        "kick": Anchors(full=122, half=104, low=85, band=6),
        "double_kick": Anchors(full=118, half=100, low=82),
        "backbeat": Anchors(full=123, half=100, low=80, band=6),
        "snare": _SNARE,
        "rider": Anchors(full=114, half=95, low=72),
        "accent_cymbal": Anchors(full=122, half=105, low=85, band=8),
        "fill": _SNARE,
        "other": _SNARE,
    },
    metric_velocity=dict.fromkeys(ROLES, (0.0, 0.0, 0.0, 0.0)),
    noise_sd=2.5,
    rider_noise_sd=2.5,
    feet=3,
    rider_gap=(4, 14),
    rider_groove=(0.6, 0.8),
    rider_flip=0.775,
    accent=(2, 6),
    soft=(25, 30),
    soft_mix=(0.6, 0.2, 0.2),
    soft_sd=2.5,
    fill_metric=(6, 5, 2, 0),
    fill_hand=2,
    fill_shift=6,
    fill_crescendo=11,
    snare_loudness=4,
    arc_span=0.15,
    energy_drift_sd=2,
    energy_drift_quarters=64,
    drift_sd=2.5,
    drift_quarters=(16, 64, 256),
    tempo_cuts=(),
    timing=(
        Timing(
            shared_sd=2.2,
            jitter_sd=(3, 1.8),
            jitter_clip=4,
            limb_ms={"snare": 1.0, "rider": 0.7, "other": 0.0},
        ),
    ),
    feel_ms=(6, 3),
)
"""Appendix A's placeholders, with the values it leaves out filled in (ADR 0051)."""

STYLE_NAMES: tuple[StyleName, ...] = ("tight", "medium", "loose")
"""The built-in styles, from the tightest. `tight` is the default."""


class StyleError(ValueError):
    """A built-in style file is missing or invalid."""


def load_style(path: Path) -> Style:
    """A style file, checked. Raises `StyleError` naming the file and what is wrong."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        return Style.model_validate_json(json.dumps(data))
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise StyleError(f"{path}: {error}") from error


@cache
def built_in_styles() -> dict[StyleName, Style]:
    """The styles in `data/styles/`, by name, each read from `<name>.toml` (ADR 0070)."""
    found: dict[StyleName, Style] = {}
    for name in STYLE_NAMES:
        style = load_style(data_dir() / "styles" / f"{name}.toml")
        if style.name != name:
            raise StyleError(f"data/styles/{name}.toml holds the style {style.name}")
        found[name] = style
    return found
