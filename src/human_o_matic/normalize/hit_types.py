"""Hit types: soft, normal or accent, read from each drum family's velocities.

A family's velocities are clustered in one dimension into at most three groups, by optimal
k-means (an exact dynamic program over the distinct velocities, so the result never depends on
a starting guess). A clustering is accepted only when every group has at least `MIN_GROUP`
notes and each pair of neighbouring groups is clearly apart: their means at least `MIN_STEP`
velocities and at least `SEPARATION` pooled standard deviations apart. Splitting one smooth
spread in two gives about 2.7 standard deviations for a normal spread and 3.5 for a uniform one,
so neither passes, and the margin above that keeps a few dozen notes from splitting by chance.
Three groups are tried first, then two. The groups are then named from the main level:
- normal is the largest group whose mean is above `SOFT_RATIO` of the loudest group's, the
  louder of two that tie;
- a quieter group is soft when its mean is at most `SOFT_RATIO` of normal's, as ghost notes
  under backbeats are, and otherwise normal too;
- a louder group is an accent.
Without such groups every note is normal, at low confidence, so the agent asks. The input is
flat when no two of the family's velocities are `MIN_STEP` apart, as with one velocity or one
note, and one group when they spread without clear groups. An answer gives a family's types as
velocity bounds instead, and is not a guess.

After this the input velocities are not used again, except to write a `skip` section back as it
came in, which the score's source notes allow.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, Self

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.schema import Confidence

type HitType = Literal["soft", "normal", "accent"]
type HitTypeReason = Literal["clusters", "flat", "one_group", "answer"]
"""How a family's types were found: `clusters` in its velocities; `flat`, too little spread to
cluster; `one_group`, a spread with no clear groups; or given in an `answer`."""
type IntArray = npt.NDArray[np.int64]

HIT_TYPES: tuple[HitType, ...] = ("soft", "normal", "accent")
MAX_GROUPS = 3
MIN_GROUP = 2
"""Each group has at least this many notes."""
MIN_STEP = 10.0
"""Neighbouring groups' means are at least this many velocities apart."""
SEPARATION = 5.0
"""Neighbouring groups' means are at least this many pooled standard deviations apart."""
SOFT_RATIO = 0.6
"""A group is soft when its mean is at most this share of the normal group's."""


class HitTypeBounds(BaseModel):
    """An answer for one family: velocities below `soft_below` are soft, those from
    `accent_from` up are accents, and the rest are normal. Leaving both out makes all normal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    soft_below: int | None = Field(default=None, ge=1, le=128)
    accent_from: int | None = Field(default=None, ge=1, le=128)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (
            self.soft_below is not None
            and self.accent_from is not None
            and self.soft_below > self.accent_from
        ):
            raise ValueError("soft_below is above accent_from")
        return self


class FamilyHitTypes(BaseModel):
    """How one family's notes were typed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: str
    reason: HitTypeReason
    confidence: Confidence
    """`high` for clear groups or an answer, and `low` when the types are a guess."""
    counts: dict[HitType, int]
    """How many notes have each type, for the types that occur."""
    velocities: dict[HitType, tuple[int, int]]
    """The lowest and highest input velocity of each type that occurs."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Typed:
    """The hit type of each note, in the order given, and each family's summary."""

    types: tuple[HitType, ...]
    confidences: tuple[Confidence, ...]
    families: tuple[FamilyHitTypes, ...]
    """In the order the families first appear."""


def groups(velocities: npt.ArrayLike, count: int) -> IntArray:
    """The optimal 1-D k-means partition of `velocities` into at most `count` groups: each
    velocity's group, numbered from 0 for the lowest. Ties go to the earliest split."""
    values = np.asarray(velocities, dtype=np.float64).ravel()
    distinct, inverse, weights = np.unique(values, return_inverse=True, return_counts=True)
    size = distinct.size
    count = max(1, min(count, size))
    w = np.concatenate(([0.0], np.cumsum(weights)))
    wx = np.concatenate(([0.0], np.cumsum(weights * distinct)))
    wxx = np.concatenate(([0.0], np.cumsum(weights * distinct**2)))
    # cost[i, j]: the squared error of one group holding distinct values i to j.
    i, j = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    n = w[j + 1] - w[i]
    s = wx[j + 1] - wx[i]
    with np.errstate(divide="ignore", invalid="ignore"):
        cost = np.where(j >= i, (wxx[j + 1] - wxx[i]) - s * s / n, np.inf)
    best = cost[0].copy()
    """The least error of values 0 to j in the groups so far."""
    splits: list[npt.NDArray[np.intp]] = []
    for _ in range(1, count):
        # Values 0 to i - 1 in the earlier groups, and i to j in a new one.
        total = np.full((size, size), np.inf)
        total[1:] = best[:-1, np.newaxis] + cost[1:]
        start = np.argmin(total, axis=0)
        splits.append(start)
        best = total[start, np.arange(size)]
    labels = np.zeros(size, dtype=np.int64)
    end = size - 1
    for group in range(count - 1, 0, -1):
        start = int(splits[group - 1][end])
        labels[start : end + 1] = group
        end = start - 1
    return labels[inverse]


def _separated(values: npt.NDArray[np.float64], labels: IntArray, count: int) -> bool:
    members = [values[labels == group] for group in range(count)]
    if any(group.size < MIN_GROUP for group in members):
        return False
    for a, b in pairwise(members):
        apart = float(b.mean() - a.mean())
        pooled = float(np.sqrt((a.size * a.var() + b.size * b.var()) / (a.size + b.size)))
        if apart < MIN_STEP or (pooled > 0 and apart / pooled < SEPARATION):
            return False
    return True


def _names(values: npt.NDArray[np.float64], labels: IntArray, count: int) -> list[HitType]:
    """Each group's hit type, from the lowest group up."""
    means = [float(values[labels == group].mean()) for group in range(count)]
    sizes = [int((labels == group).sum()) for group in range(count)]
    loud = [group for group in range(count) if means[group] > SOFT_RATIO * means[-1]]
    normal = max(loud, key=lambda group: (sizes[group], group))
    names: list[HitType] = []
    for group in range(count):
        if group > normal:
            names.append("accent")
        elif group < normal and means[group] <= SOFT_RATIO * means[normal]:
            names.append("soft")
        else:
            names.append("normal")
    return names


def classify(velocities: Sequence[int]) -> tuple[tuple[HitType, ...], HitTypeReason]:
    """The hit types of one family's velocities, and how they were found."""
    values = np.asarray(velocities, dtype=np.float64)
    if values.size == 0:
        return (), "flat"
    if float(values.max() - values.min()) < MIN_STEP:
        return _all_normal(values.size), "flat"
    for count in range(MAX_GROUPS, 1, -1):
        labels = groups(values, count)
        if int(labels.max()) + 1 == count and _separated(values, labels, count):
            names = _names(values, labels, count)
            return tuple(names[int(label)] for label in labels), "clusters"
    return _all_normal(values.size), "one_group"


def _all_normal(count: int) -> tuple[HitType, ...]:
    return tuple("normal" for _ in range(count))


def _bounded(velocities: Sequence[int], bounds: HitTypeBounds) -> tuple[HitType, ...]:
    def one(velocity: int) -> HitType:
        if bounds.soft_below is not None and velocity < bounds.soft_below:
            return "soft"
        if bounds.accent_from is not None and velocity >= bounds.accent_from:
            return "accent"
        return "normal"

    return tuple(one(velocity) for velocity in velocities)


def type_hits(
    families: Sequence[str],
    velocities: Sequence[int],
    answers: Mapping[str, HitTypeBounds] | None = None,
) -> Typed:
    """The hit type of each note, given each note's family and input velocity. `answers` gives
    a family's types as bounds instead of clustering."""
    given = answers or {}
    members: dict[str, list[int]] = {}
    for position, family in enumerate(families):
        members.setdefault(family, []).append(position)
    types: list[HitType] = ["normal"] * len(families)
    confidences: list[Confidence] = ["low"] * len(families)
    summaries: list[FamilyHitTypes] = []
    for family, positions in members.items():
        values = [velocities[position] for position in positions]
        if family in given:
            found, reason = _bounded(values, given[family]), "answer"
        else:
            found, reason = classify(values)
        confidence: Confidence = "high" if reason in ("clusters", "answer") else "low"
        for position, hit_type in zip(positions, found, strict=True):
            types[position] = hit_type
            confidences[position] = confidence
        summaries.append(_summary(family, reason, confidence, found, values))
    return Typed(types=tuple(types), confidences=tuple(confidences), families=tuple(summaries))


def _summary(
    family: str,
    reason: HitTypeReason,
    confidence: Confidence,
    types: Sequence[HitType],
    velocities: Sequence[int],
) -> FamilyHitTypes:
    counts: dict[HitType, int] = {}
    ranges: dict[HitType, tuple[int, int]] = {}
    for hit_type in HIT_TYPES:
        found = [v for t, v in zip(types, velocities, strict=True) if t == hit_type]
        if found:
            counts[hit_type] = len(found)
            ranges[hit_type] = (min(found), max(found))
    return FamilyHitTypes(
        family=family, reason=reason, confidence=confidence, counts=counts, velocities=ranges
    )


def hit_types_request(families: Sequence[FamilyHitTypes]) -> DecisionRequest | None:
    """A request to confirm the hit types, or None when every family was given in an answer."""
    asked = [summary for summary in families if summary.reason != "answer"]
    if not asked:
        return None
    parts = "; ".join(_describe(summary) for summary in asked)
    guessed = [summary.family for summary in asked if summary.confidence == "low"]
    question = "Do these look right?"
    if guessed:
        question = (
            f"On {_listing(guessed)} the velocities show no clear groups, so every note is taken "
            "as normal. Are any of them soft notes or accents? Do the others look right?"
        )
    details: list[JsonValue] = [summary.model_dump(mode="json") for summary in asked]
    return DecisionRequest(
        kind="hit_types",
        message=f"Hit types read from the velocities: {parts}. {question}",
        answer_with=("hit_types",),
        details={"families": details},
    )


def _describe(summary: FamilyHitTypes) -> str:
    """For example "snare: 34 soft (velocity 20 to 58), 120 normal (velocity 96 to 127)"."""
    listed: list[str] = []
    for hit_type, count in summary.counts.items():
        low, high = summary.velocities[hit_type]
        span = f"{low} to {high}" if low != high else str(low)
        listed.append(f"{count} {hit_type} (velocity {span})")
    return f"{summary.family}: {', '.join(listed)}"


def _listing(names: Sequence[str]) -> str:
    """For example "kick", "kick and hat" or "kick, hat and tom"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
