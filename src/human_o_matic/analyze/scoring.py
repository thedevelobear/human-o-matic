"""How well detected section boundaries match hand-labelled ones (ADR 0034).

A boundary is a section start other than bar 0, which starts every song and is never counted.
A detected boundary matches a labelled one at most `TOLERANCE` bars away, and each boundary is
in at most one match: the matches are as many as such a one-to-one pairing allows. With `m`
matches, `d` detected and `l` labelled boundaries, a track's precision is `m / d` (0 when `d` is
0), its recall `m / l`, and its F1 `2m / (d + l)`.

Over several tracks the headline is the mean of their F1, so each counts the same however long
it is. Beside it are the pooled F1, `2Σm / (Σd + Σl)`, and the mean F1 of the tracks not marked
as tuned, which the detector's parameters were not fitted to. The exit holds when at least
`EXIT_TRACKS` tracks have a mean F1 of at least `EXIT_F1`.
"""

from collections.abc import Sequence
from dataclasses import dataclass

TOLERANCE = 1
"""How many bars apart a detected and a labelled boundary may be and still match."""
EXIT_TRACKS = 10
"""How many labelled tracks the exit is measured on, at least."""
EXIT_F1 = 0.70
"""The mean F1 the exit needs."""


def match_boundaries(
    detected: Sequence[int], labelled: Sequence[int], tolerance: int = TOLERANCE
) -> int:
    """How many detected boundaries pair one to one with labelled ones at most `tolerance` bars
    away, as many as any such pairing allows. Going through both in order and pairing the first
    two that fit gives that many, since a boundary paired early never takes a partner a later
    one would need."""
    found, wanted = sorted(detected), sorted(labelled)
    matches = mine = theirs = 0
    while mine < len(found) and theirs < len(wanted):
        if abs(found[mine] - wanted[theirs]) <= tolerance:
            matches += 1
            mine += 1
            theirs += 1
        elif found[mine] < wanted[theirs]:
            mine += 1
        else:
            theirs += 1
    return matches


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundaryScore:
    """One track's detected boundaries against its labelled ones."""

    matches: int
    detected: int
    labelled: int

    @property
    def precision(self) -> float:
        return self.matches / self.detected if self.detected else 0.0

    @property
    def recall(self) -> float:
        return self.matches / self.labelled if self.labelled else 0.0

    @property
    def f1(self) -> float:
        total = self.detected + self.labelled
        return 2 * self.matches / total if total else 0.0


def score_starts(detected: Sequence[int], labelled: Sequence[int]) -> BoundaryScore:
    """Detected section starts scored against labelled ones, leaving bar 0 out of both."""
    found = sorted({start for start in detected if start != 0})
    wanted = sorted({start for start in labelled if start != 0})
    return BoundaryScore(
        matches=match_boundaries(found, wanted), detected=len(found), labelled=len(wanted)
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Totals:
    """The scores of several tracks together."""

    tracks: int
    mean_f1: float
    """The headline: the mean of the tracks' F1."""
    pooled_f1: float
    untuned: int
    """How many tracks are not marked as tuned."""
    untuned_mean_f1: float | None
    """The mean F1 of the tracks not marked as tuned, or None when every track is."""

    @property
    def exit_met(self) -> bool:
        """Whether there are enough tracks, and their mean F1 is high enough."""
        return self.tracks >= EXIT_TRACKS and self.mean_f1 >= EXIT_F1


def totals(scores: Sequence[BoundaryScore], tuned: Sequence[bool]) -> Totals:
    """The scores of tracks together, each with whether it is marked as tuned. Raises
    `ValueError` for no tracks."""
    if not scores:
        raise ValueError("there are no tracks to score")
    if len(tuned) != len(scores):
        raise ValueError("each track needs to say whether it is tuned")
    pooled = sum(score.detected + score.labelled for score in scores)
    untuned = [score.f1 for score, marked in zip(scores, tuned, strict=True) if not marked]
    return Totals(
        tracks=len(scores),
        mean_f1=sum(score.f1 for score in scores) / len(scores),
        pooled_f1=2 * sum(score.matches for score in scores) / pooled if pooled else 0.0,
        untuned=len(untuned),
        untuned_mean_f1=sum(untuned) / len(untuned) if untuned else None,
    )
