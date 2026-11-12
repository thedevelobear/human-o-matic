"""A note belongs to the beat its tick is in, whether it was played on its grid point, just before
it, or after it, so a backbeat is a backbeat and a downbeat renders with its own section
(ADR 0086)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from grooves import BAR, KICK, PPQ, Hit, normalized, plan_for, rendered, rock, song
from human_o_matic.controls import ControlVector
from human_o_matic.instruments.drums import DRUMS
from human_o_matic.normalize.score import Score


def _in_their_beats(score: Score) -> bool:
    return all(
        score.beats[note.beat].start <= note.tick < score.beats[note.beat].end
        for note in score.notes
        if note.grace_of is None
    )


@pytest.mark.parametrize("bpm", [90.0, 110.0, 120.0, 173.0])
def test_notes_on_the_grid_belong_to_the_beat_they_start(bpm: float) -> None:
    score = normalized(song(rock(64), bpm=bpm)).score
    parts = DRUMS.parts(score)

    on_beats = [note for note in score.notes if note.tick % PPQ == 0]
    snares = [part for note, part in zip(score.notes, parts, strict=True) if note.family == "snare"]

    assert all(score.beats[note.beat].start == note.tick for note in on_beats)
    assert _in_their_beats(score)
    assert len(snares) == 128
    assert all(part.role == "backbeat" for part in snares)


@given(
    st.floats(60, 240),
    st.lists(st.integers(-12, 12), min_size=96, max_size=96),
)
def test_notes_played_early_or_late_belong_to_the_beat_of_their_tick(
    bpm: float, offsets_ms: list[int]
) -> None:
    ms_per_tick = 60_000 / (bpm * PPQ)
    hits: list[Hit] = [
        (max(tick + round(offset / ms_per_tick), 0), pitch)
        for (tick, pitch, *_), offset in zip(rock(8), offsets_ms, strict=True)
    ]

    score = normalized(song(hits, bpm=bpm)).score

    assert _in_their_beats(score)
    assert all(
        score.beats[note.beat].bar == score.signatures.bar_at(note.tick)
        for note in score.notes
        if note.grace_of is None
    )


def test_a_downbeat_played_early_takes_its_own_section_s_controls() -> None:
    early = round(3 / (60_000 / (120 * PPQ)))
    """3 ms before the bar line, in ticks at 120 BPM."""
    # The kick on bar 4's downbeat is played early, and the hat with it on time.
    hits: list[Hit] = [*rock(4), (4 * BAR - early, KICK), *rock(4, start=4)[1:]]
    midi = song(hits)
    result = normalized(midi)
    plan = plan_for(
        midi,
        result,
        cuts=[4],
        sections={0: ControlVector(energy=0.0), 1: ControlVector(energy=1.0)},
    )

    notes = rendered(midi, plan, result=result).notes

    (position,) = [
        position
        for position, note in enumerate(result.score.notes)
        if note.source.start == 4 * BAR - early
    ]
    (downbeat,) = [note for note in notes if note.position == position]
    before = [note.note.velocity for note in notes if note.section == 0 and note.note.pitch == KICK]
    assert result.score.notes[position].tick == 4 * BAR
    assert downbeat.section == 1
    assert downbeat.note.velocity > max(before)
