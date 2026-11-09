"""Rendering a score: the plan's property tests, and examples of what the guards and the target
kit do (ADRs 0048 to 0050)."""

from collections.abc import Sequence
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
    grooves,
    normalized,
    plan_for,
    rendered,
    rock,
    song,
)
from human_o_matic.controls import ControlVector, SessionPlan
from human_o_matic.maps.convert import DROP
from human_o_matic.midi.io import MidiSong, Note, midi_bytes, parse_midi
from human_o_matic.normalize.answers import AnswerError
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import Rendered, RenderedNote, drift, render
from human_o_matic.render.target import place_score
from map_files import articulation, load_kit
from midi_files import MidoMessage, build, cc, end, name, off, on, tempo, track

FLAM = round(PPQ * 30 / 500)
"""30 ms at 120 BPM: a grace's gap before its main."""
CUTS = st.lists(st.integers(1, 5), max_size=3)
CAP_MS = 12.0
"""The plan's cap on an offset from the grid."""
GAP_SHARE = 0.6
"""The share of its grid gap the plan says a note keeps from the one before it on its pitch."""


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


@given(grooves(), CUTS, st.integers(0, 2**53 - 1))
def test_the_same_song_plan_and_seed_give_the_same_bytes(
    hits: list[Hit], cuts: list[int], seed: int
) -> None:
    midi = song(hits)
    result = normalized(midi)
    plan = plan_for(midi, result, cuts=cuts, seed=seed)

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
    plan = plan_for(midi, result, cuts=cuts)
    changed = data.draw(st.integers(0, len(plan.sections) - 1), label="section")
    controls = data.draw(control_vectors(skip=False), label="controls")
    again = plan_for(midi, result, cuts=cuts, sections={changed: controls})

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

    out = rendered(midi, plan_for(midi, result, cuts=cuts), substitutions=dict.fromkeys(drop, DROP))

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


@given(_played_twice(), CUTS, st.integers(0, 2**53 - 1))
def test_input_velocities_and_timing_change_nothing_but_the_hit_types(
    takes: tuple[list[Hit], list[Hit]], cuts: list[int], seed: int
) -> None:
    first, second = (song(take) for take in takes)
    one, two = normalized(first), normalized(second)

    def score(result: object) -> list[tuple[int, str, str]]:
        notes = one.score.notes if result is one else two.score.notes
        return sorted((note.tick, note.articulation, note.hit_type) for note in notes)

    assume(score(one) == score(two))
    plan = plan_for(first, one, cuts=cuts, seed=seed)

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
    """A plan whose sections' controls are drawn at their ends often, where the guards bind.
    `loose` sets the song's tightness to 0 and its feel to -1 or +1, under the sections'."""
    count = len(plan_for(midi, result, cuts=cuts).sections)
    controls = {
        number: data.draw(control_vectors(corners=True), label=f"section {number}")
        for number in range(count)
    }
    song_controls = None
    if loose:
        feel = data.draw(st.sampled_from((-1.0, 1.0)), label="feel")
        song_controls = ControlVector(tightness=0.0, feel=feel)
    return plan_for(midi, result, cuts=cuts, sections=controls, controls=song_controls)


DENSE = grooves((KICK, SNARE, HAT), per_bar=36)
"""Grooves on three drums, so notes on one pitch are often a 16th apart."""


@given(DENSE, CUTS, TEMPOS, LENGTHS, st.data())
def test_notes_on_one_pitch_keep_their_order_and_most_of_their_grid_gap(
    hits: list[Hit], cuts: list[int], bpm: float, length: int, data: st.DataObject
) -> None:
    midi = song(hits, bpm=bpm, length=length)
    result = normalized(midi)

    out = rendered(midi, at_corners(data, midi, result, cuts, loose=True))

    for notes in by_key(out.notes, "pitch").values():
        for earlier, later in pairwise(notes):
            if earlier.kept and later.kept:
                continue
            grid = (
                result.score.notes[later.position].tick - result.score.notes[earlier.position].tick
            )
            assert later.note.start > earlier.note.start
            assert later.note.start - earlier.note.start >= GAP_SHARE * grid - 1
            if not earlier.kept:
                assert earlier.note.end <= later.note.start


@given(
    grooves((KICK, SNARE, HAT), max_bars=4),
    TEMPOS,
    st.lists(st.tuples(st.integers(1, 4 * 64 - 1), TEMPOS), max_size=120),
    CUTS,
    st.data(),
)
def test_offsets_stay_within_the_cap_at_every_tempo(
    hits: list[Hit],
    bpm: float,
    tempos: list[tuple[int, float]],
    cuts: list[int],
    data: st.DataObject,
) -> None:
    changes = [(step * SIXTEENTH // 4, value) for step, value in tempos]
    midi = song(hits, bpm=bpm, tempos=changes)
    result = normalized(midi)

    out = rendered(midi, at_corners(data, midi, result, cuts, loose=True))

    for note in out.notes:
        tick = result.score.notes[note.position].tick
        slack = 2 * result.score.tempos.ms_per_tick(tick)
        assert abs(note.offset_ms) <= CAP_MS + slack


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


@pytest.mark.parametrize("cuts", [(), tuple(range(1, 32))])
def test_16ths_at_600_bpm_played_loose_keep_most_of_their_gap(cuts: tuple[int, ...]) -> None:
    midi = song([(step * SIXTEENTH, HAT) for step in range(32 * 16)], bpm=600)
    result = normalized(midi)
    loose = ControlVector(tightness=0.0, feel=1.0)

    for seed in range(4):
        plan = plan_for(midi, result, cuts=cuts, controls=loose, seed=seed)
        starts = [note.note.start for note in rendered(midi, plan, result=result).notes]
        gaps = [later - earlier for earlier, later in pairwise(starts)]
        assert min(gaps) >= GAP_SHARE * SIXTEENTH - 1


def test_neighbours_across_a_boundary_never_share_a_velocity() -> None:
    midi = song([(beat * PPQ, KICK) for beat in range(4 * 32)])
    result = normalized(midi)
    flat = ControlVector(dynamic_range=0.0)

    for seed in range(4):
        plan = plan_for(midi, result, cuts=range(1, 32), controls=flat, seed=seed)
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
    hits: list[Hit] = []
    for bar in range(8):
        hits.extend(
            (bar * BAR + step * SIXTEENTH, SNARE, SOFT if step % 4 else NORMAL)
            for step in range(16)
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


def test_rider_hits_alternate_strong_and_weak_about_three_times_in_four() -> None:
    midi = song(rock(256))
    out = rendered(midi, plan_for(midi, normalized(midi), cuts=range(8, 256, 8)))

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


@given(grooves(), CUTS, st.data())
def test_a_section_played_as_it_came_in_comes_out_unchanged(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    count = len(plan_for(midi, result, cuts=cuts).sections)
    kept = data.draw(st.integers(0, count - 1), label="kept")

    out = rendered(
        midi, plan_for(midi, result, cuts=cuts, sections={kept: ControlVector(skip=True)})
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
    for note in out.notes:
        tick = result.score.notes[note.position].tick
        assert abs(note.offset_ms) <= CAP_MS + 2 * result.score.tempos.ms_per_tick(tick)
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
