"""Sections found in songs built in code from a few grooves, read through the General MIDI map."""

from itertools import combinations, pairwise

import mido
import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.analyze.sections import (
    BOUNDARY_COST,
    LENGTH_COST,
    MIN_BARS,
    PHRASES,
    bar_patterns,
    choose_boundaries,
    drum_bars,
    find_sections,
    group_name,
    novelty,
    similarity,
)
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiSong, parse_midi
from human_o_matic.normalize.pipeline import normalize
from human_o_matic.normalize.score import Score
from midi_files import MidoMessage, build, end, name, off, on, signature, tempo, track

GM = find_kit("gm")
PPQ = 960
STEP = PPQ // 4
"""A 16th note."""
KICK, SNARE, HAT, RIDE, CRASH, CHINA, TOM = 36, 38, 42, 51, 49, 52, 45

type Groove = tuple[tuple[int, int], ...]
"""One bar of 4/4 as (16th step, pitch) hits."""

ROCK: Groove = (
    *((step, KICK) for step in (0, 8)),
    *((step, SNARE) for step in (4, 12)),
    *((step, HAT) for step in range(0, 16, 2)),
)
HALF: Groove = ((0, KICK), (10, KICK), (8, SNARE), *((step, RIDE) for step in range(0, 16, 4)))
BLAST: Groove = (
    *((step, KICK) for step in range(16)),
    *((step, SNARE) for step in range(2, 16, 4)),
    *((step, CHINA) for step in range(0, 16, 4)),
)
TOMS: Groove = ((0, CRASH), *((step, TOM) for step in range(0, 16, 2)))
GROOVES = (ROCK, HALF, BLAST, TOMS)
EMPTY: Groove = ()
STOP: Groove = ((0, KICK), (0, CRASH))
"""Hits only in the first half of the bar."""
LEAD_IN: Groove = ((12, SNARE), (13, SNARE), (14, TOM), (15, TOM))
"""Hits only in the second half of the bar."""


GRACE = round(PPQ * 30 / 500)
"""30 ms at 120 BPM, a grace's gap before its main (ADR 0027)."""


def song(
    *blocks: tuple[Groove, int] | tuple[Groove, int, int],
    markers: tuple[int, ...] = (),
    flams: bool = False,
) -> MidiSong:
    """A one-track song at 120 BPM, read back. Each block is `(groove, bars)` in 4/4, or
    `(groove, bars, sixteenths)` with that many 16ths to a bar, in 7/8 for 14. `markers` are
    ticks for SMF markers, and `flams` puts a grace before each snare."""
    items: list[tuple[int, int, MidoMessage]] = [(0, 0, name("Drums")), (0, 0, tempo(120))]
    items.extend((tick, 0, mido.MetaMessage("marker", text="Section")) for tick in markers)
    start, meter = 0, 0
    for block in blocks:
        groove, bars = block[0], block[1]
        sixteenths = block[2] if len(block) == 3 else 16
        if sixteenths != meter:
            items.append((start, 0, signature(*meter_of(sixteenths))))
            meter = sixteenths
        for number in range(bars):
            for step, pitch in groove:
                tick = start + (number * sixteenths + step) * STEP
                items.extend([(tick, 2, on(pitch)), (tick + 10, 1, off(pitch))])
                if flams and pitch == SNARE:
                    items.extend(
                        [(tick - GRACE, 2, on(SNARE, 40)), (tick - GRACE + 10, 1, off(SNARE))]
                    )
        start += bars * sixteenths * STEP
    items.sort(key=lambda item: (item[0], item[1]))
    messages = [(tick, message) for tick, _, message in items]
    return parse_midi(build(track(*messages, (messages[-1][0], end())), ppq=PPQ))


def meter_of(sixteenths: int) -> tuple[int, int]:
    """The time signature of a bar of that many 16ths: in quarters when it can be, else 8ths."""
    return (sixteenths // 4, 4) if sixteenths % 4 == 0 else (sixteenths // 2, 8)


def score_of(midi: MidiSong) -> Score:
    return normalize(midi, GM).score


def starts(midi: MidiSong, *, markers: bool = True) -> tuple[int, ...]:
    return find_sections(midi, score_of(midi), markers=markers).starts


def groups(midi: MidiSong) -> str:
    return "".join(section.group for section in find_sections(midi, score_of(midi)).sections)


def test_a_section_starts_where_the_groove_changes() -> None:
    midi = song((ROCK, 8), (HALF, 8), (ROCK, 8), (BLAST, 16))

    found = find_sections(midi, score_of(midi))

    assert found.source == "drums"
    assert found.starts == (0, 8, 16, 24)
    assert [section.bars for section in found.sections] == [8, 8, 8, 16]
    assert groups(midi) == "ABAC"


def test_one_groove_throughout_is_one_section() -> None:
    assert starts(song((ROCK, 32))) == (0,)


def test_a_change_inside_a_phrase_is_kept_when_it_is_clear() -> None:
    assert starts(song((ROCK, 6), (TOMS, 10))) == (0, 6)


def test_a_long_silence_is_a_section_of_its_own() -> None:
    midi = song((ROCK, 8), (EMPTY, 4), (ROCK, 8))

    assert starts(midi) == (0, 8, 12)
    assert groups(midi) == "ABA"


def test_a_short_silence_ends_the_section_before_it() -> None:
    assert starts(song((ROCK, 8), (EMPTY, 2), (HALF, 8))) == (0, 10)
    midi = song((ROCK, 8), (EMPTY, 3), (ROCK, 8))
    assert starts(midi) == (0, 11)
    assert groups(midi) == "AA"


def test_a_stop_starts_a_silence_and_a_lead_in_ends_it() -> None:
    midi = song((ROCK, 8), (STOP, 1), (EMPTY, 6), (LEAD_IN, 1), (HALF, 8))

    assert starts(midi) == (0, 8, 16)


def test_an_opening_silence_is_a_section_once_it_is_long_enough_to_be_one() -> None:
    # No section comes before it to end, so from two bars the drums coming in start one.
    assert starts(song((EMPTY, 4), (ROCK, 8))) == (0, 4)
    assert starts(song((EMPTY, 2), (ROCK, 8))) == (0, 2)
    assert starts(song((EMPTY, 1), (ROCK, 8))) == (0,)


def test_markers_win_snapped_to_the_nearest_bar_line() -> None:
    bar = 4 * PPQ
    marked = (0, 4 * bar - 10, 12 * bar + bar // 2 - 1, 20 * bar + bar // 2, 40 * bar)
    midi = song((ROCK, 8), (HALF, 8), (ROCK, 8), markers=marked)

    found = find_sections(midi, score_of(midi))

    assert found.source == "markers"
    # Bar 0 and bars past the drums don't start a section, and halfway snaps to the later bar.
    assert found.starts == (0, 4, 12, 21)
    assert starts(midi, markers=False) == (0, 8, 16)


def test_markers_that_start_no_section_leave_it_to_the_drums() -> None:
    midi = song((ROCK, 8), (HALF, 8), markers=(0, 100 * 4 * PPQ))

    found = find_sections(midi, score_of(midi))

    assert found.source == "drums"
    assert found.starts == (0, 8)


def test_a_groove_in_another_meter_is_a_section_of_its_own() -> None:
    seven: Groove = ((0, KICK), (6, SNARE), (10, KICK), *((step, RIDE) for step in range(0, 14, 2)))
    midi = song((ROCK, 8), (seven, 8, 14), (ROCK, 8))

    assert drum_bars(midi, score_of(midi)) == 24
    assert starts(midi) == (0, 8, 16)
    assert groups(midi) == "ABA"


def test_bars_are_alike_by_the_families_they_share() -> None:
    midi = song((ROCK, 1), (HALF, 1), (EMPTY, 1), (ROCK, 1))
    score = score_of(midi)

    alike = similarity(bar_patterns(score, 4).patterns)

    assert np.allclose(alike, alike.T)
    assert np.allclose(np.diag(alike), 1.0)
    assert alike[0, 3] == pytest.approx(1.0)
    assert alike[0, 2] == alike[1, 2] == 0.0
    # They share the kick on the first beat, half of each bar's kick pattern, and nothing else.
    assert alike[0, 1] == pytest.approx(0.5 / 3)


def test_graces_are_left_out_of_the_patterns() -> None:
    plain, flams = score_of(song((ROCK, 4))), score_of(song((ROCK, 4), flams=True))

    assert any(note.grace_of is not None for note in flams.notes)
    assert np.array_equal(bar_patterns(plain, 4).patterns, bar_patterns(flams, 4).patterns)


def test_novelty_needs_a_whole_scale_on_both_sides() -> None:
    alike = similarity(bar_patterns(score_of(song((ROCK, 4), (HALF, 4))), 8).patterns)

    novel = novelty(alike)

    assert novel[0] == novel[1] == novel[7] == 0.0
    assert int(np.argmax(novel)) == 4


def test_group_names_run_from_a_to_z_then_on_in_two_letters() -> None:
    assert [group_name(index) for index in (0, 1, 25, 26, 27, 51, 52, 701, 702)] == [
        "A",
        "B",
        "Z",
        "AA",
        "AB",
        "AZ",
        "BA",
        "ZZ",
        "AAA",
    ]


@st.composite
def _blocks(draw: st.DrawFn) -> list[tuple[int, int]]:
    """Two to five blocks of (groove index, phrase length), no two neighbours alike."""
    count = draw(st.integers(2, 5))
    blocks: list[tuple[int, int]] = []
    for _ in range(count):
        choices = [index for index in range(len(GROOVES)) if not blocks or index != blocks[-1][0]]
        blocks.append((draw(st.sampled_from(choices)), draw(st.sampled_from(PHRASES))))
    return blocks


@given(_blocks())
def test_phrases_of_distinct_grooves_are_found_and_grouped(blocks: list[tuple[int, int]]) -> None:
    midi = song(*((GROOVES[groove], bars) for groove, bars in blocks))

    found = find_sections(midi, score_of(midi))

    expected = [0]
    for _, bars in blocks[:-1]:
        expected.append(expected[-1] + bars)
    assert found.starts == tuple(expected)
    first_seen: dict[int, str] = {}
    for groove, _ in blocks:
        first_seen.setdefault(groove, group_name(len(first_seen)))
    assert [section.group for section in found.sections] == [
        first_seen[groove] for groove, _ in blocks
    ]


@given(
    st.lists(
        st.tuples(st.integers(0, 40 * 16 - 1), st.sampled_from((KICK, SNARE, HAT, RIDE, TOM))),
        min_size=1,
        max_size=200,
    )
)
def test_sections_cover_the_bars_in_order_the_same_every_time(hits: list[tuple[int, int]]) -> None:
    groove: Groove = tuple(hits)
    midi = song((groove, 1))
    score = score_of(midi)

    found = find_sections(midi, score)

    assert found == find_sections(midi, score)
    assert found.starts[0] == 0
    assert all(first.end == second.start for first, second in pairwise(found.sections))
    assert found.sections[-1].end == drum_bars(midi, score)
    seen: list[str] = []
    for section in found.sections:
        if section.group not in seen:
            assert section.group == group_name(len(seen))
            seen.append(section.group)


@given(
    st.lists(st.floats(-1, 1), min_size=2, max_size=12),
    st.data(),
)
def test_the_boundaries_chosen_score_best(values: list[float], data: st.DataObject) -> None:
    bars = len(values)
    novel = np.array(values)
    candidates = data.draw(st.lists(st.integers(1, bars - 1), unique=True), label="candidates")
    kept = set(data.draw(st.lists(st.integers(1, bars - 1), unique=True, max_size=2), "kept"))

    chosen = choose_boundaries(novel, candidates, kept, bars)

    def value(boundaries: tuple[int, ...]) -> float | None:
        edges = (0, *boundaries, bars)
        lengths = [second - first for first, second in pairwise(edges)]
        fixed = kept | {0, bars}
        if any(
            length < MIN_BARS and not (first in fixed and second in fixed)
            for (first, second), length in zip(pairwise(edges), lengths, strict=True)
        ):
            return None
        gains = sum(float(novel[bar]) - BOUNDARY_COST for bar in boundaries if bar not in kept)
        return gains - LENGTH_COST * sum(length not in PHRASES for length in lengths)

    options = sorted(set(candidates) - kept)
    best = max(
        found
        for size in range(len(options) + 1)
        for extra in combinations(options, size)
        if (found := value(tuple(sorted(kept | set(extra))))) is not None
    )
    assert set(chosen) >= kept
    assert set(chosen) <= kept | set(candidates)
    assert value(chosen) == pytest.approx(best)
