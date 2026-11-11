"""The parametric backend: one section's velocities and offsets, drawn from its parameters.

It draws, in this order and whatever the notes' roles and types, one normal value per onset for
the offset its hits share, then per note one for its own jitter, one for its velocity and one
uniform value that may swap a rider's label. So the draws depend only on how many notes and
onsets the section has, and the same section and stream always draw the same numbers.

A note's velocity is its role's center at its energy, moved by what its part, its metric level
and its type add, plus noise, a rider's with its own smaller spread so its strong and weak hits
stay apart (ADR 0076). A rider's strong hits are half its gap above its center and its weak
hits half below, unless that takes the strong ones within a spread of its noise of 127: then
they are that spread below 127 and the weak ones the whole gap below them, so their noise is
seldom reflected and the gap holds at full energy (ADR 0077). A soft-typed note is drawn about
the soft center instead, whatever its role. Its offset is its limb's, the onset's shared
offset and its own jitter, cut to the clip. A grace's offset is left at 0, since the guards give
it its main note's. The song's drifts and the guards come after (`render/engine.py`,
`render/guards.py`), so they hold for every backend."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from human_o_matic.normalize.score import ScoreNote
from human_o_matic.render.compiler import Params
from human_o_matic.render.guards import MAX_VELOCITY
from human_o_matic.render.parts import Part

type FloatArray = npt.NDArray[np.float64]
type BoolArray = npt.NDArray[np.bool_]


@dataclass(frozen=True, slots=True, kw_only=True)
class Draw:
    """One section's draws, in the order of the notes given."""

    velocities: FloatArray
    """Before the song's energy drift and the guards."""
    floors: FloatArray
    """The lowest velocity each may take before it is reflected."""
    offsets_ms: FloatArray
    """Before the song's timing drift and the guards."""
    strong: BoolArray
    """Whether an alternating rider hit was drawn strong. False for every other note."""


def sample(
    notes: Sequence[ScoreNote],
    parts: Sequence[Part],
    places: Sequence[float],
    params: Params,
    rng: np.random.Generator,
) -> Draw:
    """Draw one section's notes, given with their parts and their places in the section, from 0
    at its start to 1 at its end."""
    count = len(notes)
    onsets = sorted({note.tick for note in notes if note.grace_of is None})
    onset_of = {tick: number for number, tick in enumerate(onsets)}
    shared = rng.standard_normal(len(onsets))
    jitter = rng.standard_normal(count)
    noise = rng.standard_normal(count)
    swaps = rng.random(count)

    velocities = np.zeros(count)
    floors = np.ones(count)
    offsets = np.zeros(count)
    strong = np.zeros(count, dtype=np.bool_)
    for position, (note, part, place) in enumerate(zip(notes, parts, places, strict=True)):
        energy = params.energy_at(place)
        if note.hit_type == "soft":
            velocities[position] = params.soft_center(energy) + params.soft_sd * noise[position]
        else:
            center = params.center(part.role, energy)
            floors[position] = max(params.floor(part.role, energy), 1.0)
            if part.role == "fill":
                center += params.fill_shift + params.fill_metric[part.metric]
                center += params.fill_hand * part.hand + params.fill_crescendo * part.crescendo
            elif part.role == "double_kick":
                center += params.feet * part.foot
            elif part.role == "rider" and part.rider != "center":
                is_strong = part.rider == "alternate" and (
                    part.strong != (swaps[position] < params.rider_swap)
                )
                strong[position] = is_strong
                top = min(center + params.rider_gap / 2, MAX_VELOCITY - params.rider_noise_sd)
                center = top if is_strong else top - params.rider_gap
            if part.role != "fill":
                center += params.metric_velocity[part.role][part.metric]
            if note.hit_type == "accent":
                center += params.accent_at(energy)
            if part.limb == "snare":
                center += params.snare_loudness
            spread = params.rider_noise_sd if part.role == "rider" else params.noise_sd
            velocities[position] = center + spread * noise[position]
        if note.grace_of is None:
            own = params.jitter_sd * jitter[position]
            offsets[position] = (
                params.limb_ms[part.limb]
                + params.shared_sd * shared[onset_of[note.tick]]
                + min(max(own, -params.jitter_clip), params.jitter_clip)
            )
    return Draw(velocities=velocities, floors=floors, offsets_ms=offsets, strong=strong)
