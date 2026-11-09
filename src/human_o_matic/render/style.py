"""Styles: the numbers a performance is drawn from, before the controls shape them.

A style gives each role's velocity center at energy 1.0, 0.5 and 0.2, and the spreads, gaps and
offsets the compiler scales by the controls (`compiler.py`). It also gives the controls' defaults,
which a section's and the song's controls override.

The only style until calibration is `tight`, and its numbers are placeholders: the plan's
Appendix A, with the values it leaves out set as ADR 0051 records. Calibration replaces them
with statistics of performed MIDI, and adds `medium` and `loose` (ADR 0044). Every time in the
style is in milliseconds, and every length in quarter notes.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from human_o_matic.controls import Controls, StyleName
from human_o_matic.render.parts import LIMBS, METRIC_LEVELS, ROLES, Limb, Role

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


class Style(BaseModel):
    """The numbers of one style."""

    model_config = _FROZEN

    name: StyleName
    placeholder: bool
    """Whether the numbers are placeholders that calibration hasn't replaced yet."""
    defaults: Controls
    velocity: dict[Role, Anchors]
    """Each role's velocity centers."""
    noise_sd: float
    """The spread of a note's velocity about its center, at `dynamic_range` 0.5."""
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
    shared_sd: float
    """The spread of the offset all hits of one onset share, at `tightness` 0.5."""
    jitter_sd: tuple[float, float]
    """The spread of each hit's own offset at `tightness` 0 and 1."""
    jitter_clip: float
    """Each hit's own offset is cut to this either way."""
    limb_ms: dict[Limb, float]
    """Each limb's mean offset."""
    feel_ms: tuple[float, float]
    """The snare's and riders' offset at `feel` +1, laid back, and how early at -1, pushed."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        missing = [role for role in ROLES if role not in self.velocity]
        if missing:
            raise ValueError(f"the style has no velocities for {', '.join(missing)}")
        if len(self.fill_metric) != METRIC_LEVELS:
            raise ValueError(f"fill_metric has {METRIC_LEVELS} values, one per metric level")
        if any(limb not in self.limb_ms for limb in LIMBS):
            raise ValueError("limb_ms has an offset for every limb")
        return self


_SNARE = Anchors(full=106, half=88, low=68)
"""The plan's other normal snare, which fills and the roles without a row of their own take."""

TIGHT = Style(
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
    noise_sd=2.5,
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
    shared_sd=2.2,
    jitter_sd=(3, 1.8),
    jitter_clip=4,
    limb_ms={"snare": 1.0, "rider": 0.7, "other": 0.0},
    feel_ms=(6, 3),
)
"""The `tight` style's placeholders (ADR 0051)."""

STYLES: dict[StyleName, Style] = {"tight": TIGHT}
"""The built-in styles by name."""
