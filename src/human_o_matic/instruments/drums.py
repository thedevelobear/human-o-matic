"""Drums: each note's role, found from canonical families and the score alone (ADR 0047).

Roles never look at a pitch or a library, only at families, names, ticks and hit types, so every
library is read the same way (ADR 0008). Lengths are in quarter notes, which is what the plan's
Appendix A calls beats. Graces take their main note's part. In turn:
- **Fills** are runs of snare and tom hits at most `FILL_GAP` apart, of at least `FILL_NOTES`,
  with a tom or a gap of at most `FILL_TIGHT_GAP`, whose last hit is less than `FILL_BARS` bars
  after its first: a run that fills two bars is a fill, and a snare roll or tom groove that goes
  on into a third is not. Each note has its metric level, a hand by turns, and
  how far it is into the crescendo over the fill's last `CRESCENDO_QUARTERS` at most.
- **Double kick** is a run of at least `DOUBLE_KICK_NOTES` kick hits at most `DOUBLE_KICK_GAP`
  apart. Feet alternate from the right, unless a name says `left` or `right`.
- **Snare backbeats** are snare hits not typed soft and in no fill, on the start of a beat of
  the time signature other than the bar's first. Other snare hits are `snare`.
- **Accent cymbals** are crash, china, splash and stack hits that are alone, or first of a run
  and on the start of a beat. A run is hits on one cymbal at most `RUN_GAP` apart.
- **Riders** are hat hits other than the pedal, ride hits, and the other crash-family hits. In a
  run of a rider's hits at most `RUN_GAP` apart, the hits on a quarter note alternate strong and
  weak, and the rest are weak. The strong ones are those whose quarter note in the bar has the
  parity on which more of the run's quarter-note hits land with a snare hit, even on a tie. A
  rider hit alone is at its center.
- Everything else, toms outside fills, the hat pedal, percussion and sample layers, is `other`.
"""

from collections.abc import Sequence
from itertools import pairwise

from human_o_matic.normalize.score import Score, ScoreNote
from human_o_matic.render.parts import Limb, Part, RiderShape, Role

FILL_FAMILIES = frozenset({"snare", "tom"})
FILL_GAP = 0.5
FILL_TIGHT_GAP = 0.26
FILL_NOTES = 3
FILL_BARS = 2
CRESCENDO_QUARTERS = 4.0
DOUBLE_KICK_GAP = 0.25
DOUBLE_KICK_NOTES = 4
CRASH_FAMILIES = frozenset({"crash", "china", "splash", "stack"})
RIDER_FAMILIES = frozenset({"hat", "ride"})
RUN_GAP = 2.0
"""The longest gap within a run of one cymbal's hits: a half note."""

type Drum = tuple[str, int]


def drum_parts(score: Score) -> tuple[Part, ...]:
    """The part of each of the score's notes, in the order of `Score.notes`."""
    notes = score.notes
    mains = [position for position, note in enumerate(notes) if note.grace_of is None]
    fills = _fills(score, mains)
    feet = _double_kick(score, mains)
    accents = _accent_cymbals(score, mains)
    riders = _riders(score, mains, accents)
    parts: dict[int, Part] = {}
    """Each main note's part, by its source index."""
    for position in mains:
        note = notes[position]
        role: Role
        if position in fills:
            role = "fill"
        elif note.family == "kick":
            role = "double_kick" if position in feet else "kick"
        elif note.family == "snare":
            role = "backbeat" if _backbeat(score, note) else "snare"
        elif position in accents:
            role = "accent_cymbal"
        elif position in riders:
            role = "rider"
        else:
            role = "other"
        limb: Limb = "snare" if note.family == "snare" else "rider" if role == "rider" else "other"
        metric, hand, crescendo = fills.get(position, (0, 0, 0.0))
        shape, strong = riders.get(position, ("center", False))
        parts[note.source_index] = Part(
            role=role,
            limb=limb,
            rider=shape,
            strong=strong,
            foot=feet.get(position, 0),
            metric=metric,
            hand=hand,
            crescendo=crescendo,
        )
    return tuple(
        parts[note.source_index if note.grace_of is None else note.grace_of] for note in notes
    )


def _runs(score: Score, positions: Sequence[int], gap: float) -> list[list[int]]:
    """The positions split into runs wherever two in a row are more than `gap` quarters apart."""
    limit = gap * score.ppq
    runs: list[list[int]] = []
    for position in positions:
        if runs and score.notes[position].tick - score.notes[runs[-1][-1]].tick <= limit:
            runs[-1].append(position)
        else:
            runs.append([position])
    return runs


def _by_drum(score: Score, positions: Sequence[int]) -> dict[Drum, list[int]]:
    drums: dict[Drum, list[int]] = {}
    for position in positions:
        note = score.notes[position]
        drums.setdefault((note.family, note.piece), []).append(position)
    return drums


def _bar_offset(score: Score, tick: int) -> int:
    """How far the tick is into its bar."""
    return tick - score.signatures.bar_start(score.signatures.bar_at(tick))


def _metric_level(score: Score, tick: int) -> int:
    """0 on a quarter note, 1 on an 8th, 2 on a 16th, and 3 elsewhere, counted from the bar."""
    offset = _bar_offset(score, tick)
    for level, per_quarter in enumerate((1, 2, 4)):
        if offset * per_quarter % score.ppq == 0:
            return level
    return 3


def _on_beat(score: Score, note: ScoreNote) -> bool:
    """Whether the note starts a beat of the time signature."""
    return note.tick == score.beats[note.beat].start


def _backbeat(score: Score, note: ScoreNote) -> bool:
    return note.hit_type != "soft" and _on_beat(score, note) and score.beats[note.beat].beat != 0


def _fills(score: Score, mains: Sequence[int]) -> dict[int, tuple[int, int, float]]:
    """Each fill note's metric level, hand and place in the crescendo, by position."""
    notes = score.notes
    candidates = [position for position in mains if notes[position].family in FILL_FAMILIES]
    found: dict[int, tuple[int, int, float]] = {}
    for run in _runs(score, candidates, FILL_GAP):
        ticks = [notes[position].tick for position in run]
        tight = any(
            later - earlier <= FILL_TIGHT_GAP * score.ppq for earlier, later in pairwise(ticks)
        )
        has_tom = any(notes[position].family == "tom" for position in run)
        if len(run) < FILL_NOTES or not (has_tom or tight):
            continue
        first, last = ticks[0], ticks[-1]
        bar = score.signatures.bar_at(first)
        bar_length = score.signatures.bar_start(bar + 1) - score.signatures.bar_start(bar)
        if last - first >= FILL_BARS * bar_length:
            continue
        rise = max(first, last - round(CRESCENDO_QUARTERS * score.ppq))
        for number, (position, tick) in enumerate(zip(run, ticks, strict=True)):
            into = (tick - rise) / (last - rise) if last > rise and tick >= rise else 0.0
            found[position] = (_metric_level(score, tick), 1 if number % 2 == 0 else -1, into)
    return found


def _double_kick(score: Score, mains: Sequence[int]) -> dict[int, int]:
    """Each double kick note's foot, by position."""
    kicks = [position for position in mains if score.notes[position].family == "kick"]
    feet: dict[int, int] = {}
    for run in _runs(score, kicks, DOUBLE_KICK_GAP):
        if len(run) < DOUBLE_KICK_NOTES:
            continue
        for number, position in enumerate(run):
            words = score.notes[position].articulation.split("|")[0].split(".")
            if "left" in words:
                feet[position] = -1
            elif "right" in words:
                feet[position] = 1
            else:
                feet[position] = 1 if number % 2 == 0 else -1
    return feet


def _accent_cymbals(score: Score, mains: Sequence[int]) -> set[int]:
    crashes = [position for position in mains if score.notes[position].family in CRASH_FAMILIES]
    accents: set[int] = set()
    for positions in _by_drum(score, crashes).values():
        for run in _runs(score, positions, RUN_GAP):
            if len(run) == 1 or _on_beat(score, score.notes[run[0]]):
                accents.add(run[0])
    return accents


def _is_pedal(note: ScoreNote) -> bool:
    return "pedal" in note.articulation.split("|")[0].split(".")


def _riders(
    score: Score, mains: Sequence[int], accents: set[int]
) -> dict[int, tuple[RiderShape, bool]]:
    """Each rider hit's shape, and for an alternating one whether it is where the strong hits
    are, by position."""
    notes = score.notes
    candidates = [
        position
        for position in mains
        if (notes[position].family in RIDER_FAMILIES and not _is_pedal(notes[position]))
        or (notes[position].family in CRASH_FAMILIES and position not in accents)
    ]
    snare = {notes[position].tick for position in mains if notes[position].family == "snare"}
    found: dict[int, tuple[RiderShape, bool]] = {}
    for positions in _by_drum(score, candidates).values():
        for run in _runs(score, positions, RUN_GAP):
            if len(run) == 1:
                found[run[0]] = ("center", False)
                continue
            quarters: dict[int, int] = {}
            """Each quarter-note hit's quarter note in its bar, by position."""
            for position in run:
                offset = _bar_offset(score, notes[position].tick)
                if offset % score.ppq == 0:
                    quarters[position] = offset // score.ppq
            votes = [0, 0]
            for position, quarter in quarters.items():
                if notes[position].tick in snare:
                    votes[quarter % 2] += 1
            strong = 1 if votes[1] > votes[0] else 0
            for position in run:
                if position in quarters:
                    found[position] = ("alternate", quarters[position] % 2 == strong)
                else:
                    found[position] = ("weak", False)
    return found
