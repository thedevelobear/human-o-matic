"""Rendering a score: the plan's property tests, and examples of what the guards and the target
kit do (ADRs 0048 to 0050)."""

from collections.abc import Sequence
from functools import cache
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from grooves import (
    ACCENT,
    BAR,
    BELL,
    COWBELL,
    CRASH,
    GM,
    HAT,
    KICK,
    LENGTHS,
    NORMAL,
    OPEN_HAT,
    PEDAL,
    PPQ,
    RIDE,
    SIDESTICK,
    SIXTEENTH,
    SNARE,
    SOFT,
    TEMPOS,
    TOM_1,
    TOM_2,
    Hit,
    control_vectors,
    flams,
    grooves,
    normalized,
    plan_for,
    rendered,
    rock,
    song,
)
from human_o_matic.controls import ControlVector, SessionPlan, StyleName
from human_o_matic.maps.convert import DROP
from human_o_matic.midi.io import MidiSong, Note, midi_bytes, parse_midi
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import Rendered, RenderedNote, drift, render
from human_o_matic.render.measure import rider_gap
from human_o_matic.render.style import STYLE_NAMES
from human_o_matic.render.target import place_score
from map_files import articulation, load_kit
from midi_files import MidoMessage, build, cc, end, name, off, on, tempo, track

FLAM = round(PPQ * 30 / 500)
"""30 ms at 120 BPM: a grace's gap before its main."""
CUTS = st.lists(st.integers(1, 5), max_size=3)
STYLES = st.sampled_from(STYLE_NAMES)
"""Every property holds in every style."""
CAP_MS = 12.0
"""The plan's cap on an offset from the grid."""
GAP_SHARE = 0.6
"""The share of its grid gap the plan says a note keeps from the one before it on its pitch."""
ROUNDING_MS = 1e-6
"""Float rounding in the conversions between ticks and milliseconds."""


def by_key(notes: Sequence[RenderedNote], key: str) -> dict[object, list[RenderedNote]]:
    """The rendered notes of each output pitch (`"pitch"`) or drum (`"drum"`), in play order."""
    found: dict[object, list[RenderedNote]] = {}
    for note in notes:
        group = (
            (note.note.channel, note.note.pitch) if key == "pitch" else (note.family, note.piece)
        )
        found.setdefault(group, []).append(note)
    return found


def drum_notes(midi: MidiSong) -> list[Note]:
    return [note for note in midi.notes if note.track == 0]


@given(grooves(), CUTS, st.integers(0, 2**53 - 1), STYLES)
def test_the_same_song_plan_and_seed_give_the_same_bytes(
    hits: list[Hit], cuts: list[int], seed: int, style: StyleName
) -> None:
    midi = song(hits)
    result = normalized(midi)
    plan = plan_for(midi, result, cuts=cuts, seed=seed, style=style)

    assert midi_bytes(rendered(midi, plan).song) == midi_bytes(rendered(midi, plan).song)


def test_another_seed_or_take_draws_another_performance() -> None:
    midi = song(rock(4))
    result = normalized(midi)
    plan = plan_for(midi, result)
    take = plan.model_copy(update={"sections": (plan.sections[0].model_copy(update={"take": 1}),)})

    first = midi_bytes(rendered(midi, plan).song)

    assert midi_bytes(rendered(midi, plan.model_copy(update={"seed": 2})).song) != first
    assert midi_bytes(rendered(midi, take).song) != first


@given(grooves(), st.lists(st.integers(1, 5), min_size=1, max_size=3), st.data())
def test_rendering_one_section_again_leaves_the_others_as_they_were(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    style = data.draw(STYLES, label="style")
    plan = plan_for(midi, result, cuts=cuts, style=style)
    changed = data.draw(st.integers(0, len(plan.sections) - 1), label="section")
    controls = data.draw(control_vectors(skip=False), label="controls")
    again = plan_for(midi, result, cuts=cuts, sections={changed: controls}, style=style)

    before = {note.position: note.note for note in rendered(midi, plan).notes}
    after = rendered(midi, again).notes

    assert {
        note.position: note.note for note in after if note.section != changed
    }.items() <= before.items()


@given(grooves(), CUTS, st.data())
def test_every_note_comes_out_once_and_only_a_drop_leaves_one_out(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    names = sorted({note.articulation for note in result.score.notes})
    drop = data.draw(st.sets(st.sampled_from(names)), label="dropped")
    plan = plan_for(midi, result, cuts=cuts, style=data.draw(STYLES, label="style"))

    out = rendered(midi, plan, substitutions=dict.fromkeys(drop, DROP))

    expected = [note for note in result.score.notes if note.articulation not in drop]
    assert sorted(note.position for note in out.notes) == sorted(
        position
        for position, note in enumerate(result.score.notes)
        if note.articulation not in drop
    )
    assert len(drum_notes(out.song)) == len(expected)


@st.composite
def _played_twice(draw: st.DrawFn) -> tuple[list[Hit], list[Hit]]:
    """One groove played twice, with other velocities of the same types and other timing
    within 6 ms, on drums that never share a grid point with themselves."""
    pitches = (KICK, SNARE, HAT, RIDE, CRASH, TOM_1, COWBELL)
    hits = draw(grooves(pitches, max_bars=4))
    ranges = {SOFT: (20, 45), NORMAL: (55, 105), ACCENT: (112, 127)}
    played: list[list[Hit]] = [[], []]
    for hit in hits:
        tick, pitch, kind = hit[0], hit[1], hit[2] if len(hit) == 3 else NORMAL
        for take in played:
            shift = round(draw(st.floats(-6, 6)) * PPQ / 500)
            take.append((tick + shift + 48, pitch, draw(st.integers(*ranges[kind]))))
    return played[0], played[1]


@given(_played_twice(), CUTS, st.integers(0, 2**53 - 1), STYLES)
def test_input_velocities_and_timing_change_nothing_but_the_hit_types(
    takes: tuple[list[Hit], list[Hit]], cuts: list[int], seed: int, style: StyleName
) -> None:
    first, second = (song(take) for take in takes)
    one, two = normalized(first), normalized(second)

    def score(result: object) -> list[tuple[int, str, str]]:
        notes = one.score.notes if result is one else two.score.notes
        return sorted((note.tick, note.articulation, note.hit_type) for note in notes)

    assume(score(one) == score(two))
    plan = plan_for(first, one, cuts=cuts, seed=seed, style=style)

    assert midi_bytes(rendered(first, plan, result=one).song) == midi_bytes(
        rendered(second, plan, result=two).song
    )


def at_corners(
    data: st.DataObject,
    midi: MidiSong,
    result: Normalized,
    cuts: list[int],
    *,
    loose: bool = False,
) -> SessionPlan:
    """A plan in a drawn style whose sections' controls are drawn at their ends often, where
    the guards bind. `loose` sets the song's tightness to 0 and its feel to -1 or +1, under the
    sections'."""
    style = data.draw(STYLES, label="style")
    count = len(plan_for(midi, result, cuts=cuts).sections)
    controls = {
        number: data.draw(control_vectors(corners=True), label=f"section {number}")
        for number in range(count)
    }
    song_controls = None
    if loose:
        feel = data.draw(st.sampled_from((-1.0, 1.0)), label="feel")
        song_controls = ControlVector(tightness=0.0, feel=feel)
    return plan_for(midi, result, cuts=cuts, sections=controls, controls=song_controls, style=style)


EXTREMES = st.sampled_from((60.0, 600.0)) | TEMPOS
"""Tempos at 60 or 600 BPM half the time, so a change is often 10 to 1 either way."""


def tempo_changes(bars: int) -> st.SearchStrategy[list[tuple[int, float]]]:
    """Up to 120 tempo changes as `(tick, bpm)`, each on a 64th of the first `bars` bars, so they
    often fall between two hits a 16th apart."""
    ticks = st.integers(1, 64 * bars - 1).map(lambda step: step * SIXTEENTH // 4)
    return st.lists(st.tuples(ticks, EXTREMES), max_size=120)


DENSE = grooves((KICK, SNARE, HAT), per_bar=36)
"""Grooves on three drums, so notes on one pitch are often a 16th apart."""


@given(DENSE, CUTS, TEMPOS, tempo_changes(6), LENGTHS, st.data())
def test_notes_on_one_pitch_keep_their_order_and_most_of_their_grid_gap(
    hits: list[Hit],
    cuts: list[int],
    bpm: float,
    changes: list[tuple[int, float]],
    length: int,
    data: st.DataObject,
) -> None:
    midi = song(hits, bpm=bpm, tempos=changes, length=length)
    result = normalized(midi)

    one_pitch_keeps_its_order(
        result, rendered(midi, at_corners(data, midi, result, cuts, loose=True))
    )


def one_pitch_keeps_its_order(result: Normalized, out: Rendered) -> None:
    """Notes on one pitch keep their order and 0.6 of their grid gap in milliseconds, less half a
    tick where each lands for going to a tick, and a rendered note ends by the next one's start
    (ADR 0073)."""
    tempos = result.score.tempos
    for notes in by_key(out.notes, "pitch").values():
        for earlier, later in pairwise(notes):
            if earlier.kept and later.kept:
                continue
            ticks = [result.score.notes[note.position].tick for note in (earlier, later)]
            grid = tempos.tick_to_ms(ticks[1]) - tempos.tick_to_ms(ticks[0])
            played = tempos.tick_to_ms(later.note.start) - tempos.tick_to_ms(earlier.note.start)
            rounding = (landing_tick(result, earlier) + landing_tick(result, later)) / 2
            assert later.note.start > earlier.note.start
            assert played >= GAP_SHARE * grid - rounding - ROUNDING_MS
            if not earlier.kept:
                assert earlier.note.end <= later.note.start


def landing_tick(result: Normalized, note: RenderedNote) -> float:
    """The length of a tick where the note lands, in milliseconds: the longer of the ticks either
    side of its start, since a note going up to a tempo change is rounded in the tick before it."""
    tempos, start = result.score.tempos, note.note.start
    return max(tempos.ms_per_tick(max(start - 1, 0)), tempos.ms_per_tick(start))


@st.composite
def hat_runs(draw: st.DrawFn, groove: st.SearchStrategy[list[Hit]], bars: int) -> list[Hit]:
    """A groove with, half the time, a hat on every 16th of `bars` bars, so notes on one pitch are
    a 16th apart and their gap binds."""
    hits = draw(groove)
    if not draw(st.booleans()):
        return hits
    run: list[Hit] = [(step * SIXTEENTH, HAT) for step in range(16 * bars)]
    return [hit for hit in hits if hit[1] != HAT] + run


@given(
    flams(hat_runs(grooves((KICK, SNARE, HAT), max_bars=4), 4)),
    TEMPOS,
    tempo_changes(4),
    CUTS,
    st.data(),
)
def test_offsets_stay_within_the_cap_at_every_tempo(
    hits: list[Hit],
    bpm: float,
    changes: list[tuple[int, float]],
    cuts: list[int],
    data: st.DataObject,
) -> None:
    # Hats often run in 16ths, with changes of 10 to 1 between them, so the gap binds across a
    # change, and with graces, whose main notes move with them.
    midi = song(hits, bpm=bpm, tempos=changes)
    result = normalized(midi)

    offsets_within_the_cap(result, rendered(midi, at_corners(data, midi, result, cuts, loose=True)))


def offsets_within_the_cap(result: Normalized, out: Rendered) -> None:
    """Each rendered note's offset is within the cap plus two ticks for going to a tick, ticks of
    the tempo where the note lands, which a tempo change can set apart from its grid point's. A
    note played as it came in keeps its timing, however far off the grid it was played."""
    for note in out.notes:
        if not note.kept:
            assert abs(note.offset_ms) <= CAP_MS + 2 * landing_tick(result, note)


def test_a_note_cut_to_the_cap_before_a_tempo_change_goes_to_a_tick_of_that_tempo() -> None:
    # 60 BPM up to tick 180 and 600 after it, so a tick is 1.04 ms, then 0.10 ms. The snare on
    # tick 240, pushed early, is cut to -12 ms, which is before the change, at tick 174.48: its
    # nearest tick is half a 60 BPM tick past the cap, more than two ticks of its grid point's.
    hits: list[Hit] = [
        (0, SNARE, SOFT),
        (SIXTEENTH, KICK, SOFT),
        (SIXTEENTH, SNARE, SOFT),
        (2 * SIXTEENTH, KICK, SOFT),
        (0, KICK, SOFT),
        (10, KICK, NORMAL),
    ]
    midi = song(hits, bpm=60, tempos=[(180, 600.0)])
    result = normalized(midi)
    pushed = ControlVector(tightness=0.0, feel=-1.0)

    grid_ticks = 2 * result.score.tempos.ms_per_tick(SIXTEENTH)
    past = 0
    for seed in range(4):
        plan = plan_for(midi, result, controls=pushed, seed=seed, style="loose")
        out = rendered(midi, plan, result=result)
        offsets_within_the_cap(result, out)
        past += sum(
            note.offset_ms < -CAP_MS - grid_ticks
            for note in out.notes
            if note.note.pitch == SNARE and result.score.notes[note.position].tick == SIXTEENTH
        )
    assert past > 0


SHARED = (HAT, PEDAL, OPEN_HAT, SNARE, SIDESTICK, RIDE, BELL, KICK)
"""Pitches that share drums: three hats, snare and sidestick, ride bow and bell, so a pitch's
neighbour and its drum's neighbour are often different notes."""


@given(grooves(SHARED, velocities=(NORMAL, NORMAL, SOFT), per_bar=24), CUTS, st.data())
def test_velocities_are_1_to_127_and_never_repeat_on_a_pitch_or_a_drum(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)

    out = rendered(midi, at_corners(data, midi, result, cuts))

    assert all(1 <= note.note.velocity <= 127 for note in out.notes)
    for key in ("pitch", "drum"):
        for notes in by_key(out.notes, key).values():
            for earlier, later in pairwise(notes):
                if not (earlier.kept and later.kept):
                    assert earlier.note.velocity != later.note.velocity


@pytest.mark.parametrize("style", STYLE_NAMES)
@pytest.mark.parametrize("cuts", [(), tuple(range(1, 32))])
def test_16ths_at_600_bpm_played_loose_keep_most_of_their_gap(
    cuts: tuple[int, ...], style: StyleName
) -> None:
    midi = song([(step * SIXTEENTH, HAT) for step in range(32 * 16)], bpm=600)
    result = normalized(midi)
    loose = ControlVector(tightness=0.0, feel=1.0)

    for seed in range(4):
        plan = plan_for(midi, result, cuts=cuts, controls=loose, seed=seed, style=style)
        starts = [note.note.start for note in rendered(midi, plan, result=result).notes]
        gaps = [later - earlier for earlier, later in pairwise(starts)]
        assert min(gaps) >= GAP_SHARE * SIXTEENTH - 1


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_neighbours_across_a_boundary_never_share_a_velocity(style: StyleName) -> None:
    midi = song([(beat * PPQ, KICK) for beat in range(4 * 32)])
    result = normalized(midi)
    flat = ControlVector(dynamic_range=0.0)

    for seed in range(4):
        plan = plan_for(midi, result, cuts=range(1, 32), controls=flat, seed=seed, style=style)
        kicks = [note.note.velocity for note in rendered(midi, plan, result=result).notes]
        assert all(earlier != later for earlier, later in pairwise(kicks))


def soft_below(out: Rendered) -> None:
    """Every soft note is below every other note of its drum in its section."""
    places: dict[tuple[int, str, int], tuple[list[int], list[int]]] = {}
    for note in out.notes:
        if not note.kept:
            soft, other = places.setdefault((note.section, note.family, note.piece), ([], []))
            (soft if note.hit_type == "soft" else other).append(note.note.velocity)
    for soft, other in places.values():
        if soft and other:
            assert max(soft) < min(other)


@given(grooves(), CUTS, st.data())
def test_soft_notes_land_below_the_other_notes_of_their_drum_in_a_section(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)

    soft_below(rendered(midi, at_corners(data, midi, result, cuts)))


def test_soft_notes_are_held_below_where_their_center_meets_the_others() -> None:
    # A rider's weak hits at energy 0 and full dynamic range reach down to the soft center.
    hits: list[Hit] = []
    for bar in range(8):
        hits.extend(
            (bar * BAR + step * SIXTEENTH, HAT, SOFT if step % 4 else NORMAL) for step in range(16)
        )
    midi = song(hits)
    result = normalized(midi)
    corner = ControlVector(energy=0.0, ghost_level=1.0, groove=1.0, dynamic_range=1.0)

    held = 0
    for seed in range(4):
        out = rendered(midi, plan_for(midi, result, controls=corner, seed=seed), result=result)
        soft_below(out)
        held += out.guards.soft
    assert held > 0


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_rider_hits_alternate_strong_and_weak_about_three_times_in_four(style: StyleName) -> None:
    midi = song(rock(256))
    plan = plan_for(midi, normalized(midi), cuts=range(8, 256, 8), style=style)
    out = rendered(midi, plan)

    alternating = [note for note in out.notes if note.part.rider == "alternate"]
    pairs = [
        (earlier.strong, later.strong)
        for earlier, later in pairwise(alternating)
        if earlier.section == later.section
    ]
    flips = sum(first != second for first, second in pairs) / len(pairs)
    strong = [note.note.velocity for note in alternating if note.strong]
    weak = [note.note.velocity for note in alternating if not note.strong]

    assert 0.70 <= flips <= 0.85
    assert np.mean(strong) > np.mean(weak)


TURNS = 0.81
"""The least share of turns on a quarter-note ride, over `TURN_SEEDS` takes of 256 bars at the
defaults. Simulated over 100 seeds, one such take turns 0.77 of the time, spread 0.015, with the
riders drawing the other roles' noise, 5.12, and 0.84, spread 0.016, with their own, 2.5 (ADR
0076). The mean of four takes spreads about half as far, so this is 4 to 5 of its spreads from
each. The styles share their velocities, so each draws the same."""
TURN_SEEDS = range(1, 5)


def turns(velocities: Sequence[int]) -> tuple[int, int]:
    """Of the neighbouring steps between the velocities that both move, how many change
    direction, and how many there are."""
    signs = np.sign(np.diff(np.array(velocities, dtype=np.float64)))
    moving = (signs[:-1] != 0) & (signs[1:] != 0)
    return int(((signs[:-1] != signs[1:]) & moving).sum()), int(moving.sum())


@cache
def ride() -> tuple[MidiSong, Normalized]:
    """256 bars of a quarter-note ride over kick on 1 and 3 and snare on 2 and 4."""
    hits: list[Hit] = []
    for bar in range(256):
        at = bar * BAR
        hits.extend([(at, KICK), (at + 2 * PPQ, KICK), (at + PPQ, SNARE), (at + 3 * PPQ, SNARE)])
        hits.extend((at + quarter * PPQ, RIDE) for quarter in range(4))
    midi = song(hits)
    return midi, normalized(midi)


def ride_takes(controls: ControlVector, style: StyleName) -> tuple[float, float, int]:
    """Over `TURN_SEEDS` takes of `ride()` in sections of 8 bars, the share of turns between
    neighbouring alternating hits of a section, the mean rider gap, and the loudest velocity."""
    midi, result = ride()
    changed = steps = top = 0
    gaps: list[float] = []
    for seed in TURN_SEEDS:
        plan = plan_for(
            midi, result, cuts=range(8, 256, 8), controls=controls, seed=seed, style=style
        )
        out = rendered(midi, plan, result=result)
        sections: dict[int, list[int]] = {}
        for note in out.notes:
            if note.part.rider == "alternate":
                sections.setdefault(note.section, []).append(note.note.velocity)
        for velocities in sections.values():
            more, of = turns(velocities)
            changed, steps = changed + more, steps + of
        gap = rider_gap(out.notes)
        assert gap is not None
        gaps.append(gap)
        top = max(top, *(note.note.velocity for note in out.notes))
    return changed / steps, float(np.mean(gaps)), top


@pytest.mark.parametrize("style", STYLE_NAMES)
def test_a_quarter_note_ride_turns_up_and_down_clearly(style: StyleName) -> None:
    share, _, _ = ride_takes(ControlVector(), style)

    assert share >= TURNS, share


TOP_GAP = 7.8
TOP_TURNS = 0.815
"""The least rider gap and share of turns of `ride_takes` from energy 0.8 up. With the strong hits
held a spread of their noise under 127 (ADR 0077), simulated over 30 seeds, one 256-bar take at
energy 0.8 to 1.0 has a gap of 8.3, spread 0.29, and turns 0.84 of the time, spread 0.014, where
letting them pass 127, to be reflected below it, gave gaps of 7.6, 4.8 and 0.5 at 0.8, 0.9 and
1.0, and turns 0.83, 0.79 and 0.73. At 0.5 both give 9.1 and 0.84. The mean of four takes
spreads about half as far as one, so each floor is about 3.6 of its spreads under the held gap
and turns."""


@pytest.mark.parametrize("energy", [0.8, 0.9, 1.0])
def test_a_ride_keeps_its_gap_and_turns_at_full_energy_under_127(energy: float) -> None:
    share, gap, top = ride_takes(ControlVector(energy=energy), "tight")

    assert gap >= TOP_GAP, gap
    assert share >= TOP_TURNS, share
    assert top <= 127


def test_hits_on_one_grid_point_stay_within_10_ms_of_each_other_by_default() -> None:
    fill = ((4, SNARE), (3, TOM_1), (2, TOM_2), (1, TOM_2))
    hits: list[Hit] = [(0, CRASH)]
    for bar in range(64):
        hits.extend(rock(1, start=bar))
        hits.extend(((bar + 1) * BAR - step * SIXTEENTH, pitch) for step, pitch in fill)
    midi = song(hits)
    result = normalized(midi)
    out = rendered(midi, plan_for(midi, result))

    onsets: dict[int, list[float]] = {}
    for note in out.notes:
        if not note.grace:
            tick = result.score.notes[note.position].tick
            onsets.setdefault(tick, []).append(note.offset_ms)
    assert max(max(offsets) - min(offsets) for offsets in onsets.values()) <= 10


def test_a_grace_keeps_its_gap_before_its_main_note() -> None:
    hits: list[Hit] = []
    for bar in range(8):
        hits.extend(
            [(bar * BAR + PPQ - FLAM, SNARE, SOFT), (bar * BAR + PPQ, SNARE), (bar * BAR, KICK)]
        )
    midi = song(hits)
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result, cuts=(4,)))

    by_position = {note.position: note for note in out.notes}
    by_source = {note.source_index: position for position, note in enumerate(result.score.notes)}
    graces = [note for note in result.score.notes if note.grace_of is not None]
    assert len(graces) == 8
    for grace in graces:
        main = result.score.notes[by_source[grace.grace_of or 0]]
        written = by_position[by_source[grace.source_index]].note
        written_main = by_position[by_source[main.source_index]].note
        assert abs((written_main.start - written.start) - (main.tick - grace.tick)) <= 1


@pytest.mark.parametrize(("first", "gap", "kept"), [(0, 20, 20), (0, 30, 23), (PPQ, 30, 30)])
def test_a_flam_on_the_first_tick_keeps_its_gap_as_far_as_the_cap_allows(
    first: int, gap: int, kept: int
) -> None:
    # Two kicks `gap` ticks apart from `first`, the main read on `first`. On tick 0 the score
    # can't put the grace before its main, so the guards place it by the gap it was played at:
    # 20 ticks are 10.4 ms, inside the cap, and 30 ticks 15.6 ms, so that main stops at the cap,
    # 23 ticks. On beat 2 the grace is placed in the score, and the whole gap is kept.
    midi = song(
        [(first, KICK), (first + gap, KICK), (first + 2 * PPQ, SNARE), (first + 3 * PPQ, KICK)]
    )
    result = normalized(midi)

    for seed in range(8):
        out = rendered(midi, plan_for(midi, result, seed=seed), result=result)
        grace, main = [note for note in out.notes if note.family == "kick"][:2]
        assert (grace.grace, main.grace) == (True, False)
        assert abs((main.note.start - grace.note.start) - kept) <= 1
        assert grace.note.end <= main.note.start
        assert abs(main.offset_ms) <= CAP_MS
        assert out.guards.unmet == (1 if kept < gap else 0)
        if kept < gap:
            assert grace.note.start == 0


def graces_keep_their_gap(result: Normalized, out: Rendered) -> None:
    """Each grace starts before its main by the gap it was played at, within a tick, unless the
    score puts it on its main's tick, as on the song's first tick, and that gap would take the
    main past the cap: then the main is at the cap, and the grace still before it."""
    by_position = {note.position: note for note in out.notes}
    by_source = {note.source_index: position for position, note in enumerate(result.score.notes)}
    for position, grace in enumerate(result.score.notes):
        if grace.grace_of is None:
            continue
        main = result.score.notes[by_source[grace.grace_of]]
        written, written_main = by_position[position], by_position[by_source[grace.grace_of]]
        gap = written_main.note.start - written.note.start
        assert gap >= 1
        if abs(gap - (main.source.start - grace.source.start)) > 1:
            tick = result.score.tempos.ms_per_tick(main.tick)
            assert grace.tick == main.tick
            assert written_main.offset_ms > CAP_MS - tick


@given(flams(grooves()), CUTS, st.data())
def test_graces_keep_their_gap_and_their_order_and_on_the_first_tick_up_to_the_cap(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    # At 120 BPM no grid step is within 15 ms of a gap of 5 to 45 ms, so no drawn grace is taken
    # for a step of the grid (ADR 0027).
    midi = song(hits)
    result = normalized(midi)

    out = rendered(midi, at_corners(data, midi, result, cuts, loose=True))

    graces_keep_their_gap(result, out)
    one_pitch_keeps_its_order(result, out)


@pytest.mark.parametrize(
    ("hits", "bpm", "cuts"),
    [
        pytest.param(
            [(0, KICK), (2 * BAR - 48, HAT), (2 * BAR, HAT), (2 * BAR + PPQ, KICK)],
            600.0,
            (2,),
            id="either-side-of-a-boundary",
        ),
        pytest.param(
            [(step * SIXTEENTH, HAT) for step in range(41)] + [(2 * BAR - 250, HAT)],
            600.0,
            (2,),
            id="before-a-boundary",
        ),
        pytest.param(
            [(230, HAT, SOFT), (240, HAT, SOFT), (230, PEDAL, SOFT), (240, PEDAL, SOFT)],
            120.0,
            (),
            id="the-later-with-a-grace",
        ),
    ],
)
@pytest.mark.parametrize("style", STYLE_NAMES)
def test_two_hats_read_onto_one_grid_point_keep_their_order_and_gaps(
    hits: list[Hit], bpm: float, cuts: tuple[int, ...], style: StyleName
) -> None:
    # Two hats played a few milliseconds apart and read onto one grid point. Either side of a
    # boundary they landed on one tick. Before one, the second was pushed past its side of the
    # gap, and the next section's hat kept under 0.6 of it. With a grace before each, the second
    # kept its place and the first went after it.
    midi = song(hits, bpm=bpm)
    result = normalized(midi)

    for seed in range(4):
        for feel in (-1.0, 1.0):
            loose = ControlVector(tightness=0.0, feel=feel)
            plan = plan_for(midi, result, cuts=cuts, controls=loose, seed=seed, style=style)
            out = rendered(midi, plan, result=result)
            one_pitch_keeps_its_order(result, out)
            graces_keep_their_gap(result, out)
            offsets_within_the_cap(result, out)


@given(grooves(), CUTS, st.data())
def test_a_section_played_as_it_came_in_comes_out_unchanged(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    count = len(plan_for(midi, result, cuts=cuts).sections)
    kept = data.draw(st.integers(0, count - 1), label="kept")
    style = data.draw(STYLES, label="style")

    out = rendered(
        midi,
        plan_for(midi, result, cuts=cuts, sections={kept: ControlVector(skip=True)}, style=style),
    )

    for note in out.notes:
        if note.section == kept:
            assert note.kept
            assert note.note == result.score.notes[note.position].source


def test_other_tracks_and_every_event_stay_as_they_were() -> None:
    keys = track(
        (0, name("Keys")),
        (0, tempo(120)),
        (0, on(60, 80, channel=0)),
        (0, cc(64, 127, channel=0)),
        (BAR, off(60, channel=0)),
        (2 * BAR, end()),
    )
    drums: list[tuple[int, MidoMessage]] = [(0, name("Drums")), (0, cc(4, 0))]
    for hit in sorted(rock(2)):
        drums.extend([(hit[0], on(hit[1])), (hit[0] + 10, off(hit[1]))])
    drums.sort(key=lambda item: item[0])
    midi = parse_midi(build(keys, track(*drums, (2 * BAR, end())), ppq=PPQ))
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result))

    assert result.score.track == 1
    assert out.song.events == midi.events
    assert [note for note in out.song.notes if note.track == 0] == [
        note for note in midi.notes if note.track == 0
    ]
    assert out.song.track_ends[0] == midi.track_ends[0]
    assert len([note for note in out.song.notes if note.track == 1]) == len(result.score.notes)


def test_a_family_the_target_lacks_is_asked_about_and_a_substitution_settles_it(
    tmp_path: Path,
) -> None:
    target = load_kit(
        tmp_path,
        articulation("kick.hit", 24),
        articulation("snare.center", 26, velocity=[1, 100]),
        articulation("hat.closed", 30),
        id="small",
    )
    midi = song([*rock(2), (0, COWBELL)])
    result = normalized(midi)

    asked = place_score(result.score, GM, target)

    assert [request.kind for request in asked.decisions] == ["conversion"]
    assert asked.decisions[0].details["source"] == "cowbell.hit"
    with pytest.raises(ValueError, match="notes wait for a conversion answer"):
        render(midi, result, asked, plan_for(midi, result))

    out = rendered(midi, plan_for(midi, result), target=target, substitutions={"cowbell.hit": DROP})

    assert sorted({note.note.pitch for note in out.notes}) == [24, 26, 30]
    assert max(note.note.velocity for note in out.notes if note.note.pitch == 26) <= 100
    assert len(drum_notes(out.song)) == len(result.score.notes) - 1


def test_a_substitution_for_an_articulation_the_drums_lack_is_an_answer_error() -> None:
    midi = song(rock(1))

    with pytest.raises(AnswerError, match=r"crash\.1\.hit"):
        place_score(normalized(midi).score, GM, GM, {"crash.1.hit": "snare.center"})


def test_a_plan_that_doesn_t_cover_the_drums_bars_is_refused() -> None:
    midi = song(rock(4))
    result = normalized(midi)
    short = song(rock(2))

    with pytest.raises(ValueError, match="cover 2 bars, and the drums 4"):
        render(midi, result, place_score(result.score, GM, GM), plan_for(short, normalized(short)))


def test_a_drift_is_one_slow_process_per_time_constant() -> None:
    times = np.arange(20_000, dtype=np.float64)
    rng = np.random.default_rng(np.random.SeedSequence(0))

    values = drift(times, 2.5, (16, 64, 256), rng)

    assert values.shape == times.shape
    assert 1.5 < values.std() < 3.5
    assert np.corrcoef(values[:-1], values[1:])[0, 1] > 0.9
    assert drift(np.zeros(0), 2.5, (16,), rng).size == 0


def test_a_render_lists_its_notes_in_play_order_with_their_sections() -> None:
    midi = song(rock(4))
    result = normalized(midi)

    out: Rendered = rendered(midi, plan_for(midi, result, cuts=(2,)))

    assert [note.section for note in out.notes] == sorted(note.section for note in out.notes)
    assert {note.part.role for note in out.notes} == {"kick", "backbeat", "rider"}


def test_a_section_played_as_it_came_in_to_another_kit_keeps_its_velocity_and_timing(
    tmp_path: Path,
) -> None:
    target = load_kit(
        tmp_path,
        articulation("kick.hit", 24),
        articulation("snare.center", 26, velocity=[1, 100]),
        articulation("hat.closed", 30, channel=2),
        id="other",
    )
    midi = song([(tick + 7, pitch, ACCENT) for tick, pitch, *_ in rock(2)])
    result = normalized(midi)

    out = rendered(
        midi,
        plan_for(midi, result, controls=ControlVector(skip=True)),
        target=target,
    )

    for note in out.notes:
        source = result.score.notes[note.position].source
        assert (note.note.start, note.note.end) == (source.start, source.end)
        assert note.note.pitch == {KICK: 24, SNARE: 26, HAT: 30}[source.pitch]
        assert note.note.channel == (1 if source.pitch == HAT else source.channel)
        assert note.note.velocity == min(source.velocity, 100 if source.pitch == SNARE else 127)


def test_a_velocity_range_of_one_value_wins_over_no_repeats(tmp_path: Path) -> None:
    target = load_kit(
        tmp_path,
        articulation("kick.hit", 24, velocity=[64, 64]),
        articulation("snare.center", 26),
        articulation("hat.closed", 30),
        id="narrow",
    )
    midi = song(rock(2))

    out = rendered(midi, plan_for(midi, normalized(midi)), target=target)

    assert {note.note.velocity for note in out.notes if note.note.pitch == 24} == {64}
    assert out.guards.unmet > 0


def test_loud_notes_next_to_a_boundary_find_a_velocity_of_their_class_that_doesn_t_repeat() -> None:
    midi = song([(0, KICK), (SIXTEENTH, KICK), (2 * SIXTEENTH, KICK), (2 * BAR, KICK)])
    result = normalized(midi)
    loud = ControlVector(energy=1.0, dynamic_range=1.0, arc="drop")

    out = rendered(midi, plan_for(midi, result, cuts=(2,), sections={0: loud}))

    kicks = [note.note.velocity for note in out.notes]
    assert all(earlier != later for earlier, later in pairwise(kicks))
    assert out.guards.unmet == 0


def test_a_song_in_3_4_then_7_8_with_tempo_changes_renders_on_its_own_beats() -> None:
    three, seven = 3 * PPQ, 7 * PPQ // 2
    hits: list[Hit] = []
    for bar in range(4):
        at = bar * three
        hits.extend([(at, KICK), (at + PPQ, SNARE), (at + 2 * PPQ, SNARE)])
        hits.extend((at + eighth * PPQ // 2, HAT) for eighth in range(6))
    for bar in range(4):
        at = 4 * three + bar * seven
        hits.extend([(at, KICK), (at + 2 * PPQ // 2, SNARE), (at + 4 * PPQ // 2, SNARE)])
        hits.extend((at + eighth * PPQ // 2, HAT) for eighth in range(7))
    midi = song(
        hits,
        signatures=[(0, 3, 4), (4 * three, 7, 8)],
        tempos=[(2 * three, 90.0), (4 * three, 160.0), (4 * three + 2 * seven, 75.0)],
    )
    result = normalized(midi)
    loose = ControlVector(tightness=0.0, feel=1.0)

    out = rendered(midi, plan_for(midi, result, cuts=(4,), controls=loose))

    assert [section.bars for section in plan_for(midi, result, cuts=(4,)).sections] == [4, 4]
    assert len(out.notes) == len(hits)
    backbeats = {
        result.score.position(result.score.notes[note.position].tick).beat
        for note in out.notes
        if note.part.role == "backbeat"
    }
    assert backbeats == {1.0, 2.0, 4.0}
    offsets_within_the_cap(result, out)
    for notes in by_key(out.notes, "pitch").values():
        assert all(earlier.note.start < later.note.start for earlier, later in pairwise(notes))


def neighbours_differ(out: Rendered) -> None:
    """No two notes in a row on a pitch, or on a drum, share a velocity."""
    for key in ("pitch", "drum"):
        for notes in by_key(out.notes, key).values():
            for earlier, later in pairwise(notes):
                assert earlier.note.velocity != later.note.velocity


def test_a_pitch_s_neighbours_across_a_boundary_differ_with_its_drum_between_them() -> None:
    # Each bar opens with a pedal hat, so the closed hats either side of a bar line are a pitch's
    # neighbours whose places among the hat's notes are two apart: only their pitch tells them.
    hits: list[Hit] = []
    for bar in range(32):
        hits.append((bar * BAR, PEDAL))
        hits.extend((bar * BAR + eighth * PPQ // 2, HAT) for eighth in range(1, 8))
    midi = song(hits)
    result = normalized(midi)
    flat = ControlVector(dynamic_range=0.0)

    for seed in range(4):
        plan = plan_for(midi, result, cuts=range(1, 32), controls=flat, seed=seed)
        neighbours_differ(rendered(midi, plan, result=result))


def test_a_drum_s_neighbours_across_a_boundary_differ_on_pitches_it_doesn_t_share() -> None:
    # Three closed hats in even bars and three open hats in odd ones, a section each, riding one
    # run. The hats either side of a bar line from an even bar have the same parity of place
    # among their own pitch's notes, so only their places on the drum tell them apart.
    hits: list[Hit] = []
    for bar in range(32):
        pitch = HAT if bar % 2 == 0 else OPEN_HAT
        hits.extend((bar * BAR + beat * PPQ, pitch) for beat in range(3))
    midi = song(hits)
    result = normalized(midi)
    flat = ControlVector(dynamic_range=0.0)

    for seed in range(4):
        plan = plan_for(midi, result, cuts=range(1, 32), controls=flat, seed=seed)
        neighbours_differ(rendered(midi, plan, result=result))


def test_the_cap_holds_after_a_kept_hat_played_far_late_on_a_slow_32nd_grid() -> None:
    # At 30 BPM a 32nd is 250 ms. The kept bar's last hat is played about 115 ms after the 32nd
    # point it is read on, so keeping 0.6 of the gap would take the next hat to about +15 ms.
    late = round(0.73 * 500 / (60_000 / 30 / PPQ))
    hits: list[Hit] = [(0, KICK), (BAR, KICK), (2 * BAR, KICK)]
    hits.extend((step * SIXTEENTH + (late if step == 15 else 0), HAT) for step in range(32))
    midi = song(hits, bpm=30)
    result = normalized(midi)
    plan = plan_for(midi, result, cuts=(1,), sections={0: ControlVector(skip=True)})

    out = rendered(midi, plan, result=result)

    kept = [note for note in out.notes if note.kept and note.note.pitch == HAT][-1]
    first = next(note for note in out.notes if not note.kept and note.note.pitch == HAT)
    assert kept.offset_ms > 110
    assert first.offset_ms <= 12
    assert first.note.start > kept.note.start
    assert out.guards.unmet == 1
