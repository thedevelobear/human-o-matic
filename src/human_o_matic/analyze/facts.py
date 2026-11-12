"""Facts about each section, for the agent to ask good questions with (ADRs 0035 and 0082).

Every fact is counted from the score and the parts the drums give its notes (ADR 0047), never
from a library's pitches: how many notes each family plays and how many are soft or accents,
which cymbal keeps time, whether the backbeat is half-time, the double kick, the bars with fills,
with no notes and with a grid that is a guess, and the meter and tempo. `plays` says the most
telling of them in words, such as "crash riding, half-time, 34 soft snare notes".

A section's pattern is one bar in compact ASCII: its most typical bar, the one most alike the
section's other bars, and, when its last bar plays differently, as a fill does, that one too.
Each family is a row, from the cymbals down to the kick, with the hat pedal a row of its own,
and each column a step of the finest grid the bar needs, from 16ths, with the beats apart:
`X` an accent, `x` a normal hit, `o` a soft one and `.` none. Graces are left out, as in the
bar patterns of `sections.py`.

The guess is modest and says how sure it is. A section with no notes is silent, one in a repeat
group after its first plays like that first one, and a short one made mostly of fills is a fill:
the score shows each of these. Anything else is a groove, and how hard it plays is not guessed,
since it isn't readable from its notes: within a song, a drummer's level hardly follows note
density. The suggested questions follow the plan's question policy: the energy, and one more,
for a group's first section, and for its last repeat, whether it plays bigger.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from human_o_matic.analyze.sections import (
    REPEAT,
    BarPatterns,
    Section,
    aligned_similarity,
    bar_patterns,
    similarity,
)
from human_o_matic.midi.tempo import MICROSECONDS_PER_MINUTE
from human_o_matic.normalize.hit_types import HitType
from human_o_matic.normalize.score import Score, ScoreNote
from human_o_matic.render.parts import Part

type GuessKind = Literal["silent", "repeat", "fill", "groove"]
type GuessConfidence = Literal["low", "medium", "high"]

ROWS = ("crash", "china", "splash", "stack", "ride", "hat", "pedal")
"""The pattern's first rows, from the top. Families not named here or in `LAST_ROWS` come between
them, in name order."""
LAST_ROWS = ("tom", "snare", "kick")
DIVISIONS = (4, 3, 6, 8, 12, 24)
"""A pattern's columns per quarter note, from the simplest: 16ths, 8th triplets, 16th triplets,
32nds, and the steps that mix them. The first that puts every hit of the bar on a column is
used, and 24, where every grid point is a column (ADR 0036), otherwise."""
SYMBOLS: dict[HitType, str] = {"soft": "o", "normal": "x", "accent": "X"}
EMPTY = "."
RIDING_SHARE = 0.5
"""A cymbal keeps time when its riding hits number at least this share of the section's beats."""
HALF_TIME_SHARE = 0.75
"""A section is half-time when at least this share of its 4/4 bars with a snare on a beat have it
on beat 3 and not on 2 or 4."""
DOUBLE_KICK_NOTES = 4
"""The fewest double kick notes `plays` mentions."""
FILL_SHARE = 0.5
"""A section of `FILL_BARS` or fewer is a fill when at least this share of its hits are fills."""
FILL_BARS = 2
CLOSE_REPEAT = 0.95
"""How alike a repeat must be to its group's first section to be guessed at high confidence."""


class FamilyFacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    notes: int
    per_bar: float
    soft: int
    accent: int


class HitTypeFacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    soft: int
    normal: int
    accent: int
    low_confidence: int
    """The notes whose type is a guess, until the `hit_types` request is answered."""


class Pattern(BaseModel):
    """One bar in compact ASCII."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bar: int
    """Counting from 0."""
    per_beat: int
    """Columns per beat: 4 for 16ths in 4/4."""
    lines: tuple[str, ...]
    """A row per family, its name and then a column per step, the beats apart."""


class Guess(BaseModel):
    """What the section probably is, and how sure the guess is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: GuessKind
    confidence: GuessConfidence
    says: str
    like: int | None = None
    """For a repeat, the first bar of the section it plays like."""


class SectionFacts(BaseModel):
    """What one section plays, counted from the score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: int
    bars: int
    label: str
    """Its bars counted from 1, as a DAW shows them, such as "bars 9 to 24"."""
    group: str
    plays: str
    """The most telling facts in words."""
    meter: tuple[str, ...]
    """The time signatures in force, in order, such as `("4/4",)`."""
    bpm: tuple[float, float]
    """The lowest and highest tempo."""
    notes: int
    per_bar: float
    families: dict[str, FamilyFacts]
    hit_types: HitTypeFacts
    riding: str | None
    """The cymbal family that keeps time, or None."""
    half_time: bool | None
    """None when no 4/4 bar has a snare on a beat."""
    double_kick: int
    """Kick notes in double kick runs."""
    fill_bars: tuple[int, ...]
    empty_bars: tuple[int, ...]
    ambiguous_bars: tuple[int, ...]
    """Bars with a beat whose grid is a guess, until the `ambiguous_bars` request is answered."""
    pattern: Pattern | None
    """Its most typical bar, or None when it has no hits."""
    ends: Pattern | None
    """Its last bar with hits, when that plays unlike `pattern`."""
    guess: Guess
    questions: tuple[str, ...]


def label(start: int, bars: int) -> str:
    """A run of bars counted from 1: "bar 9" or "bars 9 to 24"."""
    return f"bar {start + 1}" if bars == 1 else f"bars {start + 1} to {start + bars}"


def song_facts(
    score: Score, parts: Sequence[Part], sections: Sequence[Section], bars: int
) -> tuple[SectionFacts, ...]:
    """The facts of each section, in order. `parts` are the drums' parts of the score's notes,
    and `bars` the drums' bars, which the sections cover."""
    read = bar_patterns(score, bars)
    bar_of = heard_bars(score)
    groups: dict[str, list[Section]] = {}
    for section in sections:
        groups.setdefault(section.group, []).append(section)
    out: list[SectionFacts] = []
    for section in sections:
        members = [
            position for position, bar in enumerate(bar_of) if section.start <= bar < section.end
        ]
        counts = _counts(score, parts, bar_of, section, members)
        group = groups[section.group]
        first = group[0] if group[0] is not section else None
        guess = _guess(section, counts, first, _alike(read, first, section) if first else None)
        out.append(
            SectionFacts(
                start=section.start,
                bars=section.bars,
                label=label(section.start, section.bars),
                group=section.group,
                plays=_plays(counts),
                meter=_meter(score, section),
                bpm=_bpm(score, section),
                notes=len(members),
                per_bar=round(len(members) / section.bars, 2),
                families=counts.families,
                hit_types=counts.hit_types,
                riding=counts.riding,
                half_time=counts.half_time,
                double_kick=counts.double_kick,
                fill_bars=counts.fill_bars,
                empty_bars=counts.empty_bars,
                ambiguous_bars=counts.ambiguous_bars,
                pattern=_pattern(score, read, bar_of, section),
                ends=_ends(score, read, bar_of, section),
                guess=guess,
                questions=_questions(section, counts, guess, group),
            )
        )
    return tuple(out)


def heard_bars(score: Score) -> tuple[int, ...]:
    """The bar each of the score's notes is heard in: the bar of its tick, or for a grace, of its
    main's, so a flam before a downbeat counts with it."""
    by_source = {note.source_index: note for note in score.notes}
    return tuple(
        score.signatures.bar_at(
            note.tick if note.grace_of is None else by_source[note.grace_of].tick
        )
        for note in score.notes
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class _Counts:
    """What `plays`, the guess and the questions are made from."""

    families: dict[str, FamilyFacts]
    hit_types: HitTypeFacts
    riding: str | None
    half_time: bool | None
    double_kick: int
    fill_bars: tuple[int, ...]
    empty_bars: tuple[int, ...]
    ambiguous_bars: tuple[int, ...]
    hits: int
    """Notes that aren't graces."""
    fill_hits: int
    crashes: dict[str, int]
    """Accent cymbal hits per family, but on the cymbal that keeps time."""
    toms: int
    """Tom hits outside fills."""


def _counts(
    score: Score,
    parts: Sequence[Part],
    bar_of: Sequence[int],
    section: Section,
    members: Sequence[int],
) -> _Counts:
    notes = [score.notes[position] for position in members]
    families: dict[str, FamilyFacts] = {}
    for family in sorted({note.family for note in notes}, key=_row_key):
        mine = [note for note in notes if note.family == family]
        families[family] = FamilyFacts(
            notes=len(mine),
            per_bar=round(len(mine) / section.bars, 2),
            soft=sum(note.hit_type == "soft" for note in mine),
            accent=sum(note.hit_type == "accent" for note in mine),
        )
    types = Counter(note.hit_type for note in notes)
    mains = [position for position in members if score.notes[position].grace_of is None]
    roles = [(score.notes[position], parts[position]) for position in mains]
    riders = Counter(note.family for note, part in roles if part.role == "rider")
    riding = None
    if riders:
        family = max(sorted(riders, key=_row_key), key=lambda name: riders[name])
        if riders[family] >= RIDING_SHARE * _beats(score, section):
            riding = family
    played = {bar_of[position] for position in members}
    crashes = Counter(
        note.family
        for note, part in roles
        if part.role == "accent_cymbal" and note.family != riding
    )
    return _Counts(
        families=families,
        hit_types=HitTypeFacts(
            soft=types["soft"],
            normal=types["normal"],
            accent=types["accent"],
            low_confidence=sum(note.hit_type_confidence == "low" for note in notes),
        ),
        riding=riding,
        half_time=_half_time(score, [note for note, _ in roles]),
        double_kick=sum(part.role == "double_kick" for _, part in roles),
        fill_bars=tuple(
            sorted({bar_of[position] for position in mains if parts[position].role == "fill"})
        ),
        empty_bars=tuple(bar for bar in range(section.start, section.end) if bar not in played),
        ambiguous_bars=tuple(
            sorted(
                {beat.bar for beat in score.ambiguous if section.start <= beat.bar < section.end}
            )
        ),
        hits=len(mains),
        fill_hits=sum(part.role == "fill" for _, part in roles),
        crashes={family: crashes[family] for family in sorted(crashes, key=_row_key)},
        toms=sum(note.family == "tom" and part.role != "fill" for note, part in roles),
    )


def _beats(score: Score, section: Section) -> int:
    """How many beats the section's bars hold."""
    signatures = score.signatures
    return sum(
        signatures.signature_at(signatures.bar_start(bar)).numerator
        for bar in range(section.start, section.end)
    )


def _half_time(score: Score, mains: Sequence[ScoreNote]) -> bool | None:
    """Whether most 4/4 bars with a snare on a beat, not typed soft, have it on beat 3 alone of
    the backbeats, or None when none has."""
    beats: dict[int, set[int]] = {}
    for note in mains:
        signature = score.signatures.signature_at(note.tick)
        place = score.position(note.tick)
        if (
            note.family == "snare"
            and note.hit_type != "soft"
            and place.beat.is_integer()
            and (signature.numerator, signature.denominator) == (4, 4)
        ):
            beats.setdefault(place.bar, set()).add(int(place.beat))
    if not beats:
        return None
    half = sum(2 in held and not held & {1, 3} for held in beats.values())
    return half >= HALF_TIME_SHARE * len(beats)


def _meter(score: Score, section: Section) -> tuple[str, ...]:
    signatures = score.signatures
    first = signatures.bar_start(section.start)
    found = [str(signatures.signature_at(first))]
    for _, bar, signature in signatures.changes:
        if section.start < bar < section.end and str(signature) != found[-1]:
            found.append(str(signature))
    return tuple(found)


def _bpm(score: Score, section: Section) -> tuple[float, float]:
    tempos = score.tempos
    first = score.signatures.bar_start(section.start)
    last = score.signatures.bar_start(section.end)
    inside = (tempos.starts > first) & (tempos.starts < last)
    values = [tempos.bpm(first), *(MICROSECONDS_PER_MINUTE / tempos.tempos[inside]).tolist()]
    return round(min(values), 3), round(max(values), 3)


def _plays(counts: _Counts) -> str:
    """The most telling facts in words."""
    if counts.hits == 0:
        return "silent"
    words: list[str] = []
    if counts.riding is not None:
        words.append({"hat": "hats", "ride": "ride"}.get(counts.riding, f"{counts.riding} riding"))
    if counts.half_time:
        words.append("half-time")
    if counts.double_kick >= DOUBLE_KICK_NOTES:
        words.append("double kick")
    if counts.toms:
        words.append("toms")
    words.extend(
        f"{count} {family} hit{'s' if count > 1 else ''}"
        for family, count in counts.crashes.items()
    )
    if counts.fill_bars:
        fills = "a fill" if len(counts.fill_bars) <= FILL_BARS else "fills"
        words.append(f"{fills} in {_listed_bars(counts.fill_bars)}")
    words.extend(
        f"{facts.soft} soft {family} note{'s' if facts.soft > 1 else ''}"
        for family, facts in counts.families.items()
        if facts.soft
    )
    if counts.empty_bars:
        rests = len(counts.empty_bars)
        words.append(f"{rests} bar{'s' if rests > 1 else ''} of rest")
    if counts.ambiguous_bars:
        words.append(f"an unclear grid in {_listed_bars(counts.ambiguous_bars)}")
    return ", ".join(words) if words else "a groove"


def _listed_bars(bars: Sequence[int]) -> str:
    """Bars counted from 1: "bar 16", "bars 8 and 16", or "4 bars" for more than three."""
    if len(bars) > 3:
        return f"{len(bars)} bars"
    named = [str(bar + 1) for bar in bars]
    if len(named) == 1:
        return f"bar {named[0]}"
    return f"bars {', '.join(named[:-1])} and {named[-1]}"


def _row(note: ScoreNote) -> str:
    """A note's row: its family, or `pedal` for the hat pedal."""
    if note.family == "hat" and "pedal" in note.articulation.split("|")[0].split("."):
        return "pedal"
    return note.family


def _row_key(row: str) -> tuple[int, str]:
    if row in ROWS:
        return ROWS.index(row), ""
    if row in LAST_ROWS:
        return len(ROWS) + 1 + LAST_ROWS.index(row), ""
    return len(ROWS), row


def _typical(read: BarPatterns, section: Section) -> int | None:
    """The bar with hits most alike the section's other bars with hits, the earliest of a tie,
    or None when no bar has hits."""
    played = [bar for bar in range(section.start, section.end) if not read.empty[bar]]
    if not played:
        return None
    alike = similarity(read.patterns[played])
    return played[int(np.argmax(alike.mean(axis=1)))]


def _pattern(
    score: Score, read: BarPatterns, bar_of: Sequence[int], section: Section
) -> Pattern | None:
    bar = _typical(read, section)
    return draw_bar(score, bar, bar_of) if bar is not None else None


def _ends(
    score: Score, read: BarPatterns, bar_of: Sequence[int], section: Section
) -> Pattern | None:
    typical = _typical(read, section)
    played = [bar for bar in range(section.start, section.end) if not read.empty[bar]]
    if typical is None or played[-1] == typical:
        return None
    last = played[-1]
    pair = aligned_similarity(read.patterns[[typical]], read.patterns[[last]])
    return draw_bar(score, last, bar_of) if float(pair[0]) < REPEAT else None


def draw_bar(score: Score, bar: int, bar_of: Sequence[int] | None = None) -> Pattern:
    """One bar of the score in compact ASCII, graces left out. `bar_of` is `heard_bars`, when
    it is at hand."""
    signatures = score.signatures
    start, end = signatures.bar_start(bar), signatures.bar_start(bar + 1)
    signature = signatures.signature_at(start)
    heard = heard_bars(score) if bar_of is None else bar_of
    hits = [
        note
        for note, at in zip(score.notes, heard, strict=True)
        if note.grace_of is None and at == bar
    ]
    ppq = score.ppq
    # A beat holds a whole number of columns.
    usable = [d for d in DIVISIONS if 4 * d % signature.denominator == 0] or [DIVISIONS[-1]]
    division = next(
        (
            division
            for division in usable
            if all((note.tick - start) * division % ppq == 0 for note in hits)
        ),
        usable[-1],
    )
    columns = max(1, round((end - start) * division / ppq))
    per_beat = max(1, 4 * division // signature.denominator)
    rows: dict[str, list[str]] = {}
    rank = {EMPTY: 0, "o": 1, "x": 2, "X": 3}
    for note in hits:
        column = min(round((note.tick - start) * division / ppq), columns - 1)
        cells = rows.setdefault(_row(note), [EMPTY] * columns)
        symbol = SYMBOLS[note.hit_type]
        if rank[symbol] > rank[cells[column]]:
            cells[column] = symbol
    width = max((len(row) for row in rows), default=0)
    lines = tuple(
        f"{row:<{width}} "
        + " ".join(
            "".join(rows[row][beat : beat + per_beat]) for beat in range(0, columns, per_beat)
        )
        for row in sorted(rows, key=_row_key)
    )
    return Pattern(bar=bar, per_beat=per_beat, lines=lines)


def _alike(read: BarPatterns, first: Section, second: Section) -> float:
    """How alike two sections play, their bars compared in order over the shorter length."""
    length = min(first.bars, second.bars)
    pairs = aligned_similarity(
        read.patterns[first.start : first.start + length],
        read.patterns[second.start : second.start + length],
    )
    return float(pairs.mean())


def _guess(section: Section, counts: _Counts, first: Section | None, alike: float | None) -> Guess:
    if counts.hits == 0:
        return Guess(
            kind="silent",
            confidence="high",
            says="No drums play here, so there is nothing to ask.",
        )
    if first is not None and alike is not None:
        return Guess(
            kind="repeat",
            confidence="high" if alike >= CLOSE_REPEAT else "medium",
            says=f"Plays like {label(first.start, first.bars)}, so it can take the same "
            "controls. Ask only if it should differ, as a bigger last chorus does.",
            like=first.start,
        )
    if section.bars <= FILL_BARS and counts.fill_hits >= FILL_SHARE * counts.hits:
        return Guess(
            kind="fill",
            confidence="medium",
            says="A short fill: fill_intensity sets how hard it builds.",
        )
    return Guess(
        kind="groove",
        confidence="low",
        says="A groove. How hard it plays isn't readable from its notes, so ask.",
    )


def _questions(
    section: Section, counts: _Counts, guess: Guess, group: Sequence[Section]
) -> tuple[str, ...]:
    where = label(section.start, section.bars)
    match guess.kind:
        case "silent":
            return ()
        case "repeat":
            first = group[0]
            if section is group[-1]:
                verb = "plays" if section.bars == 1 else "play"
                return (
                    f"{where.capitalize()} {verb} like {label(first.start, first.bars)}: the "
                    "same, or bigger, as the last time?",
                )
            return ()
        case "fill":
            return (f"How hard should the fill in {where} hit?",)
        case "groove":
            asked = [f"What's the energy in {where} ({_plays(counts)})?"]
            if counts.hit_types.soft:
                asked.append("Should its soft notes be more present, or tucked away?")
            elif counts.riding is not None:
                asked.append("Steady and even, or more groove, with more light and shade?")
            return tuple(asked)
