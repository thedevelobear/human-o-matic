"""The instrument seam: `drums` and `generic` both render through it (ADR 0045)."""

import numpy as np

from grooves import BAR, GM, SIXTEENTH, SNARE, TOM_1, TOM_2, Hit, normalized, plan_for, rock, song
from human_o_matic.controls import ControlVector
from human_o_matic.instruments.base import Instrument
from human_o_matic.instruments.drums import DRUMS
from human_o_matic.instruments.generic import GENERIC
from human_o_matic.midi.io import MidiSong, midi_bytes
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import Rendered, render
from human_o_matic.render.style import STYLES
from human_o_matic.render.target import place_score


def with_fills(bars: int) -> MidiSong:
    fill = ((4, SNARE), (3, TOM_1), (2, TOM_2), (1, TOM_2))
    hits: list[Hit] = []
    for bar in range(bars):
        hits.extend(rock(1, start=bar))
        hits.extend(((bar + 1) * BAR - step * SIXTEENTH, pitch) for step, pitch in fill)
    return song(hits)


def rendered_by(
    instrument: Instrument, midi: MidiSong, result: Normalized, controls: ControlVector
) -> Rendered:
    placement = place_score(result.score, GM, GM)
    return render(
        midi, result, placement, plan_for(midi, result, controls=controls), instrument=instrument
    )


def test_both_instruments_meet_the_seam() -> None:
    instruments: list[Instrument] = [DRUMS, GENERIC]
    midi = with_fills(1)
    score = normalized(midi).score
    style = STYLES["tight"]

    for instrument in instruments:
        assert len(instrument.parts(score)) == len(score.notes)
        assert instrument.compile(style.defaults, style, 120.0).controls == style.defaults


def test_generic_mode_plays_every_note_with_no_role_and_feel_moves_them_all() -> None:
    midi = with_fills(8)
    result = normalized(midi)

    early = rendered_by(GENERIC, midi, result, ControlVector(feel=-1))
    late = rendered_by(GENERIC, midi, result, ControlVector(feel=1))

    assert {note.part.role for note in late.notes} == {"other"}
    for family in ("kick", "snare", "hat", "tom"):
        shift = [
            b.offset_ms - a.offset_ms
            for a, b in zip(early.notes, late.notes, strict=True)
            if a.family == family and not a.grace
        ]
        assert np.mean(shift) > 6


def test_fill_intensity_changes_nothing_in_generic_mode_and_the_fills_in_drums() -> None:
    midi = with_fills(8)
    result = normalized(midi)

    def written(instrument: Instrument, fill: float) -> bytes:
        controls = ControlVector(fill_intensity=fill)
        return midi_bytes(rendered_by(instrument, midi, result, controls).song)

    assert written(GENERIC, 0.0) == written(GENERIC, 1.0)
    assert written(DRUMS, 0.0) != written(DRUMS, 1.0)
