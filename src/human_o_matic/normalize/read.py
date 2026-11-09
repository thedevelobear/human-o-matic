"""Reading the drum track through a kit: each note to the articulation it plays.

Every later stage works on canonical names, so it is library-neutral. A note the kit doesn't map
is not guessed at: it waits for the user, in one `unmapped_notes` decision request that lists
each pitch with its channels, count and first positions, as conversion does (ADR 0021). The
answer is `unmapped`, from a pitch to an articulation of the kit or `DROP`, or another
`from_map`, and an answer for a pitch with no unmapped note is an error. A note a controller
value decides among several articulations keeps them all, joined by `|` as conversion keys
them, since controllers aren't followed (ADR 0053). Notes read through a `low` confidence
articulation are counted per articulation, so the agent can confirm the names with the user
(ADR 0025).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, JsonValue

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.convert import DROP, MAX_POSITIONS
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.schema import Confidence
from human_o_matic.midi.io import MidiSong, Note
from human_o_matic.midi.tempo import TimeSignatureMap
from human_o_matic.normalize.answers import AnswerError

_CONFIDENCE_ORDER: tuple[Confidence, ...] = ("low", "medium", "high")


@dataclass(frozen=True, slots=True, kw_only=True)
class Hit:
    """A drum note and the articulation the kit reads it as."""

    index: int
    """The note's position in `MidiSong.notes`."""
    note: Note
    articulation: str
    """A canonical name of the kit. When a controller value decides among several, they are
    joined by `|`, all in one family."""
    family: str
    piece: int
    confidence: Confidence
    """The articulation's confidence, or the lowest of several."""


class LowConfidence(BaseModel):
    """How many notes were read through one `low` confidence articulation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    articulation: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """The drum track read through a kit."""

    hits: tuple[Hit, ...]
    """The notes the kit maps, or the user mapped, in the order of `MidiSong.notes`."""
    unmapped: tuple[int, ...]
    """The positions in `MidiSong.notes` of the notes waiting for a decision."""
    dropped: tuple[int, ...]
    """The positions of the notes the user chose to leave out."""
    low_confidence: tuple[LowConfidence, ...]
    """Per `low` confidence articulation, in the order they first appear."""
    decisions: tuple[DecisionRequest, ...]


def read_drums(
    song: MidiSong,
    track: int,
    kit: DrumKit,
    signatures: TimeSignatureMap,
    *,
    unmapped: Mapping[int, str] | None = None,
) -> Reading:
    """Read the notes of `track` through `kit`.

    `unmapped` answers an earlier `unmapped_notes` request: from a pitch to an articulation of
    the kit, or `DROP`. Raises `AnswerError` for an articulation the kit doesn't have, and for a
    pitch with no note the kit leaves unmapped.
    """
    answers = dict(unmapped or {})
    for pitch, answer in answers.items():
        if answer != DROP and answer not in kit:
            raise AnswerError("unmapped", pitch, f"note {pitch}: {kit.label} has no {answer}")
    answered: set[int] = set()
    hits: list[Hit] = []
    waiting: dict[int, list[tuple[int, Note]]] = {}
    dropped: list[int] = []
    low: dict[str, int] = {}
    for index, note in enumerate(song.notes):
        if note.track != track:
            continue
        matches = kit.read(note.pitch, note.velocity, note.channel)
        if matches:
            names = [match.articulation.name for match in matches]
            confidence = _lowest(match.articulation.confidence for match in matches)
        elif note.pitch in answers:
            answered.add(note.pitch)
            if answers[note.pitch] == DROP:
                dropped.append(index)
                continue
            names = [answers[note.pitch]]
            confidence = kit.articulation(names[0]).confidence
        else:
            waiting.setdefault(note.pitch, []).append((index, note))
            continue
        name = kit.canonical(names[0])
        articulation = "|".join(names)
        hits.append(
            Hit(
                index=index,
                note=note,
                articulation=articulation,
                family=name.family,
                piece=name.piece,
                confidence=confidence,
            )
        )
        if confidence == "low":
            low[articulation] = low.get(articulation, 0) + 1
    stray = sorted(answers.keys() - answered)
    if stray:
        raise _stray(stray[0], hits, kit)
    decisions = (_unmapped_request(waiting, kit, signatures),) if waiting else ()
    return Reading(
        hits=tuple(hits),
        unmapped=tuple(sorted(index for held in waiting.values() for index, _ in held)),
        dropped=tuple(dropped),
        low_confidence=tuple(LowConfidence(articulation=a, count=c) for a, c in low.items()),
        decisions=decisions,
    )


def positions(ticks: Iterable[int], signatures: TimeSignatureMap) -> list[JsonValue]:
    """The first ticks' positions as `[bar, beat]`, counted from 0, at most `MAX_POSITIONS`."""
    places = [signatures.position(tick) for tick in sorted(ticks)[:MAX_POSITIONS]]
    return [[place.bar, round(place.beat, 3)] for place in places]


def _stray(pitch: int, hits: Sequence[Hit], kit: DrumKit) -> AnswerError:
    """The error for an answer to a pitch that has no note the kit leaves unmapped."""
    names = sorted({hit.articulation for hit in hits if hit.note.pitch == pitch})
    if names:
        why = f"{kit.label} already reads it, as {' and '.join(names)}"
    else:
        why = "the drum track has no note of this pitch"
    return AnswerError("unmapped", pitch, f"note {pitch}: {why}")


def _lowest(confidences: Iterable[Confidence]) -> Confidence:
    return min(confidences, key=_CONFIDENCE_ORDER.index)


def _count(count: int, noun: str, plural: str | None = None) -> str:
    return f"{count} {noun if count == 1 else plural or noun + 's'}"


def _unmapped_request(
    waiting: Mapping[int, Sequence[tuple[int, Note]]], kit: DrumKit, signatures: TimeSignatureMap
) -> DecisionRequest:
    total = sum(len(held) for held in waiting.values())
    listed = "; ".join(
        f"note {pitch}: {_count(len(held), 'note')} from bar "
        f"{signatures.bar_at(min(note.start for _, note in held)) + 1}"
        for pitch, held in sorted(waiting.items())
    )
    groups: list[JsonValue] = [
        {
            "pitch": pitch,
            "channels": [*sorted({note.channel for _, note in held})],
            "count": len(held),
            "positions": positions((note.start for _, note in held), signatures),
        }
        for pitch, held in sorted(waiting.items())
    ]
    have = "has" if total == 1 else "have"
    return DecisionRequest(
        kind="unmapped_notes",
        message=f"{_count(total, 'note')} on {_count(len(waiting), 'pitch', 'pitches')} {have} no "
        f"articulation in {kit.label}, so they can't be read ({listed}). What does each pitch "
        "play? Leaving them out, or reading the file with another map, also settles it.",
        answer_with=("unmapped", "from_map"),
        details={"kit": kit.ref, "notes": groups},
    )
