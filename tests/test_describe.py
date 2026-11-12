"""How a rendered section came out, by role, in numbers and in words."""

from grooves import (
    BAR,
    CRASH,
    PPQ,
    SIXTEENTH,
    SNARE,
    SOFT,
    normalized,
    plan_for,
    rendered,
    rock,
    song,
)
from human_o_matic.controls import ControlVector
from human_o_matic.render.describe import sound


def sections_of(energy: float, *, skip: bool = False) -> list[str]:
    hits = [
        *rock(8),
        (0, CRASH),
        *((bar * BAR + PPQ + 3 * SIXTEENTH, SNARE, SOFT) for bar in range(8)),
    ]
    midi = song(hits)
    result = normalized(midi)
    plan = plan_for(
        midi,
        result,
        cuts=[4],
        sections={1: ControlVector(skip=skip)},
        controls=ControlVector(energy=energy),
    )
    notes = rendered(midi, plan, result=result).notes
    return [sound([note for note in notes if note.section == number]).says for number in (0, 1)]


def test_a_section_is_described_by_role_with_its_timing() -> None:
    says, _ = sections_of(0.8)

    assert says.startswith("kick about ")
    for words in ("backbeats about", "hat about", "strong hits", "crash accents about"):
        assert words in says
    assert "soft notes about" in says
    assert "timing spread about" in says


def test_the_ranges_rise_with_energy() -> None:
    hits = rock(8)
    midi = song(hits)
    result = normalized(midi)

    def kick(energy: float) -> tuple[int, int]:
        plan = plan_for(midi, result, controls=ControlVector(energy=energy))
        span = sound(rendered(midi, plan, result=result).notes).velocities["kick"]
        return span.low, span.high

    low, high = kick(0.2), kick(1.0)

    assert low[0] < high[0]
    assert low[1] < high[1]


def test_a_section_played_as_it_came_in_or_without_notes_says_so() -> None:
    _, skipped = sections_of(0.5, skip=True)

    assert skipped == "played as it came in"
    assert sound([]).says == "no notes"
    assert sound([]).velocities == {}


def test_a_few_notes_span_their_lowest_to_highest() -> None:
    midi = song([(0, CRASH), (PPQ, SNARE), (2 * PPQ, SNARE)])
    result = normalized(midi)
    notes = rendered(midi, plan_for(midi, result), result=result).notes

    found = sound(notes)
    snares = sorted(note.note.velocity for note in notes if note.family == "snare")

    assert (found.velocities["backbeats"].low, found.velocities["backbeats"].high) == (
        snares[0],
        snares[-1],
    )
    assert found.velocities["backbeats"].notes == 2
