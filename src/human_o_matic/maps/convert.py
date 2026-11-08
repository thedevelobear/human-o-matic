"""Converting notes from one kit to another, through canonical names.

Each note is read with the source kit into an articulation, whose name is found in the target
kit by the fallback order. It stops at the first name the target kit has:
1. the exact name;
2. piece substitution: a family re-spread by register, as toms are, takes the piece at the same
   place in the target's range when the kits have different numbers of pieces, and any other
   family takes the nearest piece the target has, which is its last, when it lacks the piece;
3. the name without its last variant, one variant at a time: `hat.open.quarter.tip`, then
   `hat.open.quarter`, then `hat.open`;
4. the piece's default, so `snare.flam` becomes `snare.center`, except for an articulation the
   vocabulary lists in `ask_if_missing`, such as a choke.
Every step after the first is reported. A hit never leaves its family unless the user picks a
substitute. These are decision requests instead: a target that lacks the family, a target that
lacks an `ask_if_missing` articulation, an articulation that depends on a controller value,
which M1 doesn't follow (ADR 0009), and notes the source kit doesn't map at all.

The answers come back as `substitutions`, from a source articulation to the target articulation
it becomes, and `unmapped`, from a source pitch to the target articulation. Either may be `DROP`,
which leaves those notes out. Converting a kit to itself keeps every note as it is.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from human_o_matic.decisions import DecisionOption, DecisionRequest
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.schema import Confidence
from human_o_matic.maps.vocabulary import CanonicalName, PieceSubstitution
from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import TimeSignatureMap

DROP = "drop"
"""The answer that leaves notes out. No canonical name is a single word, so none can clash."""
MAX_POSITIONS = 8
"""A decision request lists at most this many positions per group of notes, with the count."""

type StepKind = Literal["piece", "variant", "default", "picked"]
type Reason = Literal["family", "articulation", "cc"]
"""Why a conversion asks: the target lacks the family; it lacks an articulation that has no
fallback; or the articulation depends on a controller value."""

_CONFIDENCE_ORDER: tuple[Confidence, ...] = ("low", "medium", "high")


class Step(BaseModel):
    """One inexact step of a conversion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: StepKind
    """`piece`, `variant` or `default`, the fallback steps, or `picked` by the user."""
    asked: str
    used: str


class Row(BaseModel):
    """How the notes of one source articulation were converted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    """The source articulation. When a controller value decides between several, they are
    joined by `|`, and a pitch the source kit doesn't map is `note N`."""
    target: str
    """The target articulation, or `drop`."""
    count: int
    steps: tuple[Step, ...] = ()
    """Each inexact step, in order, and none for the exact name."""
    source_confidence: Confidence | None = None
    target_confidence: Confidence | None = None
    clamped: int = 0
    """How many of the notes had their velocity moved into the target's velocity range."""


@dataclass(frozen=True, slots=True)
class Resolution:
    """Where a source articulation goes in the target kit."""

    target: str | None
    """The target articulation, or None when the conversion has to ask."""
    steps: tuple[Step, ...] = ()
    reason: Reason | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Conversion:
    """The result of a conversion: the notes it settled, and what it asks about the rest."""

    notes: tuple[Note, ...]
    """The converted notes, in the order they came. Dropped notes and the notes waiting for a
    decision are left out."""
    pending: tuple[Note, ...]
    """The notes waiting for a decision, as they came."""
    rows: tuple[Row, ...]
    """How each source articulation was converted, in the order they first appear."""
    decisions: tuple[DecisionRequest, ...]

    @property
    def complete(self) -> bool:
        return not self.decisions

    @property
    def inexact(self) -> tuple[Row, ...]:
        return tuple(row for row in self.rows if row.steps)


def substitute_piece(
    rule: PieceSubstitution, piece: int, source_pieces: int, target_pieces: int
) -> int:
    """The target piece for a source piece, given how many pieces each kit has.

    `register` re-spreads when the counts differ: piece i of n_s becomes round-half-down(1 +
    (i - 1)(n_t - 1) / (n_s - 1)), so 6 toms onto 3 go 1, 1, 2, 2, 3, 3, and 3 onto 6 go 1, 3, 6.
    `nearest` keeps the piece, or takes the last one when the target has fewer.
    """
    if rule == "register" and source_pieces != target_pieces:
        if source_pieces == 1 or target_pieces == 1:
            return 1
        steps, spans = (piece - 1) * (target_pieces - 1), source_pieces - 1
        # Rounding steps / spans half down is ceil((2 * steps - spans) / (2 * spans)).
        return 1 + -(-(2 * steps - spans) // (2 * spans))
    return min(piece, target_pieces)


def resolve_name(name: str, source: DrumKit, target: DrumKit) -> Resolution:
    """Where one of the source kit's articulations goes in the target kit, by the fallback
    order. It looks at names only: `convert` asks about notes that depend on a controller value
    before it gets here."""
    vocabulary = target.vocabulary
    asked = source.canonical(name)
    pieces = target.pieces(asked.family)
    if not pieces:
        return Resolution(None, reason="family")
    rule = vocabulary.families[asked.family].piece_substitution
    piece = substitute_piece(rule, asked.piece, source.pieces(asked.family), pieces)
    steps: list[Step] = []
    current = asked
    if piece != asked.piece:
        current = vocabulary.name(asked.family, piece, asked.path)
        steps.append(Step(kind="piece", asked=asked.text, used=current.text))
    return _within_piece(current, target, steps)


def _within_piece(name: CanonicalName, target: DrumKit, steps: list[Step]) -> Resolution:
    """The fallback steps that stay on the name's piece: drop variants, then the default."""
    vocabulary = target.vocabulary
    while name.text not in target and name.variants:
        parent = vocabulary.name(name.family, name.piece, name.path[:-1])
        steps.append(Step(kind="variant", asked=name.text, used=parent.text))
        name = parent
    if name.text in target:
        return Resolution(name.text, tuple(steps))
    if name.articulation in vocabulary.ask_if_missing:
        return Resolution(None, tuple(steps), reason="articulation")
    default = vocabulary.default(name.family, name.piece)
    steps.append(Step(kind="default", asked=name.text, used=default.text))
    return Resolution(default.text, tuple(steps))


def suggestions(name: str, source: DrumKit, target: DrumKit) -> tuple[str, ...]:
    """The target kit's articulations from other families that the vocabulary suggests for a
    source articulation. They are offered to the user, never applied."""
    vocabulary = target.vocabulary
    asked = source.canonical(name)
    found: list[str] = []
    for substitute in vocabulary.suggestions.get(asked.family, ()):
        family, _, given = substitute.partition(".")
        pieces = target.pieces(family)
        if not pieces:
            continue
        allowed = vocabulary.families[family]
        path = tuple(given.split(".")) if given else asked.path
        while path and ".".join(path) not in allowed.articulations:
            path = path[:-1]
        piece = min(asked.piece if allowed.pieces == "numbered" else 1, pieces)
        start = vocabulary.name(family, piece, path or (allowed.default,))
        resolution = _within_piece(start, target, [])
        if resolution.target is not None and resolution.target not in found:
            found.append(resolution.target)
    return tuple(found)


@dataclass(slots=True)
class _Tally:
    steps: tuple[Step, ...]
    source_confidence: Confidence | None
    target_confidence: Confidence | None
    count: int = 0
    clamped: int = 0


def convert(
    notes: Iterable[Note],
    source: DrumKit,
    target: DrumKit,
    signatures: TimeSignatureMap,
    *,
    substitutions: Mapping[str, str] | None = None,
    unmapped: Mapping[int, str] | None = None,
) -> Conversion:
    """Convert notes read with `source` into notes for `target`.

    `signatures` places the notes in bars and beats for the decision requests. `substitutions`
    and `unmapped` are the user's answers to earlier requests: each value is an articulation of
    the target kit, or `DROP`. Raises `ValueError` for an answer the target kit can't play.
    """
    if source.vocabulary is not target.vocabulary:
        raise ValueError("the two kits were loaded with different vocabularies")
    picks = _checked(substitutions or {}, target)
    pitch_picks = _checked(unmapped or {}, target)
    same_kit = source.ref == target.ref
    resolutions: dict[str, Resolution] = {}
    converted: list[Note] = []
    pending: list[Note] = []
    tallies: dict[tuple[str, str], _Tally] = {}
    waiting: dict[tuple[Reason, str], list[Note]] = {}
    unknown: dict[int, list[Note]] = {}

    def wait(reason: Reason, key: str, note: Note) -> None:
        waiting.setdefault((reason, key), []).append(note)
        pending.append(note)

    for note in notes:
        matches = source.read(note.pitch, note.velocity, note.channel)
        if not matches:
            key, confidence, controlled = f"note {note.pitch}", None, False
            choice = pitch_picks.get(note.pitch)
            if choice is None:
                unknown.setdefault(note.pitch, []).append(note)
                pending.append(note)
                continue
        else:
            key = "|".join(match.articulation.name for match in matches)
            confidence = _lowest(match.articulation.confidence for match in matches)
            controlled = matches[0].binding.cc is not None or len(matches) > 1
            choice = picks.get(key)
        if choice is not None:
            steps = (Step(kind="picked", asked=key, used=choice),)
        elif same_kit:
            tally = tallies.setdefault((key, key), _Tally((), confidence, confidence))
            tally.count += 1
            converted.append(note)
            continue
        elif controlled:
            wait("cc", key, note)
            continue
        else:
            if key not in resolutions:
                resolutions[key] = resolve_name(key, source, target)
            resolution = resolutions[key]
            if resolution.target is None:
                wait(resolution.reason or "family", key, note)
                continue
            if target.write(resolution.target).cc is not None:
                wait("cc", key, note)
                continue
            choice, steps = resolution.target, resolution.steps

        tally = tallies.get((key, choice))
        if tally is None:
            used = target.articulation(choice).confidence if choice != DROP else None
            tally = tallies[key, choice] = _Tally(steps, confidence, used)
        tally.count += 1
        if choice == DROP:
            continue
        output = target.write(choice)
        velocity = min(max(note.velocity, output.velocity[0]), output.velocity[1])
        tally.clamped += velocity != note.velocity
        channel = output.channel if output.channel is not None else note.channel
        converted.append(replace(note, pitch=output.pitch, channel=channel, velocity=velocity))

    decisions: list[DecisionRequest] = []
    if unknown:
        decisions.append(_unmapped_request(unknown, source, target, signatures))
    for (reason, key), held in waiting.items():
        resolution = resolutions.get(key, Resolution(None))
        decisions.append(
            _conversion_request(reason, key, held, resolution, source, target, signatures)
        )
    rows = tuple(
        Row(
            source=key,
            target=choice,
            count=tally.count,
            steps=tally.steps,
            source_confidence=tally.source_confidence,
            target_confidence=tally.target_confidence,
            clamped=tally.clamped,
        )
        for (key, choice), tally in tallies.items()
    )
    return Conversion(
        notes=tuple(converted), pending=tuple(pending), rows=rows, decisions=tuple(decisions)
    )


def _checked[K](answers: Mapping[K, str], target: DrumKit) -> dict[K, str]:
    for key, answer in answers.items():
        if answer == DROP:
            continue
        if answer not in target:
            raise ValueError(f"{key}: {target.label} has no {answer}")
        if target.write(answer).cc is not None:
            raise ValueError(f"{key}: {answer} depends on a controller, which M1 doesn't write")
    return dict(answers)


def _lowest(confidences: Iterable[Confidence]) -> Confidence:
    return min(confidences, key=_CONFIDENCE_ORDER.index)


def _positions(notes: Sequence[Note], signatures: TimeSignatureMap) -> list[JsonValue]:
    """The first notes' positions as `[bar, beat]`, counted from 0."""
    starts = sorted(note.start for note in notes)[:MAX_POSITIONS]
    places = [signatures.position(start) for start in starts]
    return [[place.bar, round(place.beat, 3)] for place in places]


def _from_bar(notes: Sequence[Note], signatures: TimeSignatureMap) -> str:
    """For example "3 notes from bar 5", with bars counted from 1."""
    first = signatures.bar_at(min(note.start for note in notes)) + 1
    return f"{_count(len(notes), 'note')} from bar {first}"


def _count(count: int, noun: str, plural: str | None = None) -> str:
    return f"{count} {noun if count == 1 else plural or noun + 's'}"


def _unmapped_request(
    unknown: Mapping[int, Sequence[Note]],
    source: DrumKit,
    target: DrumKit,
    signatures: TimeSignatureMap,
) -> DecisionRequest:
    total = sum(len(held) for held in unknown.values())
    listed = "; ".join(
        f"note {pitch}: {_from_bar(held, signatures)}" for pitch, held in sorted(unknown.items())
    )
    groups: list[JsonValue] = [
        {
            "pitch": pitch,
            "channels": [*sorted({note.channel for note in held})],
            "count": len(held),
            "positions": _positions(held, signatures),
        }
        for pitch, held in sorted(unknown.items())
    ]
    have = "has" if total == 1 else "have"
    return DecisionRequest(
        kind="unmapped_notes",
        message=f"{_count(total, 'note')} on {_count(len(unknown), 'pitch', 'pitches')} {have} no "
        f"articulation in {source.label}, so they can't be converted ({listed}). What does each "
        f"pitch play in {target.label}? Leaving them out, or reading the file with another "
        "map, also settles it.",
        answer_with=("unmapped", "from_map"),
        details={"kit": source.ref, "notes": groups},
    )


def _conversion_request(
    reason: Reason,
    key: str,
    held: Sequence[Note],
    resolution: Resolution,
    source: DrumKit,
    target: DrumKit,
    signatures: TimeSignatureMap,
) -> DecisionRequest:
    first = key.split("|")[0]
    label = source.articulation(first).label if "|" not in key else None
    what = f"{label} ({key})" if label else key
    asked = source.canonical(first)
    offered: list[str] = []
    if reason == "family":
        why = f"{target.label} has no {asked.family}"
        offered.extend(suggestions(first, source, target))
    elif reason == "articulation":
        tried = target.vocabulary.parse(resolution.steps[-1].used if resolution.steps else key)
        default = target.vocabulary.default(tried.family, tried.piece)
        why = (
            f"{target.label} has no {tried}, and playing {default} instead could sound a hit "
            "the source never did"
        )
        offered.append(default.text)
    else:
        why = "it depends on a controller value, which this version can't convert yet"
        if target.pieces(asked.family):
            default = target.vocabulary.default(asked.family, 1)
            if target.write(default.text).cc is None:
                offered.append(default.text)
    them = "it" if len(held) == 1 else "them"
    options = [_option(name, target, them) for name in offered]
    options.append(DecisionOption(value=DROP, label=f"Leave {them} out"))
    return DecisionRequest(
        kind="conversion",
        message=f"{what}, {_from_bar(held, signatures)}, can't be converted: {why}. What "
        f"should {'it' if len(held) == 1 else 'they'} play in {target.label}?",
        answer_with=("substitutions",),
        options=tuple(options),
        details={
            "source": key,
            "reason": reason,
            "count": len(held),
            "positions": _positions(held, signatures),
        },
    )


def _option(name: str, target: DrumKit, them: str) -> DecisionOption:
    label = target.articulation(name).label
    described = f" ({label})" if label else ""
    pitch = target.write(name).pitch
    return DecisionOption(value=name, label=f"Play {them} as {name}{described}, note {pitch}")
