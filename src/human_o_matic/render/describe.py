"""How a section came out, by role, in numbers and in plain words (ADR 0083).

The notes are a section's as rendered, so the words say what its controls give in this take, not
what a model of the engine expects: each role's velocities from the 5th to the 95th percentile,
the riders' strong hits against their weak ones, the timing spread and how far the snare and the
riders sit behind the other notes. `set_section_controls` says these after storing a section's
controls, and `render` beside its statistics. Notes played as they came in aren't described.
"""

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from human_o_matic.render.engine import RenderedNote
from human_o_matic.render.measure import rider_gap, timing_spread
from human_o_matic.render.parts import Role

GROUPS: tuple[tuple[str, tuple[Role, ...]], ...] = (
    ("kick", ("kick", "double_kick")),
    ("backbeats", ("backbeat",)),
    ("other snare", ("snare",)),
    ("riders", ("rider",)),
    ("accents", ("accent_cymbal",)),
    ("fills", ("fill",)),
    ("other drums", ("other",)),
)
"""The roles described together, in the order the words give them. Soft-typed notes are their
own group, `soft notes`, whatever their role."""
LOW, HIGH = 5, 95
"""The percentiles a role's velocities are given between."""
FEW = 5
"""With fewer notes than this a role's range is its lowest to its highest."""


class Span(BaseModel):
    """A group's velocities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    notes: int
    low: int
    high: int


class Sound(BaseModel):
    """How a section came out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    velocities: dict[str, Span]
    """Per group of roles, in the order of `GROUPS`, and `soft notes`."""
    rider_gap: float | None
    """How much louder the riders' strong hits are than their weak ones."""
    timing_spread_ms: float | None
    behind_ms: float | None
    """How far the snare and the riders sit behind the other notes, on average."""
    says: str


def _span(velocities: Sequence[int]) -> Span:
    values = np.array(velocities, dtype=np.float64)
    if values.size < FEW:
        low, high = values.min(), values.max()
    else:
        low, high = np.percentile(values, LOW), np.percentile(values, HIGH)
    return Span(notes=int(values.size), low=round(float(low)), high=round(float(high)))


def sound(notes: Sequence[RenderedNote]) -> Sound:
    """How a section's rendered notes came out."""
    played = [note for note in notes if not note.kept]
    spans: dict[str, Span] = {}
    names: dict[str, str] = {}
    for group, roles in GROUPS:
        mine = [note for note in played if note.part.role in roles and note.hit_type != "soft"]
        if mine:
            spans[group] = _span([note.note.velocity for note in mine])
            if group in ("riders", "accents"):
                families = sorted({note.family for note in mine})
                names[group] = (
                    " and ".join(families)
                    if group == "riders"
                    else (f"{' and '.join(families)} accents")
                )
    soft = [note.note.velocity for note in played if note.hit_type == "soft"]
    if soft:
        spans["soft notes"] = _span(soft)
    gap = rider_gap(played)
    spread = timing_spread(played)
    behind = _behind(played)
    return Sound(
        velocities=spans,
        rider_gap=round(gap, 1) if gap is not None else None,
        timing_spread_ms=round(spread, 1) if spread is not None else None,
        behind_ms=round(behind, 1) if behind is not None else None,
        says=_says(notes, spans, names, gap, spread, behind),
    )


def _behind(notes: Sequence[RenderedNote]) -> float | None:
    mains = [note for note in notes if not note.grace]
    feel = [note.offset_ms for note in mains if note.part.limb in ("snare", "rider")]
    others = [note.offset_ms for note in mains if note.part.limb == "other"]
    if not feel or not others:
        return None
    return float(np.mean(feel) - np.mean(others))


def _says(
    notes: Sequence[RenderedNote],
    spans: dict[str, Span],
    names: dict[str, str],
    gap: float | None,
    spread: float | None,
    behind: float | None,
) -> str:
    if not notes:
        return "no notes"
    if all(note.kept for note in notes):
        return "played as it came in"
    parts: list[str] = []
    for group, span in spans.items():
        words = f"{names.get(group, group)} about {span.low} to {span.high}"
        if group == "riders" and gap is not None:
            words += f", strong hits {gap:.0f} above weak"
        parts.append(words)
    said = "; ".join(parts)
    timing: list[str] = []
    if spread is not None:
        timing.append(f"timing spread about {spread:.1f} ms")
    if behind is not None and abs(behind) >= 0.05:
        side = "behind" if behind > 0 else "ahead of"
        timing.append(f"snare and riders {abs(behind):.1f} ms {side} the rest")
    return "; ".join([said, ", ".join(timing)]) if timing else said
