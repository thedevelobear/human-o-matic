"""The score: a drum part as canonical hits on a grid, with hit types.

Every later stage reads the score instead of the MIDI notes, so it is library-neutral: each note
has a canonical articulation, never a pitch of a library. Its input velocity and timing are
kept only in its source note, which writes a `skip` section back exactly as it came in. The
score is frozen, like the song it was read from.
"""

from dataclasses import dataclass

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.schema import Confidence
from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import BarBeat, TempoMap, TimeSignatureMap
from human_o_matic.normalize.grid import BeatGrid, Grid
from human_o_matic.normalize.hit_types import FamilyHitTypes, HitType
from human_o_matic.normalize.read import LowConfidence


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreNote:
    """One hit of the score."""

    source: Note
    """The note as it came in, which writes it back unchanged."""
    source_index: int
    """The source note's position in `MidiSong.notes`, which identifies it."""
    articulation: str
    """A canonical name of the kit it was read with. When a controller value decides among
    several, they are joined by `|`, all in one family."""
    family: str
    piece: int
    tick: int
    """The quantized start: its grid point, or for a grace, its place before its main."""
    offset_ms: float
    """The performed start minus the quantized start, in milliseconds."""
    beat: int
    """Its beat, as a position in `Score.beats`. A grace has its main's."""
    grid: Grid
    """Its beat's grid."""
    grace_of: int | None
    """For a grace, the `source_index` of its main."""
    hit_type: HitType
    hit_type_confidence: Confidence
    """`high` when the type is read from clear groups or given in an answer, `low` when it is a
    guess."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Score:
    """A drum part, quantized, with hit types."""

    ppq: int
    track: int
    """The drum track in the song."""
    kit: str
    """The kit it was read with, as `library/kit`."""
    notes: tuple[ScoreNote, ...]
    """By tick, then by source order. Notes of one pitch and channel keep their source order."""
    beats: tuple[BeatGrid, ...]
    """The beats that have notes, in order, each with its grid."""
    hit_types: tuple[FamilyHitTypes, ...]
    """How each family's notes were typed, in the order the families first appear."""
    tempos: TempoMap
    signatures: TimeSignatureMap

    def position(self, tick: int) -> BarBeat:
        """The bar and beat of a tick, counted from 0."""
        return self.signatures.position(tick)

    def graces(self, main: ScoreNote) -> tuple[ScoreNote, ...]:
        """The graces of a main note, in order."""
        return tuple(note for note in self.notes if note.grace_of == main.source_index)

    @property
    def ambiguous(self) -> tuple[BeatGrid, ...]:
        """The beats whose grid is a guess."""
        return tuple(beat for beat in self.beats if beat.ambiguous)


@dataclass(frozen=True, slots=True, kw_only=True)
class Normalized:
    """The result of normalizing: the score, and what the user is asked about it."""

    score: Score
    pending: tuple[int, ...]
    """The positions in `MidiSong.notes` of drum notes the kit doesn't map, which wait for an
    `unmapped_notes` answer and are not in the score."""
    dropped: tuple[int, ...]
    """The positions of drum notes the user chose to leave out."""
    low_confidence: tuple[LowConfidence, ...]
    """How many notes were read through each `low` confidence articulation."""
    decisions: tuple[DecisionRequest, ...]
    """`unmapped_notes`, `ambiguous_bars` and `hit_types`, in that order, when they apply."""

    @property
    def complete(self) -> bool:
        """Whether every drum note is in the score or was left out by the user."""
        return not self.pending
