"""The guards on slots built by hand: each rule, and what each counts (ADR 0050)."""

from dataclasses import replace
from math import ceil

import numpy as np

from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import TempoMap
from human_o_matic.render.guards import Slot, Tally, hold_timing, hold_velocity

PPQ = 960
TEMPO = TempoMap.constant(PPQ, 120)
"""A tick is 0.52 ms."""


def slot(
    tick: int,
    *,
    section: int = 0,
    kept: bool = False,
    start: int | None = None,
    length: int = 10,
    order: int = 0,
    window: tuple[int, int] | None = None,
) -> Slot:
    """A note on the snare at its grid point `tick`, played at `start`."""
    played = tick if start is None else start
    return Slot(
        section=section,
        kept=kept,
        source=Note(
            track=0,
            channel=9,
            pitch=38,
            start=played,
            end=played + length,
            velocity=100,
            order=order,
            off_order=order,
        ),
        tick=tick,
        main=None,
        channel=9,
        pitch=38,
        drum=("snare", 1),
        soft=False,
        velocity=(1, 127),
        order=order,
        off_order=order,
        window=window,
    )


def test_a_note_before_a_kept_one_moves_earlier_to_keep_its_gap_and_counts_it() -> None:
    slots = [slot(1000, order=1), slot(1100, section=1, kept=True, start=1070, order=2)]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, 0.0]), TEMPO, tally)

    assert timed.starts[0] <= 1070 - 60
    assert timed.starts[1] == 1070
    assert tally.frozen().gap == 1
    assert tally.frozen().unmet == 0


def test_a_note_after_another_moves_later_to_keep_its_gap() -> None:
    slots = [slot(1000, order=1), slot(1100, order=2)]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, -12.0]), TEMPO, tally)

    assert timed.starts[1] - timed.starts[0] >= 60
    assert tally.frozen().gap == 1


def test_offsets_past_the_cap_are_cut_to_it() -> None:
    tally = Tally()

    timed = hold_timing([slot(2000, order=1)], np.array([40.0]), TEMPO, tally)

    assert abs(TEMPO.tick_to_ms(int(timed.starts[0])) - TEMPO.tick_to_ms(2000) - 12) < 0.6
    assert tally.frozen().capped == 1


def test_across_a_boundary_each_note_keeps_to_its_side_of_the_gap() -> None:
    slots = [slot(1000, order=1), slot(1100, section=1, order=2)]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, -12.0]), TEMPO, tally)

    assert timed.starts[0] <= 1000 + 20 + 1
    assert timed.starts[1] >= 1100 - 20 - 1
    assert tally.frozen().gap == 0


def test_a_note_ends_by_the_next_one_s_start_with_the_lower_order() -> None:
    slots = [slot(1000, length=500, order=1), slot(1240, order=2)]

    timed = hold_timing(slots, np.array([0.0, 0.0]), TEMPO, Tally())

    assert timed.ends[0] == timed.starts[1] == 1240
    assert timed.off_orders[0] == 1


def test_a_note_ends_where_the_next_section_s_note_could_start_whatever_it_draws() -> None:
    slots = [slot(1000, length=500, order=1), slot(1240, section=1, order=2)]

    early = hold_timing(slots, np.array([0.0, -12.0]), TEMPO, Tally())
    late = hold_timing(slots, np.array([0.0, 12.0]), TEMPO, Tally())

    assert early.ends[0] == late.ends[0] <= early.starts[1] < late.starts[1]
    assert early.ends[0] < 1240


def test_the_controller_window_wins_over_the_gap_and_says_so() -> None:
    slots = [slot(1000, order=1), slot(1050, order=2, window=(0, 1052))]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, 0.0]), TEMPO, tally)

    assert timed.starts[1] == 1052
    counts = tally.frozen()
    assert (counts.controller, counts.unmet, counts.gap) == (1, 1, 0)


def test_when_both_gaps_can_t_be_kept_the_one_from_the_note_before_wins() -> None:
    slots = [
        slot(1000, order=1),
        slot(1040, order=2),
        slot(1080, section=1, kept=True, start=1070, order=3),
    ]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, 0.0, 0.0]), TEMPO, tally)

    assert timed.starts[1] - timed.starts[0] == ceil(0.6 * 40)
    assert timed.starts[2] - timed.starts[1] < ceil(0.6 * 40)
    counts = tally.frozen()
    assert (counts.gap, counts.unmet) == (1, 1)


def test_a_note_inside_its_controller_window_stays_and_one_before_it_moves_to_its_start() -> None:
    tally = Tally()

    inside = hold_timing([slot(1050, window=(1000, 1100))], np.array([0.0]), TEMPO, tally)
    before = hold_timing([slot(1050, window=(1060, 1500))], np.array([0.0]), TEMPO, tally)

    assert inside.starts[0] == 1050
    assert before.starts[0] == 1060
    assert tally.frozen().controller == 1


def test_a_note_is_held_no_lower_than_1_below_the_lowest_where_its_drum_has_soft_notes() -> None:
    # A soft snare, then a snare at the lowest normal velocity, a sidestick, and a snare that
    # can't repeat the snare or the sidestick before it, nor the kept snare after it. Below 59
    # it would meet the soft note at 58, so it repeats instead, and says so.
    def velocity_slot(pitch: int, order: int, soft: bool = False, high: int = 127) -> Slot:
        return replace(slot(1000, order=order), pitch=pitch, soft=soft, velocity=(1, high))

    kept = slot(1100, section=1, kept=True, order=5)
    slots = [
        velocity_slot(38, 1, soft=True),
        velocity_slot(38, 2, high=61),
        velocity_slot(37, 3),
        velocity_slot(38, 4, high=61),
        replace(kept, source=replace(kept.source, velocity=59)),
    ]
    tally = Tally()

    out = hold_velocity(slots, np.array([70.0, 60.0, 61.0, 60.0, 0.0]), np.ones(5), tally)

    assert list(out) == [58, 60, 61, 60, 59]
    assert tally.frozen().unmet == 1
