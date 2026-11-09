"""Measuring a render: the statistic each control mainly drives, per section (ADR 0052).

Each statistic takes the rendered notes of one section, or any set of them, and is None when the
notes it needs aren't there. Notes played as they came in aren't measured. `section_stats` is
what `human-o-matic render` prints for a section, and the other functions are what the tests that
each control moves its statistic measure:

| Control | Statistic |
|---|---|
| `energy` | `mean_velocity` of normal-typed notes |
| `groove` | `accent_contrast`, the soft notes' `mean_velocity`, and `rider_gap` |
| `dynamic_range` | `rider_gap` and `velocity_spread` |
| `tightness` | `timing_spread`, which falls as it rises |
| `feel` | `feel_offset`, and the snare's `mean_velocity` when laid back |
| `arc` | `velocity_trend`: `drop` below `steady` below `build` |
| `fill_intensity` | the fills' `mean_velocity` and `fill_rise` |
| `ghost_level` | the soft notes' `mean_velocity` |
"""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from human_o_matic.normalize.hit_types import HitType
from human_o_matic.render.engine import RenderedNote
from human_o_matic.render.parts import Role


class SectionStats(BaseModel):
    """What one section came out as."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    notes: int
    velocity: float | None
    """The mean velocity of the notes not typed soft."""
    lowest: int | None
    highest: int | None
    soft: float | None
    """The mean velocity of the soft-typed notes."""
    accent_contrast: float | None
    timing_spread_ms: float | None
    mean_offset_ms: float | None


def _rendered(notes: Sequence[RenderedNote]) -> list[RenderedNote]:
    return [note for note in notes if not note.kept]


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def mean_velocity(
    notes: Sequence[RenderedNote],
    *,
    hit_types: Sequence[HitType] = ("normal",),
    roles: Sequence[Role] | None = None,
    families: Sequence[str] | None = None,
) -> float | None:
    """The mean velocity of the notes of those hit types, and of those roles and families when
    given."""
    chosen = [
        note.note.velocity
        for note in _rendered(notes)
        if note.hit_type in hit_types
        and (roles is None or note.part.role in roles)
        and (families is None or note.family in families)
    ]
    return float(np.mean(chosen)) if chosen else None


def accent_contrast(notes: Sequence[RenderedNote]) -> float | None:
    """How much louder accent-typed notes are than normal ones, on average over the drums that
    have both."""
    gaps: list[float] = []
    for drum in {(note.family, note.piece) for note in _rendered(notes)}:
        mine = [note for note in notes if (note.family, note.piece) == drum]
        accent = mean_velocity(mine, hit_types=("accent",))
        normal = mean_velocity(mine)
        if accent is not None and normal is not None:
            gaps.append(accent - normal)
    return float(np.mean(gaps)) if gaps else None


def velocity_spread(notes: Sequence[RenderedNote]) -> float | None:
    """The mean, over drums with two or more, of the spread of the normal-typed notes'
    velocities."""
    drums: dict[tuple[str, int], list[int]] = {}
    for note in _rendered(notes):
        if note.hit_type == "normal":
            drums.setdefault((note.family, note.piece), []).append(note.note.velocity)
    spreads = [float(np.std(velocities)) for velocities in drums.values() if len(velocities) > 1]
    return float(np.mean(spreads)) if spreads else None


def rider_gap(notes: Sequence[RenderedNote]) -> float | None:
    """How much louder the strong alternating rider hits are than the weak ones."""
    alternating = [
        note
        for note in _rendered(notes)
        if note.part.rider == "alternate" and note.hit_type != "soft"
    ]
    strong = [note.note.velocity for note in alternating if note.strong]
    weak = [note.note.velocity for note in alternating if not note.strong]
    return float(np.mean(strong) - np.mean(weak)) if strong and weak else None


def timing_spread(notes: Sequence[RenderedNote]) -> float | None:
    """The spread of the notes' offsets from the grid, graces left out, in milliseconds."""
    offsets = [note.offset_ms for note in _rendered(notes) if not note.grace]
    return float(np.std(offsets)) if len(offsets) > 1 else None


def mean_offset(notes: Sequence[RenderedNote]) -> float | None:
    offsets = [note.offset_ms for note in _rendered(notes) if not note.grace]
    return float(np.mean(offsets)) if offsets else None


def feel_offset(notes: Sequence[RenderedNote]) -> float | None:
    """The mean offset of the snare and the riders, which `feel` moves."""
    return mean_offset([note for note in notes if note.part.limb in ("snare", "rider")])


def velocity_trend(notes: Sequence[RenderedNote]) -> float | None:
    """How much the velocity of the notes not typed soft rises from the first to the last, on
    the straight line that fits them best."""
    chosen = [note for note in _rendered(notes) if note.hit_type != "soft"]
    ticks = np.array([note.note.start for note in chosen], dtype=np.float64)
    if len(chosen) < 2 or ticks.max() == ticks.min():
        return None
    velocities = np.array([note.note.velocity for note in chosen], dtype=np.float64)
    slope = float(np.polyfit(ticks, velocities, 1)[0])
    return slope * float(ticks.max() - ticks.min())


def fill_rise(notes: Sequence[RenderedNote]) -> float | None:
    """How much louder the fill notes in the second half of their crescendo are than the
    others."""
    fills = [note for note in _rendered(notes) if note.part.role == "fill"]
    late = [note.note.velocity for note in fills if note.part.crescendo > 0.5]
    early = [note.note.velocity for note in fills if note.part.crescendo <= 0.5]
    return float(np.mean(late) - np.mean(early)) if late and early else None


def section_stats(notes: Sequence[RenderedNote]) -> SectionStats:
    """The statistics `human-o-matic render` prints for a section."""
    velocities = [note.note.velocity for note in _rendered(notes)]
    return SectionStats(
        notes=len(notes),
        velocity=_round(mean_velocity(notes, hit_types=("normal", "accent"))),
        lowest=min(velocities, default=None),
        highest=max(velocities, default=None),
        soft=_round(mean_velocity(notes, hit_types=("soft",))),
        accent_contrast=_round(accent_contrast(notes)),
        timing_spread_ms=_round(timing_spread(notes)),
        mean_offset_ms=_round(mean_offset(notes)),
    )
