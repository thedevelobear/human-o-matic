"""Compiling one section's controls with the style into what the backend draws from.

The compiled parameters are the style's numbers scaled by the controls, as ADR 0051 sets out:
the spreads, gaps and offsets are plain numbers, and what depends on a note's energy, its
velocity center, its accent and its soft center, is worked out per note from the energy the arc
gives its place in the section. The timing is the style's for the tempo band of the section's
tempo. `roles=False` is `generic` mode: no limb takes an offset of its own, and `feel` moves every
note.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from math import sqrt

from human_o_matic.controls import Controls
from human_o_matic.render.parts import LIMBS, Limb, Role
from human_o_matic.render.style import Anchors, Style

ARC_SIGN = {"steady": 0.0, "build": 1.0, "drop": -1.0}


@dataclass(frozen=True, slots=True, kw_only=True)
class Params:
    """One section's parameters."""

    controls: Controls
    velocity: Mapping[Role, Anchors]
    metric_velocity: Mapping[Role, tuple[float, ...]]
    """What a note of each role adds by its metric level."""
    arc_span: float
    noise_sd: float
    """The spread of a velocity about its center."""
    rider_noise_sd: float
    """The same for a rider hit not typed soft."""
    feet: float
    rider_gap: float
    rider_swap: float
    """The chance an alternating rider hit takes the other label than its vote gives."""
    accent: tuple[float, float]
    """Two numbers `a` and `b`: an accent adds `a + b * energy`, with the groove already in."""
    soft: tuple[float, float]
    soft_mix: tuple[float, float, float]
    soft_sd: float
    fill_shift: float
    fill_metric: tuple[float, ...]
    fill_hand: float
    fill_crescendo: float
    snare_loudness: float
    shared_sd: float
    jitter_sd: float
    jitter_clip: float
    limb_ms: Mapping[Limb, float]
    """Each limb's offset, `feel` included."""

    def energy_at(self, place: float) -> float:
        """The energy at a place in the section, from 0 at its start to 1 at its end."""
        sign = ARC_SIGN[self.controls.arc]
        return self.controls.energy + sign * self.arc_span * (2 * place - 1)

    def center(self, role: Role, energy: float) -> float:
        return self.velocity[role].at(energy)

    def floor(self, role: Role, energy: float) -> float:
        """The lowest velocity of the role before a draw is reflected."""
        band = self.velocity[role].band
        return self.center(role, energy) - band if band is not None else 1.0

    def accent_at(self, energy: float) -> float:
        """How much louder an accent-typed note is than its center."""
        return self.accent[0] + self.accent[1] * energy

    def soft_center(self, energy: float) -> float:
        ghost, by_energy, by_groove = self.soft_mix
        mix = ghost * self.controls.ghost_level + by_energy * energy
        mix += by_groove * self.controls.groove
        return self.soft[0] + self.soft[1] * min(max(mix, 0.0), 1.0)


def swap_chance(flip: float) -> float:
    """The chance of swapping each label so neighbours that should differ do with chance `flip`:
    they differ when neither or both swap, `1 - 2q + 2q²`, which is `flip` at this `q`."""
    return (1 - sqrt(max(2 * flip - 1, 0.0))) / 2


def compile_section(controls: Controls, style: Style, bpm: float, *, roles: bool = True) -> Params:
    """The parameters of a section rendered with `controls`, in `style`, at `bpm`."""
    timing = style.timing_at(bpm)
    late, early = style.feel_ms
    feel = late * controls.feel if controls.feel >= 0 else early * controls.feel
    limb_ms: dict[Limb, float] = {}
    for limb in LIMBS:
        if roles:
            limb_ms[limb] = timing.limb_ms[limb] + (feel if limb != "other" else 0.0)
        else:
            limb_ms[limb] = feel
    gap_low, gap_high = style.rider_gap
    groove_base, groove_scale = style.rider_groove
    jitter_loose, jitter_tight = timing.jitter_sd
    accent_base, accent_energy = style.accent
    contrast = 0.5 + controls.groove
    return Params(
        controls=controls,
        velocity=style.velocity,
        metric_velocity=style.metric_velocity,
        arc_span=style.arc_span,
        noise_sd=style.noise_sd * (0.5 + controls.dynamic_range),
        rider_noise_sd=style.rider_noise_sd * (0.5 + controls.dynamic_range),
        feet=style.feet,
        rider_gap=(gap_low + (gap_high - gap_low) * controls.dynamic_range)
        * (groove_base + groove_scale * controls.groove),
        rider_swap=swap_chance(style.rider_flip),
        accent=(accent_base * contrast, accent_energy * contrast),
        soft=style.soft,
        soft_mix=style.soft_mix,
        soft_sd=style.soft_sd,
        fill_shift=style.fill_shift * (controls.fill_intensity - 0.5),
        fill_metric=style.fill_metric,
        fill_hand=style.fill_hand,
        fill_crescendo=style.fill_crescendo * controls.fill_intensity,
        snare_loudness=style.snare_loudness * max(controls.feel, 0.0) if roles else 0.0,
        shared_sd=timing.shared_sd * (1.5 - controls.tightness),
        jitter_sd=jitter_loose + (jitter_tight - jitter_loose) * controls.tightness,
        jitter_clip=timing.jitter_clip,
        limb_ms=limb_ms,
    )
