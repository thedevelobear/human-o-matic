"""Normalizing a song's drums: read through a kit, quantized per beat, typed by velocity.

The steps are the read (`read.read_drums`), the quantizer (`quantize.quantize`, with
`grid.snap`) and the hit types (`hit_types.type_hits`). What can't go on without the user, a
missing tempo or an unclear drum track, raises `DecisionRequired`. What only wants confirming
is returned with the score as decision requests: unmapped notes, ambiguous bars and the hit
types. Each is answered by calling again with the argument it names, and the same song, kit and
answers always give the same score.
"""

from collections.abc import Mapping

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.kit import DrumKit
from human_o_matic.midi.io import MidiSong
from human_o_matic.midi.tempo import tempo_map, time_signature_map
from human_o_matic.midi.tracks import choose_drum_track
from human_o_matic.normalize.grid import Grid, ambiguous_request
from human_o_matic.normalize.hit_types import HitTypeBounds, hit_types_request, type_hits
from human_o_matic.normalize.quantize import quantize
from human_o_matic.normalize.read import read_drums
from human_o_matic.normalize.score import Normalized, Score, ScoreNote


def normalize(
    song: MidiSong,
    kit: DrumKit,
    *,
    track: int | None = None,
    bpm: float | None = None,
    unmapped: Mapping[int, str] | None = None,
    grids: Mapping[tuple[int, int], Grid] | None = None,
    hit_types: Mapping[str, HitTypeBounds] | None = None,
) -> Normalized:
    """The song's drum part as a score, read with `kit`.

    `track` and `bpm` answer the `drum_track` and `tempo` requests. `unmapped` answers
    `unmapped_notes`: from a pitch to an articulation of the kit, or `DROP`. `grids` answers
    `ambiguous_bars`: the grid of a beat, by its bar and place in the bar, both from 0.
    `hit_types` answers `hit_types`: velocity bounds for a family. Raises `DecisionRequired`
    when the tempo or the drum track is unclear, and `AnswerError` for an answer that names a
    pitch with no unmapped note, a beat without notes or a family without notes, or that the kit
    or the beat can't take.
    """
    tempos = tempo_map(song, bpm=bpm)
    drums = choose_drum_track(song, track).track
    signatures = time_signature_map(song)
    reading = read_drums(song, drums, kit, signatures, unmapped=unmapped)
    hits = reading.hits
    placed = quantize(hits, tempos, signatures, grids)
    typed = type_hits([hit.family for hit in hits], [hit.note.velocity for hit in hits], hit_types)

    notes = [
        ScoreNote(
            source=hit.note,
            source_index=hit.index,
            articulation=hit.articulation,
            family=hit.family,
            piece=hit.piece,
            tick=int(placed.ticks[position]),
            offset_ms=float(placed.offsets_ms[position]),
            beat=int(placed.beat_of[position]),
            grid=placed.beats[int(placed.beat_of[position])].grid,
            grace_of=hits[main].index if (main := placed.grace_of[position]) is not None else None,
            hit_type=typed.types[position],
            hit_type_confidence=typed.confidences[position],
        )
        for position, hit in enumerate(hits)
    ]
    notes.sort(key=lambda note: (note.tick, note.source_index))
    score = Score(
        ppq=song.ppq,
        track=drums,
        kit=kit.ref,
        notes=tuple(notes),
        beats=placed.beats,
        hit_types=typed.families,
        tempos=tempos,
        signatures=signatures,
    )
    asked = (ambiguous_request(placed.beats), hit_types_request(typed.families))
    decisions: list[DecisionRequest] = [*reading.decisions]
    decisions.extend(request for request in asked if request is not None)
    return Normalized(
        score=score,
        pending=reading.unmapped,
        dropped=reading.dropped,
        low_confidence=reading.low_confidence,
        decisions=tuple(decisions),
    )
