"""The guards on slots built by hand: each rule, and what each counts (ADRs 0050 and 0073)."""

from dataclasses import replace
from itertools import pairwise
from math import ceil

import numpy as np
import pytest

from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import IntArray, TempoMap
from human_o_matic.render.guards import Slot, Tally, hold_timing, hold_velocity

PPQ = 960
TEMPO = TempoMap.constant(PPQ, 120)
"""A tick is 0.52 ms."""
FAST, SLOW = 100_000, 1_000_000
"""600 and 60 BPM in microseconds per quarter note, where a tick is 0.10 ms and 1.04 ms."""
CAP_MS = 12.0
ROUNDING_MS = 1e-6
"""Float rounding in the conversions between ticks and milliseconds."""


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


def flam_at_tick_0(*played: int) -> list[Slot]:
    """Graces played at the first ticks given and their main at the last, all read on tick 0,
    as the score has them: a grace can't go before tick 0."""
    *graces, main = (slot(0, start=start, order=order) for order, start in enumerate(played))
    return [*(replace(grace, main=len(graces)) for grace in graces), main]


def test_a_flam_on_tick_0_starts_there_and_keeps_the_gap_it_was_played_at() -> None:
    # 20 ticks are 10.4 ms, inside the cap. The main is drawn early, so the grace would start
    # before tick 0, and the main goes later with it.
    tally = Tally()

    early = hold_timing(flam_at_tick_0(0, 20), np.array([0.0, -5.0]), TEMPO, tally)
    late = hold_timing(flam_at_tick_0(0, 20), np.array([0.0, 11.0]), TEMPO, Tally())

    assert list(early.starts) == [0, 20]
    assert early.ends[0] <= early.starts[1]
    assert late.starts[1] - late.starts[0] == 20
    assert late.starts[0] > 0
    counts = tally.frozen()
    assert (counts.tick_zero, counts.unmet) == (2, 0)


def test_the_cap_wins_over_a_flam_s_gap_on_tick_0_and_its_notes_keep_their_order() -> None:
    # 30 ticks are 15.6 ms, so the main stops at the cap, 23 ticks, with its grace on tick 0.
    # In the drag, both graces would start before tick 0 at the cap: they keep their order.
    flam, drag = Tally(), Tally()

    one = hold_timing(flam_at_tick_0(0, 30), np.array([0.0, 0.0]), TEMPO, flam)
    two = hold_timing(flam_at_tick_0(0, 10, 50), np.array([0.0, 0.0, 0.0]), TEMPO, drag)

    assert list(one.starts) == [0, 23]
    assert list(two.starts) == [0, 1, 23]
    assert (flam.frozen().unmet, drag.frozen().unmet) == (1, 1)
    assert (flam.frozen().tick_zero, drag.frozen().tick_zero) == (1, 2)


def test_the_cap_wins_over_the_gap_after_a_kept_note_played_late() -> None:
    # The kept note is 70 ms late, so 0.6 of the 125 ms gap would take the next to +20 ms.
    slots = [slot(1000, section=0, kept=True, start=1134, order=1), slot(1240, section=1, order=2)]
    tally = Tally()

    timed = hold_timing(slots, np.array([0.0, 0.0]), TEMPO, tally)

    offset = TEMPO.tick_to_ms(int(timed.starts[1])) - TEMPO.tick_to_ms(1240)
    assert 11 < offset <= 12
    assert timed.starts[1] > 1134
    counts = tally.frozen()
    assert (counts.unmet, counts.gap) == (1, 0)


def test_the_cap_wins_over_the_gap_before_a_kept_note_played_early() -> None:
    slots = [slot(1000, section=0, order=1), slot(1240, section=1, kept=True, start=1106, order=2)]
    tally = Tally()

    timed = hold_timing(slots, np.array([0.0, 0.0]), TEMPO, tally)

    offset = TEMPO.tick_to_ms(int(timed.starts[0])) - TEMPO.tick_to_ms(1000)
    assert -12 <= offset < -11
    assert timed.starts[0] < 1106
    counts = tally.frozen()
    assert (counts.unmet, counts.gap) == (1, 0)


def held_to_the_cap_and_the_gap(slots: list[Slot], starts: IntArray, tempos: TempoMap) -> None:
    """Each note is within the cap, plus half a tick of the tempo where it lands for going to
    a tick, and keeps 0.6 of its grid gap from the note before it, both in milliseconds."""
    played = tempos.ticks_to_ms(starts)
    grid = tempos.ticks_to_ms(np.array([slot.tick for slot in slots], dtype=np.int64))
    for start, offset in zip(starts, played - grid, strict=True):
        tick = max(tempos.ms_per_tick(max(int(start) - 1, 0)), tempos.ms_per_tick(int(start)))
        assert abs(offset) <= CAP_MS + tick / 2 + ROUNDING_MS
    for earlier, later in pairwise(range(len(slots))):
        kept = played[later] - played[earlier]
        assert kept >= 0.6 * (grid[later] - grid[earlier]) - ROUNDING_MS


def test_the_gap_across_a_tempo_change_leaves_the_later_note_within_the_cap() -> None:
    # 600 BPM up to tick 180 and 60 after it. The first snare, 12 ms late, is on tick 115, and
    # its grid gap to the second is 81.25 ms. Counted in ticks, 0.6 of the 240 took the second
    # to tick 259, 19.8 ms late. Counted in milliseconds, 48.75, it stays where it was drawn,
    # 12 ms early, on its nearest tick.
    tempos = TempoMap(PPQ, [0, 180], [FAST, SLOW])
    slots = [slot(0, order=1), slot(240, order=2)]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, -12.0]), tempos, tally)

    assert list(timed.starts) == [115, 228]
    held_to_the_cap_and_the_gap(slots, timed.starts, tempos)
    counts = tally.frozen()
    assert (counts.gap, counts.unmet) == (0, 0)


@pytest.mark.parametrize(
    ("ticks", "tempos"),
    [
        pytest.param([0, 180], [FAST, SLOW], id="slower-between-the-notes"),
        pytest.param([0, 180], [SLOW, FAST], id="faster-between-the-notes"),
        pytest.param([0, 240], [FAST, SLOW], id="slower-on-a-grid-point"),
        pytest.param([0, 240], [SLOW, FAST], id="faster-on-a-grid-point"),
        pytest.param([0, 60], [FAST, SLOW], id="slower-before-the-first-is-played"),
        pytest.param([0, 60], [SLOW, FAST], id="faster-before-the-first-is-played"),
        pytest.param([0, 180, 230], [FAST, SLOW, FAST], id="slower-for-50-ticks"),
        pytest.param([0, 180, 230], [SLOW, FAST, SLOW], id="faster-for-50-ticks"),
    ],
)
def test_notes_keep_their_gap_in_milliseconds_and_the_cap_across_a_tempo_change(
    ticks: list[int], tempos: list[int]
) -> None:
    # Snares a 16th or a 32nd apart, drawn at the cap either way, around changes of 10 to 1:
    # the gap never takes a note past the cap, and no note is short of its gap.
    tempo_map = TempoMap(PPQ, ticks, tempos)
    drawn = [(12.0, -12.0), (12.0, 12.0), (-12.0, -12.0), (12.0, -12.0, -12.0), (12.0, 12.0, -12.0)]
    for step in (240, 120):
        for offsets in drawn:
            slots = [slot(number * step, order=number + 1) for number in range(len(offsets))]
            tally = Tally()

            timed = hold_timing(slots, np.array(offsets), tempo_map, tally)

            held_to_the_cap_and_the_gap(slots, timed.starts, tempo_map)
            assert tally.frozen().unmet == 0


def test_a_main_note_across_a_tempo_change_moves_with_its_grace_in_milliseconds() -> None:
    # 600 BPM up to tick 1600 and 60 after it. The grace on tick 1440 keeps its gap from the
    # snare before it by moving about 14 ms later. Moved by the same 134 ticks, its main on tick
    # 1680 would go 127 ms late. Moved by the same milliseconds, it keeps the grace's offset, to
    # within the tick each went to.
    tempos = TempoMap(PPQ, [0, 1600], [FAST, SLOW])
    slots = [slot(1200, order=1), replace(slot(1440, order=2), main=2), slot(1680, order=3)]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, -12.0, -12.0]), tempos, tally)

    held_to_the_cap_and_the_gap(slots, timed.starts, tempos)
    grid = tempos.ticks_to_ms(np.array([1440, 1680]))
    grace, main = tempos.ticks_to_ms(timed.starts[1:]) - grid
    assert grace > 0
    assert abs(grace - main) <= tempos.ms_per_tick(1680)
    counts = tally.frozen()
    assert (counts.gap, counts.unmet) == (1, 0)


def test_a_unit_s_shift_is_counted_in_the_shortest_tick_of_its_notes() -> None:
    # 600 BPM up to tick 1600 and 60 after it. The grace shares its grid point with the snare
    # before it, 12 ms late, so it keeps a tick after it, 0.10 ms, and its main hardly moves.
    # Counted in its main's ticks, past the change, the shift would be 1.04 ms, and take the
    # grace and its main 1 ms and 1.5 ms past the cap.
    tempos = TempoMap(PPQ, [0, 1600], [FAST, SLOW])
    slots = [slot(1440, order=1), replace(slot(1440, order=2), main=2), slot(1680, order=3)]
    tally = Tally()

    timed = hold_timing(slots, np.array([12.0, 12.0, 12.0]), tempos, tally)

    assert list(timed.starts) == [1555, 1556, 1692]
    _, grace, main = tempos.ticks_to_ms(timed.starts) - tempos.ticks_to_ms([1440, 1440, 1680])
    assert grace <= CAP_MS + tempos.ms_per_tick(1556)
    assert main <= CAP_MS + tempos.ms_per_tick(1692) / 2
    counts = tally.frozen()
    assert (counts.gap, counts.unmet) == (1, 0)
