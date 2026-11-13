"""Creative mode: the plan's properties with sections that add notes, and examples of what each
addition does and when it is skipped (ADRs 0091 to 0095)."""

from collections import Counter
from collections.abc import Sequence
from itertools import pairwise

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from grooves import (
    BAR,
    CRASH,
    GM,
    HAT,
    KICK,
    LENGTHS,
    NORMAL,
    PPQ,
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
from human_o_matic.instruments.generic import GENERIC
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiSong, Note, midi_bytes
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import Rendered, RenderedNote, render
from human_o_matic.render.style import STYLE_NAMES
from human_o_matic.render.target import place_score

CUTS = st.lists(st.integers(1, 5), max_size=3)
STYLES = st.sampled_from(STYLE_NAMES)
CAP_MS = 12.0
GAP_SHARE = 0.6
ROUNDING_MS = 1e-6
SLEEP_TOKEN = find_kit("sleep-token-ii/default")
RIMSHOT, CHOKE = 40, 91
"""Sleep Token II's snare rimshot and crash 1 choke."""
ON = ControlVector(creative=True)


def identity(note: RenderedNote) -> tuple[object, ...]:
    """What names a note across two renders: its position in the score, or for an added note,
    its section, kind, grid point and pitch."""
    if note.added is not None and note.added != "rimshot":
        return ("added", note.section, note.added, note.tick, note.note.pitch)
    return ("score", note.position)


def others(out: Rendered, changed: int) -> dict[tuple[object, ...], Note]:
    return {identity(note): note.note for note in out.notes if note.section != changed}


def drawn_plan(
    data: st.DataObject,
    midi: MidiSong,
    result: Normalized,
    cuts: list[int],
    *,
    loose: bool = False,
) -> SessionPlan:
    """A plan in a drawn style whose sections' controls, creative among them, are drawn at
    their ends often, where the guards bind."""
    count = len(plan_for(midi, result, cuts=cuts).sections)
    controls = {
        number: data.draw(control_vectors(corners=True, creative=True), label=f"section {number}")
        for number in range(count)
    }
    song_controls = ControlVector(creative=data.draw(st.booleans(), label="song creative"))
    if loose:
        feel = data.draw(st.sampled_from((-1.0, 1.0)), label="feel")
        song_controls = song_controls.model_copy(update={"tightness": 0.0, "feel": feel})
    style = data.draw(STYLES, label="style")
    return plan_for(midi, result, cuts=cuts, sections=controls, controls=song_controls, style=style)


@st.composite
def sparse_songs(draw: st.DrawFn) -> list[Hit]:
    """Up to 12 bars of kick and snare with few cymbals, a crash on a drawn 16th of some bars,
    and toms and soft snare notes here and there: what gets crashes and fills added, with the
    same cymbal and drums either side of the boundaries."""
    bars = draw(st.integers(2, 12))
    hits: list[Hit] = []
    for bar in range(bars):
        at = bar * BAR
        hits += [(at, KICK), (at + PPQ, SNARE), (at + 3 * PPQ, SNARE)]
        hits += [(at + step * PPQ, HAT) for step in range(0, 4, draw(st.sampled_from((2, 4))))]
        for _ in range(draw(st.integers(0, 2))):
            step = draw(st.integers(0, 15))
            pitch = draw(st.sampled_from((CRASH, TOM_1, TOM_2, SNARE)))
            hits.append((at + step * SIXTEENTH, pitch, SOFT if pitch == SNARE else NORMAL))
    unique = {(hit[0], hit[1]): hit for hit in hits}
    return list(unique.values())


SPARSE_CUTS = st.lists(st.integers(1, 11), min_size=1, max_size=5)


@given(grooves() | sparse_songs(), CUTS | SPARSE_CUTS, st.data())
def test_a_section_turned_creative_leaves_every_other_section_as_it_was(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    plan = drawn_plan(data, midi, result, cuts)
    changed = data.draw(st.integers(0, len(plan.sections) - 1), label="section")
    sections = list(plan.sections)
    off, on = (
        plan.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={"controls": section.controls.model_copy(update={"creative": value})}
                    )
                    if number == changed
                    else section
                    for number, section in enumerate(sections)
                )
            }
        )
        for value in (False, True)
    )

    assert others(rendered(midi, off), changed) == others(rendered(midi, on), changed)


@given(
    grooves() | sparse_songs(),
    st.lists(st.integers(1, 5), min_size=1, max_size=3) | SPARSE_CUTS,
    st.data(),
)
def test_rendering_one_section_again_leaves_the_others_and_what_they_added_as_they_were(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    plan = drawn_plan(data, midi, result, cuts)
    changed = data.draw(st.integers(0, len(plan.sections) - 1), label="section")
    held = plan.sections[changed]
    controls = data.draw(control_vectors(skip=False, creative=True), label="controls")
    # Turning `skip` on or off is the one exception (ADR 0050), so the section keeps its own.
    controls = controls.model_copy(update={"skip": held.controls.skip})
    take = data.draw(st.integers(0, 2), label="take")
    again = plan.model_copy(
        update={
            "sections": tuple(
                section.model_copy(update={"controls": controls, "take": take})
                if number == changed
                else section
                for number, section in enumerate(plan.sections)
            )
        }
    )

    assert others(rendered(midi, plan), changed) == others(rendered(midi, again), changed)


@given(grooves(), CUTS, st.integers(0, 2**53 - 1), STYLES)
def test_the_same_song_plan_and_seed_give_the_same_bytes_with_creative_sections(
    hits: list[Hit], cuts: list[int], seed: int, style: str
) -> None:
    midi = song(hits)
    result = normalized(midi)
    plan = plan_for(midi, result, cuts=cuts, controls=ON, seed=seed)
    plan = plan.model_copy(update={"style": style})

    assert midi_bytes(rendered(midi, plan).song) == midi_bytes(rendered(midi, plan).song)


@given(grooves(), CUTS, st.data())
def test_creative_mode_left_off_or_set_false_renders_as_without_it(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    style = data.draw(STYLES, label="style")
    unset = plan_for(midi, result, cuts=cuts, style=style)
    false = plan_for(midi, result, cuts=cuts, style=style, controls=ControlVector(creative=False))

    out = rendered(midi, false)

    assert midi_bytes(out.song) == midi_bytes(rendered(midi, unset).song)
    assert all(report is None for report in out.creative)
    assert all(note.added is None for note in out.notes)


def placed_drums(result: Normalized, target: object = GM) -> set[tuple[str, int, int]]:
    """Each drum of the score as placed in General MIDI, with the ticks it has a note on."""
    placement = place_score(result.score, GM, GM)
    return {
        (placed.family, placed.piece, note.tick)
        for note, placed in zip(result.score.notes, placement.notes, strict=True)
        if placed is not None
    }


@given(grooves() | sparse_songs(), CUTS | SPARSE_CUTS, st.data())
def test_every_note_comes_out_once_and_the_added_ones_are_those_the_report_counts(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)

    out = rendered(midi, drawn_plan(data, midi, result, cuts))

    added = [note for note in out.notes if note.added not in (None, "rimshot")]
    reported = Counter[str]()
    for report in out.creative:
        if report is not None:
            reported.update(report.added)
    assert sorted(
        note.position for note in out.notes if note.position < len(result.score.notes)
    ) == list(range(len(result.score.notes)))
    assert len(out.notes) == len(result.score.notes) + len(added)
    assert Counter(note.added for note in out.notes if note.added) == reported
    assert len([n for n in out.song.notes if n.track == 0]) == len(out.notes)
    taken = placed_drums(result)
    grid = Counter((note.note.channel, note.note.pitch, note.tick) for note in out.notes)
    for note in added:
        assert (note.family, note.piece, note.tick) not in taken
        assert grid[note.note.channel, note.note.pitch, note.tick] == 1
        assert out.creative[note.section] is not None


def by_key(notes: Sequence[RenderedNote], key: str) -> dict[object, list[RenderedNote]]:
    found: dict[object, list[RenderedNote]] = {}
    for note in notes:
        group = (
            (note.note.channel, note.note.pitch) if key == "pitch" else (note.family, note.piece)
        )
        found.setdefault(group, []).append(note)
    return found


@given(grooves(per_bar=16) | sparse_songs(), CUTS | SPARSE_CUTS, st.data())
def test_velocities_are_1_to_127_never_repeat_and_soft_notes_land_below_with_added_notes(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)

    out = rendered(midi, drawn_plan(data, midi, result, cuts))

    assert all(1 <= note.note.velocity <= 127 for note in out.notes)
    for key in ("pitch", "drum"):
        for notes in by_key(out.notes, key).values():
            for earlier, later in pairwise(notes):
                if not (earlier.kept and later.kept):
                    assert earlier.note.velocity != later.note.velocity
    places: dict[tuple[int, str, int], tuple[list[int], list[int]]] = {}
    for note in out.notes:
        if not note.kept:
            soft, other = places.setdefault((note.section, note.family, note.piece), ([], []))
            (soft if note.hit_type == "soft" else other).append(note.note.velocity)
    for soft, other in places.values():
        if soft and other:
            assert max(soft) < min(other)


EXTREMES = st.sampled_from((60.0, 600.0)) | TEMPOS
CHANGES = st.lists(
    st.tuples(st.integers(1, 64 * 12 - 1).map(lambda step: step * SIXTEENTH // 4), EXTREMES),
    max_size=40,
)
"""Tempo changes on 64ths of the first 12 bars, often 10 to 1 either way."""


def landing_tick(result: Normalized, start: int) -> float:
    tempos = result.score.tempos
    return max(tempos.ms_per_tick(max(start - 1, 0)), tempos.ms_per_tick(start))


@given(
    grooves((KICK, SNARE, HAT, CRASH, TOM_1), per_bar=24) | sparse_songs(),
    CUTS | SPARSE_CUTS,
    TEMPOS,
    CHANGES,
    LENGTHS,
    st.data(),
)
def test_added_notes_keep_their_pitch_s_order_gap_and_ends_and_the_cap(
    hits: list[Hit],
    cuts: list[int],
    bpm: float,
    changes: list[tuple[int, float]],
    length: int,
    data: st.DataObject,
) -> None:
    midi = song(hits, bpm=bpm, tempos=changes, length=length)
    result = normalized(midi)
    tempos = result.score.tempos

    out = rendered(midi, drawn_plan(data, midi, result, cuts, loose=True))

    for note in out.notes:
        if not note.kept:
            assert abs(note.offset_ms) <= CAP_MS + 2 * landing_tick(result, note.note.start)
    for notes in by_key(out.notes, "pitch").values():
        for earlier, later in pairwise(notes):
            if earlier.kept and later.kept:
                continue
            grid = tempos.tick_to_ms(later.tick) - tempos.tick_to_ms(earlier.tick)
            played = tempos.tick_to_ms(later.note.start) - tempos.tick_to_ms(earlier.note.start)
            rounding = (
                landing_tick(result, earlier.note.start) + landing_tick(result, later.note.start)
            ) / 2
            assert later.note.start > earlier.note.start
            assert played >= GAP_SHARE * grid - rounding - ROUNDING_MS
            if not earlier.kept:
                assert earlier.note.end <= later.note.start


@given(grooves(), CUTS, st.data())
def test_a_skipped_section_adds_nothing_and_comes_out_as_it_came_in(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    count = len(plan_for(midi, result, cuts=cuts).sections)
    kept = data.draw(st.integers(0, count - 1), label="kept")
    plan = plan_for(
        midi,
        result,
        cuts=cuts,
        controls=ON,
        sections={kept: ControlVector(skip=True, creative=True)},
    )

    out = rendered(midi, plan)

    assert out.creative[kept] is None
    mine = [note for note in out.notes if note.section == kept]
    assert all(note.kept and note.added is None for note in mine)
    for note in mine:
        source = result.score.notes[note.position].source
        assert (note.note.start, note.note.end, note.note.velocity) == (
            source.start,
            source.end,
            source.velocity,
        )


@st.composite
def played_twice(draw: st.DrawFn) -> tuple[list[Hit], list[Hit]]:
    """One groove played twice, with other velocities of the same types and other timing within
    6 ms."""
    hits = draw(grooves((KICK, SNARE, HAT, CRASH, TOM_1), max_bars=4))
    ranges = {SOFT: (20, 45), NORMAL: (55, 105), 120: (112, 127)}
    played: list[list[Hit]] = [[], []]
    for hit in hits:
        tick, pitch, kind = hit[0], hit[1], hit[2] if len(hit) == 3 else NORMAL
        for take in played:
            shift = round(draw(st.floats(-6, 6)) * PPQ / 500)
            take.append((tick + shift + 48, pitch, draw(st.integers(*ranges[kind]))))
    return played[0], played[1]


@given(played_twice(), CUTS, st.integers(0, 2**53 - 1))
def test_what_is_added_never_reads_the_input_s_velocities_or_timing(
    takes: tuple[list[Hit], list[Hit]], cuts: list[int], seed: int
) -> None:
    first, second = (song(take) for take in takes)
    one, two = normalized(first), normalized(second)

    def score(result: Normalized) -> list[tuple[int, str, str]]:
        return sorted((note.tick, note.articulation, note.hit_type) for note in result.score.notes)

    if score(one) != score(two):
        return
    plan = plan_for(first, one, cuts=cuts, controls=ON, seed=seed)

    assert midi_bytes(rendered(first, plan, result=one).song) == midi_bytes(
        rendered(second, plan, result=two).song
    )


def kinds(out: Rendered, section: int = 0) -> Counter[str]:
    return Counter(note.added for note in out.notes if note.section == section and note.added)


def test_a_fill_leads_into_the_next_section_where_there_is_none_but_not_after_the_last() -> None:
    midi = song(rock(8))
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result, cuts=[4], controls=ON))

    fills = [note for note in out.notes if note.added == "fill"]
    assert fills
    assert all(note.section == 0 for note in fills)
    assert {note.tick for note in fills} <= set(range(3 * BAR + 2 * PPQ, 4 * BAR, SIXTEENTH))
    assert all(note.part.role == "fill" and note.family == "snare" for note in fills)
    assert kinds(out, 1)["fill"] == 0


def test_a_section_with_a_fill_of_its_own_gets_none() -> None:
    fill: list[Hit] = [(3 * BAR + 2 * PPQ + step * SIXTEENTH, TOM_1) for step in range(8)]
    midi = song([*rock(8), *fill])
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result, cuts=[4], controls=ON))

    assert kinds(out)["fill"] == 0


def test_a_fill_runs_from_the_snare_down_the_toms_the_section_plays() -> None:
    toms: list[Hit] = [(PPQ // 2, TOM_1), (5 * PPQ // 2, TOM_2)]
    midi = song([*rock(8), *toms])
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result, cuts=[4], controls=ON))

    fills = sorted((note for note in out.notes if note.added == "fill"), key=lambda n: n.tick)
    drums = [(note.family, note.piece) for note in fills]
    assert drums == sorted(drums, key=lambda drum: (drum[0] != "snare", drum[1]))
    assert {("snare", 1), ("tom", 1), ("tom", 2)} <= set(drums)
    hands = [note.part.hand for note in fills]
    assert all(a == -b for a, b in pairwise(hands))
    rises = [note.part.crescendo for note in fills]
    assert rises == sorted(rises)
    assert (rises[0], rises[-1]) == (0, 1)


def sparse(bars: int) -> list[Hit]:
    """Kick and snare with hats on half notes: fewer cymbal hits than beats."""
    hits: list[Hit] = []
    for bar in range(bars):
        at = bar * BAR
        hits += [(at, KICK), (at + PPQ, SNARE), (at + 2 * PPQ, KICK), (at + 3 * PPQ, SNARE)]
        hits += [(at, HAT), (at + 2 * PPQ, HAT)]
    return [*hits, (0, CRASH)]


def test_a_section_with_few_cymbals_gets_crashes_each_4_bars_and_its_rider_on_each_beat() -> None:
    midi = song(sparse(8))
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result, controls=ON))

    crashes = [note for note in out.notes if note.added == "cymbal" and note.family == "crash"]
    riders = [note for note in out.notes if note.added == "cymbal" and note.family == "hat"]
    assert [note.tick for note in crashes] == [4 * BAR]
    assert all(note.part.role == "accent_cymbal" for note in crashes)
    assert {note.tick % (2 * PPQ) for note in riders} == {PPQ}
    assert all(note.part.role == "rider" for note in riders)


def test_a_section_with_a_cymbal_on_each_beat_gets_no_more() -> None:
    midi = song([*rock(8), (0, CRASH)])
    result = normalized(midi)

    assert kinds(rendered(midi, plan_for(midi, result, controls=ON)))["cymbal"] == 0


def test_ghost_notes_are_soft_between_8ths_and_follow_ghost_level() -> None:
    midi = song(rock(16))
    result = normalized(midi)
    levels: list[float] = []
    for ghost_level in (0.0, 1.0):
        controls = ControlVector(creative=True, ghost_level=ghost_level)
        out = rendered(midi, plan_for(midi, result, controls=controls))
        ghosts = [note for note in out.notes if note.added == "ghost"]
        assert ghosts
        assert all(note.hit_type == "soft" and note.family == "snare" for note in ghosts)
        assert all(note.tick % SIXTEENTH == 0 and note.tick % (2 * SIXTEENTH) for note in ghosts)
        levels.append(float(np.mean([note.note.velocity for note in ghosts])))
    assert levels[1] > levels[0]


def test_another_take_picks_other_ghost_notes() -> None:
    midi = song(rock(8))
    result = normalized(midi)
    plan = plan_for(midi, result, controls=ON)
    take = plan.model_copy(update={"sections": (plan.sections[0].model_copy(update={"take": 1}),)})

    def ghosts(out: Rendered) -> set[int]:
        return {note.tick for note in out.notes if note.added == "ghost"}

    assert ghosts(rendered(midi, plan)) != ghosts(rendered(midi, take))


def test_a_flam_is_a_soft_grace_just_before_the_last_backbeat_of_each_4_bars() -> None:
    midi = song(rock(8))
    result = normalized(midi)
    tempos = result.score.tempos

    out = rendered(midi, plan_for(midi, result, controls=ON))

    flams = sorted((note for note in out.notes if note.added == "flam"), key=lambda n: n.tick)
    mains = [3 * BAR + 3 * PPQ, 7 * BAR + 3 * PPQ]
    assert len(flams) == 2
    for flam, main in zip(flams, mains, strict=True):
        assert (flam.grace, flam.hit_type, flam.note.pitch) == (True, "soft", SNARE)
        assert tempos.tick_to_ms(main) - tempos.tick_to_ms(flam.tick) == pytest.approx(25, abs=1)
        played = next(note for note in out.notes if note.tick == main and note.family == "snare")
        assert flam.note.start < played.note.start
        assert flam.note.velocity < played.note.velocity


def test_rimshots_and_chokes_the_kit_lacks_are_skipped_and_counted() -> None:
    midi = song([*rock(8), (0, CRASH)])
    result = normalized(midi)

    out = rendered(midi, plan_for(midi, result, controls=ON))

    report = out.creative[0]
    assert report is not None
    assert report.skipped["missing"] == {"rimshot": 2, "choke": 1}
    assert kinds(out)["rimshot"] == kinds(out)["choke"] == 0


def test_a_rimshot_or_choke_on_a_pitch_the_section_doesn_t_play_is_skipped_and_counted() -> None:
    midi = song([*rock(8), (0, CRASH)])
    result = normalized(midi, SLEEP_TOKEN)

    out = rendered(
        midi,
        plan_for(midi, result, controls=ON),
        kit=SLEEP_TOKEN,
        target=SLEEP_TOKEN,
        result=result,
    )

    report = out.creative[0]
    assert report is not None
    assert report.skipped["unplayed"] == {"rimshot": 2, "choke": 1}


def test_a_section_that_plays_rimshots_and_chokes_gets_more_of_them() -> None:
    hits: list[Hit] = [*rock(8), (0, CRASH), (BAR, CHOKE), (6 * BAR, CRASH)]
    hits += [(bar * BAR + SIXTEENTH, RIMSHOT) for bar in range(8)]
    hits += [(bar * BAR, SNARE) for bar in range(8)]
    midi = song(hits)
    result = normalized(midi, SLEEP_TOKEN)
    plan = plan_for(midi, result, controls=ON)

    out = rendered(midi, plan, kit=SLEEP_TOKEN, target=SLEEP_TOKEN, result=result)
    base = rendered(
        midi, plan_for(midi, result), kit=SLEEP_TOKEN, target=SLEEP_TOKEN, result=result
    )

    rimshots = [note for note in out.notes if note.added == "rimshot"]
    assert [note.tick for note in rimshots] == [PPQ, 4 * BAR + PPQ]
    assert all(note.note.pitch == RIMSHOT and note.family == "snare" for note in rimshots)
    assert len(out.notes) == len(base.notes) + sum(
        count for kind, count in kinds(out).items() if kind != "rimshot"
    )
    chokes = [note for note in out.notes if note.added == "choke"]
    assert [(note.tick, note.note.pitch) for note in chokes] == [(6 * BAR + PPQ // 2, CHOKE)]


def test_generic_mode_adds_nothing() -> None:
    midi = song(rock(8))
    result = normalized(midi)
    placement = place_score(result.score, GM, GM)

    out = render(midi, result, placement, plan_for(midi, result, controls=ON), instrument=GENERIC)

    assert all(note.added is None for note in out.notes)
    assert out.creative[0] is not None
    assert not out.creative[0].added
