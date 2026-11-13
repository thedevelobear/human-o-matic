"""What a creative drum section adds (ADR 0092), read from canonical families, the drums' parts,
ticks and grids, and the hit types, never from a pitch, a library (ADR 0008), a velocity or a
note's timing.

Each addition copies how one of the section's notes is written, so it lands on a pitch and a drum
the section plays, apart from a rimshot and a choke, which the target kit writes by their
canonical names. Each takes its part, so the style and the compiler give it its velocity and
timing as they give the section's own notes of that role. In the order they are admitted
(`render/creative.py`):
- **Fill**: when the section's last bar has notes and none of them is a fill, and the next
  section has notes, a run of 16ths over that bar's last `FILL_QUARTERS` quarter notes, or the
  whole bar when it is shorter, on the section's snare and the toms it plays, from the snare down
  the toms in even shares. Each is a fill note with its metric level, a hand by turns and its
  place in the crescendo, as a fill of the score has (ADR 0047).
- **Cymbals**, when the section has fewer cymbal hits than beats: a crash on the first tick of
  every `PHRASE` bars from its start, on the crash-family cymbal it plays most, where no
  crash-family cymbal or ride hits; and its most played rider on each beat between that rider's
  first and last hits where no cymbal hits.
- **Ghost notes**: soft hits on its most played snare articulation, on the 16ths between the
  8ths that the section's stream picks once for every bar, each with the chance `GHOST_CHANCE`,
  between the section's first and last notes on that snare, and before the fill.
- **Flams**: a soft grace `FLAM_MS` before the last backbeat of every `PHRASE`th bar, on the
  backbeat's own articulation, when the note before it on its pitch is the section's and an 8th
  or more before it, and the backbeat has no grace.
- **Rimshots**: the first backbeat of every `PHRASE` bars from its start, written as the kit's
  rimshot of its snare.
- **Chokes**: the kit's choke of the section's last crash-family accent, an 8th after it, when no
  hit of that cymbal follows within a quarter note and the section goes on that long.
No 16th is added in a beat whose grid is a triplet. A rimshot or a choke the target kit has no
articulation for, or only one a controller value decides, is `missing`; a fill with neither a
snare nor a tom, and a crash with no crash-family cymbal, are `unplayed`, and an addition on a
tick where its drum or its pitch already has a note, of the score or added before it, is
`played`. A section with no notes adds nothing.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from math import ceil

import numpy as np

from human_o_matic.instruments.drums import CRASH_FAMILIES, is_pedal, metric_level
from human_o_matic.normalize.hit_types import HitType
from human_o_matic.normalize.score import Score, ScoreNote
from human_o_matic.render.creative import Addition, Candidate, Proposal, SectionView, Skip
from human_o_matic.render.parts import Part
from human_o_matic.render.target import Placed, written

PHRASE = 4
"""The bars of a phrase, from the section's start: where crashes, flams and rimshots go."""
FILL_QUARTERS = 2
"""How many quarter notes a fill takes at the end of the section's last bar."""
GHOST_CHANCE = 0.3
"""The chance each 16th between 8ths is in the section's ghost notes."""
GHOST_SLOTS = 64
"""The 16ths of a bar the ghost notes' pattern covers: a bar of 16 quarter notes."""
FLAM_MS = 25.0
"""A flam's grace before its main, within the gap of ADR 0027."""
CYMBAL_FAMILIES = CRASH_FAMILIES | {"ride", "hat"}
"""The families whose hits count as cymbals, the hat pedal aside."""
TRIPLETS = frozenset({"8th_triplet", "16th_triplet"})


def propose(view: SectionView, rng: np.random.Generator) -> Proposal:
    """What a creative section of drums adds, in the order it is admitted. A section with no
    notes adds nothing."""
    pattern = [bool(chosen) for chosen in rng.random(GHOST_SLOTS) < GHOST_CHANCE]
    if not view.members:
        return Proposal()
    found: list[Candidate] = []
    skipped: dict[Skip, dict[Addition, int]] = {}

    def skip(reason: Skip, kind: Addition, count: int = 1) -> None:
        kinds = skipped.setdefault(reason, {})
        kinds[kind] = kinds.get(kind, 0) + count

    fill = _fill(view, skip)
    found += fill
    if _sparse(view):
        found += _crashes(view, skip)
        found += _riders(view)
    found += _ghosts(view, pattern, fill[0].tick if fill else view.end_tick)
    found += _flams(view)
    found += _rimshots(view, skip)
    found += _chokes(view, skip)
    return Proposal(candidates=_unstacked(view, found, skip), skipped=skipped)


def _unstacked(
    view: SectionView, found: Sequence[Candidate], skip: Callable[[Skip, Addition, int], None]
) -> tuple[Candidate, ...]:
    """The candidates, but an added note on a tick where its drum or its pitch already has a
    note, of the score or added before it, which is counted as `played`."""
    taken: set[tuple[object, int]] = set()
    for placed, note in zip(view.placement.notes, view.score.notes, strict=True):
        if placed is not None:
            taken.update((((placed.family, placed.piece), note.tick), (_key(placed), note.tick)))
    kept: list[Candidate] = []
    for candidate in found:
        places = ((candidate.drum, candidate.tick), (candidate.key, candidate.tick))
        if candidate.replaces is None and any(place in taken for place in places):
            skip("played", candidate.kind, 1)
            continue
        taken.update(places)
        kept.append(candidate)
    return tuple(kept)


def _key(placed: Placed) -> tuple[int, int]:
    return placed.channel, placed.pitch


type Anchor = tuple[Placed, int]
"""How a note of the section is written, and its length."""


def _mains(view: SectionView) -> list[int]:
    return [p for p in view.members if view.score.notes[p].grace_of is None]


def _anchor(view: SectionView, pick: Callable[[ScoreNote, Part, Placed], bool]) -> Anchor | None:
    """How the section's most played notes that `pick` takes are written, the first on a tie,
    leaving out graces, soft notes and notes a controller value decides."""
    counts: Counter[Placed] = Counter()
    lengths: dict[Placed, int] = {}
    for position in _mains(view):
        note = view.score.notes[position]
        placed = view.placement.notes[position]
        if placed is None or placed.controllers is not None or note.hit_type == "soft":
            continue
        if pick(note, view.parts[position], placed):
            counts[placed] += 1
            lengths.setdefault(placed, max(note.source.end - note.source.start, 1))
    if not counts:
        return None
    placed = counts.most_common(1)[0][0]
    return placed, lengths[placed]


def _sixteenths(score: Score, start: int, end: int) -> list[int]:
    """The 16ths from `start` to before `end`, but those in a beat whose grid is a triplet."""
    count = ceil((end - start) * 4 / score.ppq)
    ticks = [start + round(step * score.ppq / 4) for step in range(count)]
    return [tick for tick in ticks if tick < end and not _triplet(score, tick)]


def _triplet(score: Score, tick: int) -> bool:
    for beat in score.beats:
        if beat.start <= tick < beat.end:
            return beat.grid in TRIPLETS
    return False


def _candidate(
    kind: Addition,
    tick: int,
    anchor: Anchor,
    part: Part,
    hit_type: HitType = "normal",
) -> Candidate:
    placed, length = anchor
    return Candidate(
        kind=kind, tick=tick, placed=placed, hit_type=hit_type, part=part, length=length
    )


def _fill(view: SectionView, skip: Callable[[Skip, Addition, int], None]) -> list[Candidate]:
    score = view.score
    last = view.end - 1
    start, end = score.signatures.bar_start(last), score.signatures.bar_start(last + 1)
    heard = [p for p in _mains(view) if score.signatures.bar_at(score.notes[p].tick) == last]
    if not view.leads_on or not heard or any(view.parts[p].role == "fill" for p in heard):
        return []
    ticks = _sixteenths(score, max(start, end - FILL_QUARTERS * score.ppq), end)
    if not ticks:
        return []
    drums: list[Anchor] = []
    snare = _anchor(view, lambda _, __, placed: placed.family == "snare")
    if snare is not None:
        drums.append(snare)
    toms = {
        placed.piece
        for position in view.members
        if (placed := view.placement.notes[position]) is not None and placed.family == "tom"
    }
    for piece in sorted(toms):
        drum = ("tom", piece)
        tom = _anchor(view, lambda _, __, placed, drum=drum: (placed.family, placed.piece) == drum)
        if tom is not None:
            drums.append(tom)
    if not drums:
        skip("unplayed", "fill", len(ticks))
        return []
    first, final = ticks[0], ticks[-1]
    found: list[Candidate] = []
    for number, tick in enumerate(ticks):
        anchor = drums[number * len(drums) // len(ticks)]
        part = Part(
            role="fill",
            limb="snare" if anchor[0].family == "snare" else "other",
            metric=metric_level(score, tick),
            hand=1 if number % 2 == 0 else -1,
            crescendo=(tick - first) / (final - first) if final > first else 0.0,
        )
        found.append(_candidate("fill", tick, anchor, part))
    return found


def _cymbal(note: ScoreNote) -> bool:
    return note.family in CYMBAL_FAMILIES and not is_pedal(note)


def _sparse(view: SectionView) -> bool:
    """Whether the section has fewer cymbal hits than beats (ADR 0092)."""
    hits = sum(_cymbal(view.score.notes[p]) for p in _mains(view))
    return hits < len(_beats(view))


def _beats(view: SectionView) -> list[int]:
    """The first tick of each beat of the section's bars, by their time signatures."""
    signatures = view.score.signatures
    ticks: list[int] = []
    for bar in range(view.start, view.end):
        start = signatures.bar_start(bar)
        signature = signatures.signature_at(start)
        length = 4 * view.score.ppq / signature.denominator
        ticks += [start + round(beat * length) for beat in range(signature.numerator)]
    return ticks


def _ticks_of(score: Score, families: frozenset[str] | set[str]) -> set[int]:
    """The ticks of the score's notes in those families, the hat pedal aside."""
    return {note.tick for note in score.notes if note.family in families and not is_pedal(note)}


def _crashes(view: SectionView, skip: Callable[[Skip, Addition, int], None]) -> list[Candidate]:
    score = view.score
    crash = _anchor(view, lambda _, __, placed: placed.family in CRASH_FAMILIES)
    struck = _ticks_of(score, CRASH_FAMILIES | {"ride"})
    found: list[Candidate] = []
    for bar in range(view.start, view.end, PHRASE):
        tick = score.signatures.bar_start(bar)
        if tick in struck:
            continue
        if crash is None:
            skip("unplayed", "cymbal", 1)
            continue
        part = Part(role="accent_cymbal", limb="other", metric=0)
        found.append(_candidate("cymbal", tick, crash, part))
    return found


def _riders(view: SectionView) -> list[Candidate]:
    rider = _anchor(view, lambda _, part, __: part.role == "rider")
    if rider is None:
        return []
    placed = rider[0]
    own = [view.score.notes[p].tick for p in _mains(view) if view.placement.notes[p] == placed]
    struck = _ticks_of(view.score, CYMBAL_FAMILIES)
    found: list[Candidate] = []
    for tick in _beats(view):
        if min(own) < tick < max(own) and tick not in struck:
            part = Part(
                role="rider",
                limb="rider",
                rider="weak",
                metric=metric_level(view.score, tick),
            )
            found.append(_candidate("cymbal", tick, rider, part))
    return found


def _ghosts(view: SectionView, pattern: Sequence[bool], before: int) -> list[Candidate]:
    score = view.score
    snare = _anchor(view, lambda _, __, placed: placed.family == "snare")
    if snare is None:
        return []
    own = [score.notes[p].tick for p in view.members if view.placement.notes[p] == snare[0]]
    found: list[Candidate] = []
    for bar in range(view.start, view.end):
        start = score.signatures.bar_start(bar)
        for tick in _sixteenths(score, start, score.signatures.bar_start(bar + 1)):
            step = round((tick - start) * 4 / score.ppq)
            if step % 2 == 0 or step >= len(pattern) or not pattern[step]:
                continue
            if min(own) < tick < max(own) and tick < before:
                part = Part(role="snare", limb="snare", metric=metric_level(score, tick))
                found.append(_candidate("ghost", tick, snare, part, "soft"))
    return found


def _backbeats(view: SectionView, bars: range) -> list[list[int]]:
    """The section's backbeats in each of `bars`, by tick."""
    score = view.score
    found: dict[int, list[int]] = {bar: [] for bar in bars}
    for position in _mains(view):
        bar = score.signatures.bar_at(score.notes[position].tick)
        if bar in found and view.parts[position].role == "backbeat":
            found[bar].append(position)
    return [sorted(found[bar], key=lambda p: score.notes[p].tick) for bar in bars]


def _flams(view: SectionView) -> list[Candidate]:
    score = view.score
    tempos = score.tempos
    found: list[Candidate] = []
    for backbeats in _backbeats(view, range(view.start + PHRASE - 1, view.end, PHRASE)):
        if not backbeats:
            continue
        position = backbeats[-1]
        main = score.notes[position]
        placed = view.placement.notes[position]
        if placed is None or placed.controllers is not None or score.graces(main):
            continue
        key = (placed.channel, placed.pitch)
        before = [
            p
            for p, other in enumerate(view.placement.notes)
            if other is not None
            and (other.channel, other.pitch) == key
            and score.notes[p].tick < main.tick
        ]
        if not before:
            continue
        prior = max(before, key=lambda p: score.notes[p].tick)
        if prior not in view.members or main.tick - score.notes[prior].tick < score.ppq / 2:
            continue
        tick = round(tempos.ms_to_tick(tempos.tick_to_ms(main.tick) - FLAM_MS))
        if not score.notes[prior].tick < tick < main.tick:
            continue
        length = max(main.source.end - main.source.start, 1)
        found.append(
            Candidate(
                kind="flam",
                tick=tick,
                placed=placed,
                hit_type="soft",
                part=view.parts[position],
                length=length,
                grace_of=main.source_index,
            )
        )
    return found


def _rimshots(view: SectionView, skip: Callable[[Skip, Addition, int], None]) -> list[Candidate]:
    score = view.score
    kit = view.placement.target
    found: list[Candidate] = []
    for backbeats in _backbeats(view, range(view.start, view.end, PHRASE)):
        if not backbeats:
            continue
        position = backbeats[0]
        placed = view.placement.notes[position]
        if placed is None or placed.controllers is not None:
            continue
        name = kit.vocabulary.name(placed.family, placed.piece, ("rimshot",)).text
        if name not in kit or kit.write(name).cc is not None:
            skip("missing", "rimshot", 1)
            continue
        if placed.articulation == name:
            continue
        note = score.notes[position]
        found.append(
            Candidate(
                kind="rimshot",
                tick=note.tick,
                placed=written(name, kit, placed.channel),
                hit_type=note.hit_type,
                part=view.parts[position],
                length=max(note.source.end - note.source.start, 1),
                replaces=position,
            )
        )
    return found


def _chokes(view: SectionView, skip: Callable[[Skip, Addition, int], None]) -> list[Candidate]:
    score = view.score
    kit = view.placement.target
    accents = [
        p
        for p in _mains(view)
        if view.parts[p].role == "accent_cymbal" and score.notes[p].family in CRASH_FAMILIES
    ]
    if not accents:
        return []
    position = max(accents, key=lambda p: score.notes[p].tick)
    cymbal = score.notes[position]
    placed = view.placement.notes[position]
    tick = cymbal.tick + score.ppq // 2
    if placed is None or tick >= view.end_tick:
        return []
    drum = (placed.family, placed.piece)
    for other, at in zip(score.notes, view.placement.notes, strict=True):
        if (
            at is not None
            and (at.family, at.piece) == drum
            and cymbal.tick < other.tick <= cymbal.tick + score.ppq
        ):
            return []
    try:
        name = kit.vocabulary.name(placed.family, placed.piece, ("choke",)).text
    except ValueError:
        name = None
    if name is None or name not in kit or kit.write(name).cc is not None:
        skip("missing", "choke", 1)
        return []
    part = Part(role="other", limb="other", metric=metric_level(score, tick))
    choke = written(name, kit, placed.channel)
    return [_candidate("choke", tick, (choke, max(score.ppq // 8, 1)), part)]
