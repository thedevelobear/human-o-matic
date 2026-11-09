"""Sections of a song's drums: the bar where each begins, and which ones repeat each other.

Each bar is described by its onset pattern in each drum family of the score, so the sections
come from canonical families and never from a library's notes (ADR 0008). A family's pattern
marks the slots of the bar where it has a hit, `SLOTS_PER_QUARTER` to a quarter note, which puts
every point of the four grids on a slot of its own. Graces are left out, as ornaments of their
main notes. Two bars are as alike as the cosine of their patterns, each family's pattern scaled
to length 1 first: every family a bar plays counts the same however busy it is, and a family
only one of the two plays makes them less alike. Two empty bars are alike, and an empty bar is
unlike any other.

A boundary is where the bars before it are alike among themselves and unlike the bars after it.
The novelty at bar `b` at a scale of `L` bars is the mean likeness within the `L` bars before
`b` and within the `L` bars from `b`, less the mean likeness across them, and it is averaged
over the `SCALES` that fit in the song on both sides. Its peaks are the candidates, except on an
empty bar, since a short silence ends the section before it.

A stretch of at least `MIN_SILENCE` empty bars is a section of its own. A bar just before it
whose hits all fall in its first half is a stop and starts it, and a bar just after it whose hits
all fall in its second half is a lead-in and ends it.

The boundaries are the candidates that score best together: each is worth its novelty less
`BOUNDARY_COST`, and each section that isn't one of the `PHRASES` long costs `LENGTH_COST`. A
section is at least `MIN_BARS` long, and the silent stretches' boundaries are always kept. An
exact dynamic program finds the best choice.

The sections then fall into repeat groups, in song order. Two sections are as alike as their
bars compared in order, over the shorter one's length. A section joins the group it is most
alike, averaged over the group's sections, when that is at least `REPEAT`, and otherwise starts
a group of its own. Groups are named A, B, C and on, in the order they first appear.

When the file has SMF markers they win: each marker snaps to the nearest bar line, and the
sections start at the markers' bars instead. `find_sections` takes `markers=False` to leave them
out, as the measurement against hand labels does (ADR 0034).

Nothing here is random, so the same song and score always give the same sections.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from human_o_matic.midi.io import MidiSong
from human_o_matic.normalize.score import Score

type FloatArray = npt.NDArray[np.float64]
type BoolArray = npt.NDArray[np.bool_]
type SectionSource = Literal["markers", "drums"]
"""Where the sections came from: the file's markers, or the drums themselves."""

SLOTS_PER_QUARTER = 24
"""Onset slots per quarter note: every point of the 16th, 8th triplet, 16th triplet and 32nd
grids (ADR 0026) is a slot."""
SCALES = (2, 4, 8)
"""The novelty's scales, in bars: half a phrase, a phrase and two."""
PHRASES = (4, 8, 16)
"""Section lengths, in bars, that cost nothing."""
BOUNDARY_COST = 0.2
"""The novelty a boundary needs before it is worth placing."""
LENGTH_COST = 0.2
"""What a section costs when it isn't one of the `PHRASES` long."""
MIN_BARS = 2
"""The shortest section, in bars, but for one the silent stretches make: the smallest scale."""
MIN_SILENCE = 4
"""The shortest stretch of empty bars that is a section of its own: the shortest phrase."""
REPEAT = 0.8
"""How alike a section must be to a group to join it."""
META_MARKER = 0x06
"""The meta event type of an SMF marker."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Section:
    """A run of whole bars."""

    start: int
    """Its first bar, counting from 0."""
    bars: int
    """How many bars it has."""
    group: str
    """Its repeat group: sections in one group play alike."""

    @property
    def end(self) -> int:
        """The bar after its last."""
        return self.start + self.bars


@dataclass(frozen=True, slots=True, kw_only=True)
class Sections:
    """A song's sections, which together cover its bars in order."""

    sections: tuple[Section, ...]
    source: SectionSource

    @property
    def starts(self) -> tuple[int, ...]:
        """The bar where each section begins, from 0."""
        return tuple(section.start for section in self.sections)


@dataclass(frozen=True, slots=True, kw_only=True)
class BarPatterns:
    """What each bar plays."""

    patterns: FloatArray
    """By bar, family and slot: 1 where the family has a hit, then each family's pattern in a bar
    scaled to length 1."""
    families: tuple[str, ...]
    """The families of the second axis."""
    empty: BoolArray
    """The bars without hits."""
    stop: BoolArray
    """The bars whose hits all fall in their first half."""
    lead_in: BoolArray
    """The bars whose hits all fall in their second half."""


def drum_bars(song: MidiSong, score: Score) -> int:
    """How many bars the drums span: from bar 0 to the bar of the drum track's last note as it
    was played, including notes the kit doesn't map, as `analyze` counts them."""
    starts = [note.start for note in song.notes if note.track == score.track]
    return score.signatures.bar_at(max(starts, default=0)) + 1


def bar_patterns(score: Score, bars: int) -> BarPatterns:
    """The patterns of the first `bars` bars. A hit after them counts in the last."""
    lines = np.array([score.signatures.bar_start(bar) for bar in range(bars + 1)], dtype=np.int64)
    lengths = np.diff(lines)
    hits = [note for note in score.notes if note.grace_of is None]
    families = tuple(sorted({note.family for note in hits}))
    index = {family: position for position, family in enumerate(families)}
    width = max(1, -(-int(lengths.max()) * SLOTS_PER_QUARTER // score.ppq))

    ticks = np.array([note.tick for note in hits], dtype=np.int64)
    bar_of = np.clip(np.searchsorted(lines, ticks, side="right") - 1, 0, bars - 1)
    offsets = ticks - lines[bar_of]
    slots = np.minimum(np.rint(offsets * SLOTS_PER_QUARTER / score.ppq).astype(np.int64), width - 1)
    family_of = np.array([index[note.family] for note in hits], dtype=np.int64)
    patterns = np.zeros((bars, len(families), width))
    patterns[bar_of, family_of, slots] = 1.0
    norms = np.linalg.norm(patterns, axis=2, keepdims=True)
    patterns = np.divide(patterns, norms, out=np.zeros_like(patterns), where=norms > 0)

    early = 2 * offsets < lengths[bar_of]
    in_first = np.bincount(bar_of[early], minlength=bars)
    in_second = np.bincount(bar_of[~early], minlength=bars)
    return BarPatterns(
        patterns=patterns,
        families=families,
        empty=(in_first + in_second) == 0,
        stop=(in_first > 0) & (in_second == 0),
        lead_in=(in_second > 0) & (in_first == 0),
    )


def similarity(patterns: FloatArray) -> FloatArray:
    """How alike each pair of bars is, from 0 to 1."""
    flat = patterns.reshape(patterns.shape[0], -1)
    played = np.count_nonzero(patterns.any(axis=2), axis=1).astype(np.float64)
    scale = np.sqrt(np.outer(played, played))
    dots = flat @ flat.T
    alike = np.divide(dots, scale, out=np.zeros_like(dots), where=scale > 0)
    empty = played == 0
    alike[np.ix_(empty, empty)] = 1.0
    return np.clip(alike, 0.0, 1.0)


def novelty(alike: FloatArray) -> FloatArray:
    """How much each bar starts something new, averaged over the scales that fit around it. It
    is 0 where none fits, in the first two bars and the last."""
    bars = alike.shape[0]
    total = np.zeros(bars)
    count = np.zeros(bars)
    for scale in SCALES:
        for bar in range(scale, bars - scale + 1):
            before, after = slice(bar - scale, bar), slice(bar, bar + scale)
            within = (alike[before, before].mean() + alike[after, after].mean()) / 2
            total[bar] += within - alike[before, after].mean()
            count[bar] += 1
    return np.divide(total, count, out=np.zeros(bars), where=count > 0)


def silences(read: BarPatterns) -> tuple[tuple[int, int], ...]:
    """Each silent stretch as its first bar and the bar after it, with its stop and lead-in."""
    bars = read.empty.size
    stretches: list[tuple[int, int]] = []
    bar = 0
    while bar < bars:
        if not read.empty[bar]:
            bar += 1
            continue
        end = bar
        while end < bars and read.empty[end]:
            end += 1
        if end - bar >= MIN_SILENCE:
            start = bar - 1 if bar > 0 and read.stop[bar - 1] else bar
            if end < bars and read.lead_in[end]:
                end += 1
            stretches.append((start, end))
        bar = end
    return tuple(stretches)


def marker_bars(song: MidiSong, score: Score, bars: int) -> tuple[int, ...]:
    """The bars the file's markers snap to, from any track, after bar 0 and before `bars`. A
    marker snaps to the nearest bar line, and to the later one from halfway."""
    signatures = score.signatures
    found: set[int] = set()
    for event in song.events:
        if event.meta_type != META_MARKER:
            continue
        bar = signatures.bar_at(event.tick)
        start, end = signatures.bar_start(bar), signatures.bar_start(bar + 1)
        if 2 * (event.tick - start) >= end - start:
            bar += 1
        if 0 < bar < bars:
            found.add(bar)
    return tuple(sorted(found))


def drum_boundaries(read: BarPatterns, alike: FloatArray) -> tuple[int, ...]:
    """The bars after bar 0 where the drums start a section. A candidate is a peak of the
    novelty: a bar with hits, at least as novel as the bar before it and more than the bar
    after it."""
    bars = alike.shape[0]
    novel = novelty(alike)
    kept = {bar for stretch in silences(read) for bar in stretch if 0 < bar < bars}
    candidates = [
        bar
        for bar in range(1, bars)
        if novel[bar] > 0
        and novel[bar] >= novel[bar - 1]
        and (bar + 1 == bars or novel[bar] > novel[bar + 1])
        and not read.empty[bar]
    ]
    return choose_boundaries(novel, candidates, kept, bars)


def choose_boundaries(
    novel: FloatArray, candidates: Sequence[int], kept: set[int], bars: int
) -> tuple[int, ...]:
    """The boundaries that score best together, keeping every one of `kept`."""
    fixed = kept | {0, bars}
    positions = sorted(set(candidates) | fixed)
    best: dict[int, float] = {0: 0.0}
    before: dict[int, int] = {}
    last_fixed = 0
    for bar in positions[1:]:
        gain = 0.0 if bar in fixed else float(novel[bar]) - BOUNDARY_COST
        # A section can't run past a kept boundary, so it starts at the last one or later.
        for start in positions:
            if start >= bar:
                break
            if start < last_fixed or start not in best:
                continue
            if bar - start < MIN_BARS and not (start in fixed and bar in fixed):
                continue
            value = best[start] + gain - (0.0 if bar - start in PHRASES else LENGTH_COST)
            if bar not in best or value > best[bar]:
                best[bar] = value
                before[bar] = start
        if bar in fixed:
            last_fixed = bar
    chosen: list[int] = []
    bar = before[bars]
    while bar:
        chosen.append(bar)
        bar = before[bar]
    return tuple(reversed(chosen))


def group_name(index: int) -> str:
    """A repeat group's name from its index: A to Z, then AA, AB and on."""
    name = ""
    number = index + 1
    while number:
        number, letter = divmod(number - 1, 26)
        name = chr(ord("A") + letter) + name
    return name


def repeat_groups(alike: FloatArray, starts: Sequence[int]) -> tuple[str, ...]:
    """The repeat group of each section, from the bars where they start."""
    bars = alike.shape[0]
    spans = list(zip(starts, [*starts[1:], bars], strict=True))
    members: list[list[int]] = []
    groups: list[int] = []
    for position, span in enumerate(spans):
        scores = [
            float(np.mean([_alike(alike, spans[member], span) for member in held]))
            for held in members
        ]
        found = int(np.argmax(scores)) if scores else -1
        if found < 0 or scores[found] < REPEAT:
            found = len(members)
            members.append([])
        members[found].append(position)
        groups.append(found)
    return tuple(group_name(group) for group in groups)


def _alike(alike: FloatArray, first: tuple[int, int], second: tuple[int, int]) -> float:
    """How alike two sections are, comparing their bars in order over the shorter length."""
    length = min(first[1] - first[0], second[1] - second[0])
    block = alike[first[0] : first[0] + length, second[0] : second[0] + length]
    return float(np.diagonal(block).mean())


def find_sections(song: MidiSong, score: Score, *, markers: bool = True) -> Sections:
    """The sections of a song's drums, from its markers when it has them and `markers` is set,
    and otherwise from the drums."""
    bars = drum_bars(song, score)
    read = bar_patterns(score, bars)
    alike = similarity(read.patterns)
    marked = marker_bars(song, score, bars) if markers else ()
    source: SectionSource = "markers" if marked else "drums"
    starts = (0, *(marked or drum_boundaries(read, alike)))
    ends = (*starts[1:], bars)
    groups = repeat_groups(alike, starts)
    return Sections(
        sections=tuple(
            Section(start=start, bars=end - start, group=group)
            for start, end, group in zip(starts, ends, groups, strict=True)
        ),
        source=source,
    )
