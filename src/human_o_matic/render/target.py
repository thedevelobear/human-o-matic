"""Where each note of the score is written: a pitch, a channel and a velocity range in the target
kit (ADR 0048).

In the kit the score was read with, a note keeps its pitch and channel, and its velocities stay
within the range of the bindings that read it. In another kit, its articulation is placed by
conversion's fallback order (`maps.convert.place`), and it is written with the target's binding:
its note, its channel or else the kit's or else the note's own, and its velocity range. What the
fallback order can't settle is a `conversion` request, as converting asks it (ADR 0021), and the
answers are `substitutions`, from a source articulation to an articulation of the target or
`drop`, which leaves its notes out.

A note a controller value decides or shapes keeps the controllers it depends on, for the guard
that holds its controller value (ADR 0053). Writing a controller value to another kit waits for
a map that gives the controller and its values, so such a note is always a request there.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.convert import DROP, Reason, Resolution, checked, conversion_request, place
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.schema import Binding
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.normalize.score import Score, ScoreNote

type Controllers = frozenset[int] | Literal["all"]
"""The controllers whose value a note keeps: those its bindings name, or all of them on its
channel when one names none."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Placed:
    """How one score note is written."""

    articulation: str
    """Its articulation in the target kit, or its own when the kit is the same."""
    family: str
    piece: int
    pitch: int
    channel: int
    """0 to 15."""
    velocity: tuple[int, int]
    """The velocities it may take."""
    controllers: Controllers | None
    """What a controller-bound note depends on, and None for any other."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Placement:
    """Where the score's notes are written, and what is asked about the rest."""

    kit: str
    """The target kit, as `library/kit`."""
    notes: tuple[Placed | None, ...]
    """For each of the score's notes, how it is written, or None when it is left out by a
    substitution or waits for a request."""
    dropped: tuple[int, ...]
    """The positions in `Score.notes` that a substitution leaves out."""
    decisions: tuple[DecisionRequest, ...]

    @property
    def complete(self) -> bool:
        return not self.decisions


def controllers(bindings: Iterable[Binding]) -> Controllers | None:
    """The controllers notes read through these bindings depend on, or None for none."""
    numbers: set[int] = set()
    for binding in bindings:
        if binding.cc is None:
            continue
        if binding.cc.controller is None:
            return "all"
        numbers.add(binding.cc.controller)
    return frozenset(numbers) if numbers else None


def place_score(
    score: Score,
    source: DrumKit,
    target: DrumKit,
    substitutions: Mapping[str, str] | None = None,
) -> Placement:
    """Place each of the score's notes, read with `source`, in `target`.

    Raises `ValueError` for a substitution the target kit can't play, and `AnswerError` for one
    whose source articulation the score doesn't have.
    """
    picks = checked(substitutions or {}, target)
    keys = {note.articulation for note in score.notes}
    stray = sorted(picks.keys() - keys)
    if stray:
        raise AnswerError(
            "substitutions", stray[0], f"{stray[0]}: the drums have no notes read as it"
        )
    same_kit = source.ref == target.ref
    resolutions: dict[str, Resolution] = {}
    waiting: dict[tuple[Reason, str], list[ScoreNote]] = {}
    placed: list[Placed | None] = []
    dropped: list[int] = []
    for position, note in enumerate(score.notes):
        key = note.articulation
        if same_kit and key not in picks:
            placed.append(_kept(note, source))
            continue
        first = source.articulation(key.split("|")[0])
        controlled = "|" in key or controllers(first.bindings) is not None
        resolution = place(key, controlled, source, target, picks, resolutions)
        if resolution.target is None:
            waiting.setdefault((resolution.reason or "family", key), []).append(note)
            placed.append(None)
        elif resolution.target == DROP:
            dropped.append(position)
            placed.append(None)
        else:
            placed.append(_written(note, resolution.target, target))
    decisions = tuple(
        conversion_request(
            reason,
            key,
            [note.source for note in held],
            resolutions.get(key, Resolution(None)),
            source,
            target,
            score.signatures,
        )
        for (reason, key), held in waiting.items()
    )
    return Placement(
        kit=target.ref, notes=tuple(placed), dropped=tuple(dropped), decisions=decisions
    )


def _kept(note: ScoreNote, kit: DrumKit) -> Placed:
    """A note written to the kit it was read with: its pitch and channel, and the velocities of
    the bindings that read it."""
    source = note.source
    matches = kit.read(source.pitch, source.velocity, source.channel)
    if matches:
        low = max(match.binding.velocity[0] for match in matches)
        high = min(match.binding.velocity[1] for match in matches)
        # Bindings that share a note are told apart by `select` ranges, so several matches name
        # their controller.
        depends = controllers(match.binding for match in matches)
    else:
        # A note the kit doesn't map, read as the articulation an `unmapped` answer gave it.
        low, high = kit.write(note.articulation).velocity
        depends = controllers(kit.articulation(note.articulation).bindings)
    return Placed(
        articulation=note.articulation,
        family=note.family,
        piece=note.piece,
        pitch=source.pitch,
        channel=source.channel,
        velocity=(low, high),
        controllers=depends,
    )


def _written(note: ScoreNote, name: str, kit: DrumKit) -> Placed:
    output = kit.write(name)
    canonical = kit.canonical(name)
    return Placed(
        articulation=name,
        family=canonical.family,
        piece=canonical.piece,
        pitch=output.pitch,
        channel=output.channel if output.channel is not None else note.source.channel,
        velocity=output.velocity,
        controllers=None,
    )
