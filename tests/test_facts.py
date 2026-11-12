"""Each section's facts, its ASCII pattern, the guess and the suggested questions, on songs built
in code and read through the General MIDI map."""

from collections.abc import Sequence

import pytest

from grooves import (
    ACCENT,
    BAR,
    CHINA,
    CRASH,
    GM,
    HAT,
    KICK,
    PEDAL,
    PPQ,
    SIXTEENTH,
    SNARE,
    SOFT,
    TOM_1,
    TOM_2,
    Hit,
    normalized,
    rock,
    song,
)
from human_o_matic.analyze.facts import SectionFacts, draw_bar, heard_bars, label, song_facts
from human_o_matic.analyze.sections import Section, drum_bars
from human_o_matic.instruments.drums import DRUMS
from human_o_matic.normalize.pipeline import normalize


def facts(
    hits: Sequence[Hit],
    spans: Sequence[tuple[int, int, str]],
    *,
    tempos: Sequence[tuple[int, float]] = (),
    signatures: Sequence[tuple[int, int, int]] = (),
) -> tuple[SectionFacts, ...]:
    """The facts of the song's sections, each `(start, bars, group)`."""
    midi = song(hits, tempos=tempos, signatures=signatures)
    result = normalized(midi)
    score = result.score
    sections = [Section(start=start, bars=bars, group=group) for start, bars, group in spans]
    return song_facts(score, DRUMS.parts(score), sections, drum_bars(midi, score))


def one(
    hits: Sequence[Hit], bars: int, *, signatures: Sequence[tuple[int, int, int]] = ()
) -> SectionFacts:
    (found,) = facts(hits, [(0, bars, "A")], signatures=signatures)
    return found


def test_labels_count_bars_from_1() -> None:
    assert label(8, 16) == "bars 9 to 24"
    assert label(3, 1) == "bar 4"


def test_a_rock_bar_is_drawn_from_the_cymbals_down_to_the_kick() -> None:
    found = one(rock(4), 4)

    assert found.pattern is not None
    assert found.pattern.per_beat == 4
    assert found.pattern.lines == (
        "hat   x.x. x.x. x.x. x.x.",
        "snare .... x... .... x...",
        "kick  x... .... x... ....",
    )
    assert found.ends is None


def test_accents_and_soft_notes_have_their_own_symbols_and_the_pedal_its_row() -> None:
    hits: list[Hit] = [
        (0, KICK, ACCENT),
        (PPQ, SNARE),
        (PPQ + 3 * SIXTEENTH, SNARE, SOFT),
        (0, CRASH, ACCENT),
        *((beat * PPQ, PEDAL) for beat in range(4)),
    ]

    pattern = one(hits, 1).pattern

    assert pattern is not None
    assert pattern.lines == (
        "crash X... .... .... ....",
        "pedal x... x... x... x...",
        "snare .... x..o .... ....",
        "kick  X... .... .... ....",
    )


def test_a_triplet_bar_takes_the_triplet_grid() -> None:
    shuffle: list[Hit] = [
        *((beat * PPQ + step * PPQ // 3, HAT) for beat in range(4) for step in (0, 2)),
        (0, KICK),
        (PPQ, SNARE),
    ]

    pattern = one(shuffle, 1).pattern

    assert pattern is not None
    assert pattern.per_beat == 3
    assert pattern.lines[0] == "hat   x.x x.x x.x x.x"


def test_a_bar_of_7_8_has_eighth_note_beats() -> None:
    hits: list[Hit] = [(0, KICK), (2 * PPQ // 2, SNARE), (5 * PPQ // 2, KICK)]

    pattern = one(hits, 1, signatures=[(0, 7, 8)]).pattern

    assert pattern is not None
    assert pattern.per_beat == 2
    assert pattern.lines == ("snare .. .. x. .. .. .. ..", "kick  x. .. .. .. .. x. ..")


def test_what_keeps_time_the_backbeat_and_the_double_kick_are_counted() -> None:
    crash_ride: list[Hit] = []
    for bar in range(4):
        at = bar * BAR
        crash_ride.extend((at + beat * PPQ, CRASH) for beat in range(4))
        crash_ride.extend([(at, KICK), (at + 2 * PPQ, SNARE)])
    blast: list[Hit] = []
    for bar in range(4):
        at = bar * BAR
        blast.extend((at + beat * PPQ, CHINA) for beat in range(4))
        blast.extend((at + step * SIXTEENTH, KICK) for step in range(16))
        blast.extend([(at + PPQ, SNARE), (at + 3 * PPQ, SNARE)])

    ride = one(crash_ride, 4)
    china = one(blast, 4)
    hats = one(rock(4), 4)

    assert (ride.riding, ride.half_time) == ("crash", True)
    assert ride.plays.startswith("crash riding, half-time")
    assert (china.riding, china.half_time, china.double_kick) == ("china", False, 64)
    assert china.plays.startswith("china riding, double kick")
    assert (hats.riding, hats.half_time, hats.double_kick) == ("hat", False, 0)
    assert hats.plays == "hats"
    assert hats.families["hat"].per_bar == 8.0
    assert hats.families["kick"].notes == 8


def test_soft_notes_fills_rests_and_unclear_bars_are_counted_in_their_bars() -> None:
    hits: list[Hit] = [
        *rock(3),
        (PPQ + 3 * SIXTEENTH, SNARE, SOFT),
        *(
            (3 * BAR + 3 * PPQ + step * SIXTEENTH, TOM_1 if step < 2 else TOM_2)
            for step in range(4)
        ),
        (5 * BAR, KICK),
        (5 * BAR + PPQ + 340, SNARE),
    ]

    found = one(hits, 6)

    assert found.hit_types.soft == 1
    assert found.families["snare"].soft == 1
    assert found.fill_bars == (3,)
    assert found.empty_bars == (4,)
    assert found.ambiguous_bars == (5,)
    assert "1 soft snare note" in found.plays
    assert "a fill in bar 4" in found.plays
    assert "1 bar of rest" in found.plays
    assert "an unclear grid in bar 6" in found.plays


def test_a_last_bar_that_plays_differently_is_drawn_too() -> None:
    fill: list[Hit] = [
        *rock(3),
        *((3 * BAR + step * SIXTEENTH, TOM_1) for step in range(16)),
    ]

    found = one(fill, 4)

    assert found.pattern is not None
    assert found.pattern.bar in (0, 1, 2)
    assert found.ends is not None
    assert found.ends.bar == 3
    assert found.ends.lines == ("tom xxxx xxxx xxxx xxxx",)


def test_a_grace_is_heard_in_its_main_s_bar_and_left_out_of_the_pattern() -> None:
    hits: list[Hit] = [*rock(2), (BAR - 30, SNARE, SOFT), (BAR, SNARE)]
    midi = song(hits)
    score = normalized(midi).score

    bars = heard_bars(score)
    (grace,) = [position for position, note in enumerate(score.notes) if note.grace_of is not None]

    assert score.notes[grace].tick < BAR
    assert bars[grace] == 1
    assert draw_bar(score, 1).lines[1] == "snare x... x... .... x..."


def test_the_meter_and_tempo_of_each_section_are_given() -> None:
    hits = rock(4)

    first, second = facts(
        hits, [(0, 2, "A"), (2, 2, "B")], tempos=[(2 * BAR + PPQ, 140.0), (3 * BAR, 150.0)]
    )

    assert (first.meter, first.bpm) == (("4/4",), (120.0, 120.0))
    assert second.bpm == (120.0, 150.0)


def test_silent_repeat_fill_and_groove_are_guessed_with_how_sure() -> None:
    verse = rock(4)
    chorus: list[Hit] = []
    for bar in range(4, 8):
        at = bar * BAR
        chorus.extend((at + beat * PPQ, CRASH) for beat in range(4))
        chorus.extend([(at, KICK), (at + 2 * PPQ, SNARE)])
    fill = [(12 * BAR + step * SIXTEENTH, TOM_1 if step % 2 else SNARE) for step in range(32)]
    hits = [*verse, *chorus, *rock(4, start=8), *fill, (14 * BAR, KICK)]

    found = facts(
        hits,
        [(0, 4, "A"), (4, 4, "B"), (8, 4, "A"), (12, 2, "C"), (14, 1, "D")],
    )
    first, second, repeat, fills, last = found

    assert (first.guess.kind, first.guess.confidence) == ("groove", "low")
    assert first.questions[0] == "What's the energy in bars 1 to 4 (hats)?"
    assert first.questions[1] == "Steady and even, or more groove, with more light and shade?"
    assert second.guess.kind == "groove"
    assert (repeat.guess.kind, repeat.guess.confidence, repeat.guess.like) == ("repeat", "high", 0)
    assert repeat.questions == (
        "Bars 9 to 12 play like bars 1 to 4: the same, or bigger, as the last time?",
    )
    assert (fills.guess.kind, fills.guess.confidence) == ("fill", "medium")
    assert fills.questions == ("How hard should the fill in bars 13 to 14 hit?",)
    assert last.guess.kind == "groove"
    assert all(
        "energy" not in fact.guess.says or "isn't readable" in fact.guess.says for fact in found
    )


def test_a_section_with_no_hits_is_silent_and_asks_nothing() -> None:
    hits = [*rock(2), *rock(2, start=6)]

    silent = facts(hits, [(0, 2, "A"), (2, 4, "B"), (6, 2, "A")])[1]

    assert silent.notes == 0
    assert (silent.plays, silent.guess.kind, silent.guess.confidence) == (
        "silent",
        "silent",
        "high",
    )
    assert silent.questions == ()
    assert silent.pattern is None
    assert silent.empty_bars == (2, 3, 4, 5)


def test_a_repeat_that_isn_t_its_group_s_last_asks_nothing() -> None:
    hits = rock(12)

    _, middle, last = facts(hits, [(0, 4, "A"), (4, 4, "A"), (8, 4, "A")])

    assert middle.guess.kind == last.guess.kind == "repeat"
    assert middle.questions == ()
    assert len(last.questions) == 1


@pytest.mark.parametrize("bars", [1, 4])
def test_the_facts_add_up_to_the_score(bars: int) -> None:
    hits = rock(8)
    midi = song(hits)
    score = normalize(midi, GM).score
    spans = [(start, bars, "A") for start in range(0, 8, bars)]

    found = facts(hits, spans)

    assert sum(fact.notes for fact in found) == len(score.notes)
    assert all(fact.per_bar == fact.notes / fact.bars for fact in found)
