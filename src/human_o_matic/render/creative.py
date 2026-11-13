"""Creative mode: the notes a section adds, kept from changing any other section (ADRs 0091 to
0095).

A section whose controls set `creative`, and not `skip`, asks its instrument what it would add
(`Instrument.additions`): candidates, each a note on a grid point with its part and how it is
written, or one of the section's notes written as another articulation, and the notes it can't
add because the target kit lacks their articulation or the section plays nothing to add them on.
`admit` keeps a candidate only where it changes no other section, and counts the rest:
- no note of its drum, or of its pitch, is on its grid point, in the score or added before it;
  otherwise it is `crowded`;
- its section plays its pitch and its drum, so a class it takes next to another section comes
  from its own section's note there (`render/guards.py`), and a note written as another
  articulation has its section's notes before and after it on both pitches; otherwise it is
  `unplayed`;
- when the note before or after it on its pitch is another section's, the latest and earliest
  that note can be played, and the earliest anything that section adds can be, leave it the gap
  the guards keep, within the cap, wherever it is drawn; otherwise it is `crowded`.
The target kit lacking an articulation is `missing`, which the instrument counts. Nothing is ever
asked about, and no addition changes a hit's family.
"""

import bisect
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from human_o_matic.midi.tempo import TempoMap
from human_o_matic.normalize.hit_types import HitType
from human_o_matic.normalize.score import Score
from human_o_matic.render.guards import MAX_OFFSET_MS, MIN_GAP_SHARE
from human_o_matic.render.parts import Part
from human_o_matic.render.target import Placed, Placement

type Addition = Literal["ghost", "cymbal", "fill", "flam", "rimshot", "choke"]
"""What a creative section adds: soft notes on the snare, crashes and rider hits where it has
few cymbals, a fill into the next section, a flam's grace, and a choke after a cymbal. A rimshot
is one of its own snare notes written as the kit's rimshot."""
ADDITIONS: tuple[Addition, ...] = ("ghost", "cymbal", "fill", "flam", "rimshot", "choke")
type Skip = Literal["missing", "unplayed", "crowded"]
"""Why a note wasn't added: the target kit lacks its articulation, the section doesn't play its
pitch or drum, or another note leaves it no room."""
SKIPS: tuple[Skip, ...] = ("missing", "unplayed", "crowded")
SLACK = 2
"""Ticks the worst cases allow for going to a tick, either way."""

type Key = tuple[int, int]
"""A channel and a pitch."""
type Drum = tuple[str, int]


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidate:
    """A note a creative section would add, or one of its notes written as another
    articulation."""

    kind: Addition
    tick: int
    """Its grid point, or for a flam's grace, its place before its main."""
    placed: Placed
    hit_type: HitType
    part: Part
    length: int
    """In ticks."""
    grace_of: int | None = None
    """For a flam's grace, the `source_index` of its main, as a grace of the score has."""
    replaces: int | None = None
    """For a note written as another articulation, its position in `Score.notes`."""

    @property
    def key(self) -> Key:
        return self.placed.channel, self.placed.pitch

    @property
    def drum(self) -> Drum:
        return self.placed.family, self.placed.piece


@dataclass(frozen=True, slots=True, kw_only=True)
class Proposal:
    """What an instrument would add to a section, in the order it is admitted, and what it can't
    add at all."""

    candidates: tuple[Candidate, ...] = ()
    skipped: Mapping[Skip, Mapping[Addition, int]] = field(
        default_factory=dict[Skip, Mapping[Addition, int]]
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionView:
    """What an instrument reads to propose a section's additions: the section's own notes and
    bars, how the score's notes are placed, and whether another section with notes follows."""

    score: Score
    parts: tuple[Part, ...]
    """Each of the score's notes' parts, found on the score alone."""
    placement: Placement
    members: tuple[int, ...]
    """The positions in `Score.notes` of the section's notes, in play order, without those left
    out."""
    start: int
    """Its first bar."""
    end: int
    """The bar after its last."""
    leads_on: bool
    """Whether the next section has notes, so a fill leads somewhere."""

    @property
    def first_tick(self) -> int:
        return self.score.signatures.bar_start(self.start)

    @property
    def end_tick(self) -> int:
        return self.score.signatures.bar_start(self.end)


class CreativeReport(BaseModel):
    """What a creative section added, by kind, and what it couldn't, by why and kind. A rimshot
    is a note of the section written as one, not a note added."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    added: dict[Addition, int] = Field(default_factory=dict[Addition, int])
    skipped: dict[Skip, dict[Addition, int]] = Field(
        default_factory=dict[Skip, dict[Addition, int]]
    )

    @property
    def notes(self) -> int:
        """The notes added, without the notes written as rimshots."""
        return sum(count for kind, count in self.added.items() if kind != "rimshot")

    @classmethod
    def summed(cls, reports: Sequence["CreativeReport | None"]) -> "CreativeReport | None":
        """The reports of the creative sections added together, or None when none is creative."""
        given = [report for report in reports if report is not None]
        if not given:
            return None
        added: Counter[Addition] = Counter()
        skipped: dict[Skip, Counter[Addition]] = {}
        for report in given:
            added.update(report.added)
            for reason, kinds in report.skipped.items():
                skipped.setdefault(reason, Counter()).update(kinds)
        return cls(
            added={kind: added[kind] for kind in ADDITIONS if added[kind]},
            skipped={
                reason: {kind: skipped[reason][kind] for kind in ADDITIONS if skipped[reason][kind]}
                for reason in SKIPS
                if reason in skipped
            },
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Neighbours:
    """The score's notes as placed in the target kit, in play order by pitch, with what the
    worst cases around an added note need: each note's section, whether it is played as it came
    in, and its controller window."""

    score: Score
    placement: Placement
    section_of: Sequence[int]
    kept: Sequence[bool]
    windows: Sequence[tuple[int, int] | None]
    starts: Sequence[int]
    """Each section's first tick."""
    by_key: Mapping[Key, Sequence[int]]
    """The positions on each pitch, in play order."""
    taken: frozenset[tuple[Drum | Key, int]]
    """Each drum and each pitch with a note on a tick."""
    played: Mapping[int, frozenset[Drum | Key]]
    """The drums and pitches each section has notes on."""

    @classmethod
    def build(
        cls,
        score: Score,
        placement: Placement,
        order: Sequence[int],
        section_of: Sequence[int],
        kept: Sequence[bool],
        windows: Sequence[tuple[int, int] | None],
        starts: Sequence[int],
    ) -> "Neighbours":
        by_key: dict[Key, list[int]] = {}
        taken: set[tuple[Drum | Key, int]] = set()
        played: dict[int, set[Drum | Key]] = {}
        for position in order:
            placed = placement.notes[position]
            if placed is None:
                continue
            tick = score.notes[position].tick
            key, drum = (placed.channel, placed.pitch), (placed.family, placed.piece)
            by_key.setdefault(key, []).append(position)
            taken.update(((drum, tick), (key, tick)))
            played.setdefault(section_of[position], set()).update((key, drum))
        return cls(
            score=score,
            placement=placement,
            section_of=section_of,
            kept=kept,
            windows=windows,
            starts=starts,
            by_key=by_key,
            taken=frozenset(taken),
            played={number: frozenset(found) for number, found in played.items()},
        )

    def plays(self, number: int, key: Key, drum: Drum) -> bool:
        """Whether section `number` has a note on the pitch and one on the drum."""
        own = self.played.get(number, frozenset())
        return key in own and drum in own

    def around(
        self, key: Key, tick: int, *, but: int | None = None
    ) -> tuple[int | None, int | None]:
        """The positions of the last note on the pitch before the tick and the first after it,
        leaving out `but`."""
        positions = [p for p in self.by_key.get(key, ()) if p != but]
        ticks = [self.score.notes[p].tick for p in positions]
        low = bisect.bisect_left(ticks, tick)
        high = bisect.bisect_right(ticks, tick)
        before = positions[low - 1] if low > 0 else None
        after = positions[high] if high < len(positions) else None
        return before, after

    def _ms(self, tick: int) -> float:
        return self.score.tempos.tick_to_ms(tick)

    def latest_start(self, position: int) -> int:
        note = self.score.notes[position]
        window = self.windows[position]
        if self.kept[position]:
            return note.source.start
        latest = _shifted(self.score.tempos, note.tick, MAX_OFFSET_MS) + SLACK
        return max(latest, window[1]) if window is not None else latest

    def latest_end(self, position: int) -> int:
        source = self.score.notes[position].source
        if self.kept[position]:
            return source.end
        return self.latest_start(position) + max(source.end - source.start, 1)

    def earliest_start(self, position: int) -> int:
        note = self.score.notes[position]
        window = self.windows[position]
        if self.kept[position]:
            return note.source.start
        earliest = max(_shifted(self.score.tempos, note.tick, -MAX_OFFSET_MS) - SLACK, 0)
        return min(earliest, window[0]) if window is not None else earliest


def _shifted(tempos: TempoMap, tick: int, ms: float) -> int:
    """The tick nearest `ms` milliseconds from `tick`."""
    return round(tempos.ms_to_tick(tempos.tick_to_ms(tick) + ms))


@dataclass(frozen=True, slots=True, kw_only=True)
class Admitted:
    """A section's additions as admitted, and its report."""

    added: tuple[tuple[Candidate, int | None], ...]
    """Each note added, with the latest tick it may end on, when the next note of its pitch is in
    another section."""
    rewritten: Mapping[int, Candidate]
    """The notes written as another articulation, by their position in `Score.notes`."""
    report: CreativeReport


def admit(number: int, proposal: Proposal, around: Neighbours) -> Admitted:
    """The candidates of section `number` that change no other section, and the report."""
    tempos = around.score.tempos
    taken = set(around.taken)
    added: list[tuple[Candidate, int | None]] = []
    rewritten: dict[int, Candidate] = {}
    counts: dict[Addition, int] = {}
    skipped: dict[Skip, dict[Addition, int]] = {
        reason: dict(kinds) for reason, kinds in proposal.skipped.items()
    }

    def skip(reason: Skip, kind: Addition) -> None:
        kinds = skipped.setdefault(reason, {})
        kinds[kind] = kinds.get(kind, 0) + 1

    for candidate in proposal.candidates:
        tick = candidate.tick
        if (candidate.key, tick) in taken or (
            candidate.replaces is None and (candidate.drum, tick) in taken
        ):
            skip("crowded", candidate.kind)
            continue
        if candidate.replaces is not None:
            if not _between_own(around, number, candidate):
                skip("unplayed", candidate.kind)
                continue
            rewritten[candidate.replaces] = candidate
        else:
            if not around.plays(number, candidate.key, candidate.drum):
                skip("unplayed", candidate.kind)
                continue
            room, end_by = _room(around, number, candidate, tempos)
            if not room:
                skip("crowded", candidate.kind)
                continue
            added.append((candidate, end_by))
            taken.add((candidate.drum, tick))
        taken.add((candidate.key, tick))
        counts[candidate.kind] = counts.get(candidate.kind, 0) + 1
    report = CreativeReport(
        added={kind: counts[kind] for kind in ADDITIONS if counts.get(kind)},
        skipped={
            reason: {kind: skipped[reason][kind] for kind in ADDITIONS if skipped[reason].get(kind)}
            for reason in SKIPS
            if reason in skipped and any(skipped[reason].values())
        },
    )
    return Admitted(added=tuple(added), rewritten=rewritten, report=report)


def _between_own(around: Neighbours, number: int, candidate: Candidate) -> bool:
    """Whether a note written as another articulation has its section's notes before and after
    it on the pitch it was placed on and on the one it is written on, so it is next to no other
    section on either."""
    position = candidate.replaces
    assert position is not None
    placed = around.placement.notes[position]
    if placed is None:
        return False
    for key in ((placed.channel, placed.pitch), candidate.key):
        before, after = around.around(key, candidate.tick, but=position)
        if before is None or after is None:
            return False
        if around.section_of[before] != number or around.section_of[after] != number:
            return False
    return True


def _room(
    around: Neighbours, number: int, candidate: Candidate, tempos: TempoMap
) -> tuple[bool, int | None]:
    """Whether an added note keeps its gap, within the cap, from the notes of other sections next
    to it on its pitch, however they and it are drawn, and the latest tick it may end on when the
    note after it is another section's."""
    tick = candidate.tick
    ms = tempos.tick_to_ms
    earliest = max(_shifted(tempos, tick, -MAX_OFFSET_MS) - SLACK, 0)
    latest = _shifted(tempos, tick, MAX_OFFSET_MS) + SLACK
    before, after = around.around(candidate.key, tick)
    if before is not None and around.section_of[before] != number:
        grid = ms(tick) - ms(around.score.notes[before].tick)
        if earliest < around.latest_end(before):
            return False, None
        if ms(earliest) - ms(around.latest_start(before)) < MIN_GAP_SHARE * grid:
            return False, None
    end_by: int | None = None
    if after is not None and around.section_of[after] != number:
        grid = ms(around.score.notes[after].tick) - ms(tick)
        first = around.earliest_start(after)
        if ms(first) - ms(latest) < MIN_GAP_SHARE * grid or first <= latest:
            return False, None
        end_by = first
        if not around.kept[after]:
            # That section may add a note from its first tick, as early as the cap allows.
            edge = around.starts[around.section_of[after]]
            soonest = max(_shifted(tempos, edge, -MAX_OFFSET_MS) - SLACK, 0)
            if ms(soonest) - ms(latest) < MIN_GAP_SHARE * (ms(edge) - ms(tick)):
                return False, None
            if soonest <= latest:
                return False, None
            end_by = min(end_by, soonest)
    return True, end_by
