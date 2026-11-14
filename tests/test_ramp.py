"""Ramps: a section's last bars climbing, bar by bar, toward the energy the next section starts
at (ADR 0107). The properties are held by `hypothesis`, and examples hold the climb's sound in
numbers, its bounds and where no ramp plays."""

from itertools import pairwise

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from grooves import (
    ARCS,
    BAR,
    HAT,
    PPQ,
    SIXTEENTH,
    SNARE,
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
from human_o_matic.controls import (
    MAX_RAMP,
    Arc,
    Clamped,
    ControlInput,
    ControlVector,
    SessionPlan,
    StyleName,
    clamp,
    ramp_bars,
)
from human_o_matic.midi.io import MidiSong, midi_bytes
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.compiler import arc_energy, compile_section, ramped
from human_o_matic.render.engine import Rendered
from human_o_matic.render.measure import bar_velocities, mean_velocity
from human_o_matic.render.style import STYLE_NAMES, built_in_styles

CUTS = st.lists(st.integers(1, 5), max_size=3)
STYLES = st.sampled_from(STYLE_NAMES)
SEEDS = range(8)
"""Velocities are compared as means over these seeds."""
VERSE, CHORUS = 0.3, 0.9
RAMPS = st.integers(1, MAX_RAMP) | st.sampled_from((None, 0))
"""Ramps set most of the time, so the properties meet them often."""


@st.composite
def sectioned(draw: st.DrawFn) -> tuple[list[Hit], list[int]]:
    """Rock of 6 to 16 bars with a drawn groove over its first bars, and 1 to 3 cuts inside it,
    so it has 2 to 4 sections, often of several bars, which a ramp needs."""
    bars = draw(st.integers(6, 16))
    hits = [*rock(bars), *draw(grooves(max_bars=4))]
    cuts = draw(st.lists(st.integers(2, bars - 2), min_size=1, max_size=3, unique=True))
    return list({(hit[0], hit[1]): hit for hit in hits}.values()), cuts


def ramping(data: st.DataObject, count: int, *, skip: bool = True) -> dict[int, ControlVector]:
    """Each section's controls drawn, `skip` among them when `skip` is set, with a ramp most of
    the time, and half the time energies rising from section to section, so ramps play."""
    rising = data.draw(st.booleans(), label="rising")
    energies = sorted(data.draw(st.lists(st.floats(0, 1), min_size=count, max_size=count)))
    out: dict[int, ControlVector] = {}
    for number in range(count):
        drawn = data.draw(control_vectors(skip=skip), label=f"section {number}")
        update: dict[str, object] = {"ramp": data.draw(RAMPS, label=f"ramp {number}")}
        if rising:
            update["energy"] = energies[number]
        out[number] = drawn.model_copy(update=update)
    return out


def with_fill(bars: int, fill_bar: int) -> list[Hit]:
    """Rock for `bars` bars, with a fill of 16ths over the last two beats of `fill_bar`: snare,
    then the toms."""
    at = fill_bar * BAR + 2 * PPQ
    fill = [SNARE, SNARE, TOM_1, TOM_1, TOM_2, TOM_2, TOM_2, TOM_2]
    hits = [
        hit for hit in rock(bars) if not (at <= hit[0] < at + 2 * PPQ and hit[1] in (SNARE, HAT))
    ]
    return hits + [(at + step * SIXTEENTH, pitch) for step, pitch in enumerate(fill)]


def verse_and_chorus(
    midi: MidiSong,
    result: Normalized,
    ramp: int | None,
    *,
    verse: ControlVector | None = None,
    chorus: ControlVector | None = None,
    seed: int = 1,
    cut: int = 8,
) -> SessionPlan:
    """A verse at `VERSE` to bar `cut` with the ramp given, then a chorus at `CHORUS`."""
    return plan_for(
        midi,
        result,
        cuts=[cut],
        sections={
            0: (verse or ControlVector(energy=VERSE)).model_copy(update={"ramp": ramp}),
            1: chorus or ControlVector(energy=CHORUS),
        },
        seed=seed,
    )


def bar_means(midi: MidiSong, result: Normalized, ramp: int, bars: range) -> list[float]:
    """The normal notes' mean velocity in each of `bars`, averaged over `SEEDS`."""
    ticks = [bar * BAR for bar in range(bars.start, bars.stop + 1)]
    means = np.zeros(len(bars))
    for seed in SEEDS:
        plan = verse_and_chorus(midi, result, ramp, seed=seed)
        found = bar_velocities(rendered(midi, plan, result=result).notes, ticks)
        means += np.array(found, dtype=np.float64) / len(SEEDS)
    return [float(mean) for mean in means]


@given(grooves(), CUTS, st.data())
def test_a_ramp_of_0_renders_every_byte_as_without_the_control(
    hits: list[Hit], cuts: list[int], data: st.DataObject
) -> None:
    midi = song(hits)
    result = normalized(midi)
    count = len(plan_for(midi, result, cuts=cuts).sections)
    controls = {
        number: data.draw(control_vectors(corners=True, creative=True), label=f"section {number}")
        for number in range(count)
    }
    style = data.draw(STYLES, label="style")
    seed = data.draw(st.integers(0, 2**53 - 1), label="seed")
    zeroed = data.draw(st.sets(st.integers(0, count - 1)), label="ramp 0")
    song_zero = data.draw(st.booleans(), label="song ramp 0")
    unset = plan_for(midi, result, cuts=cuts, sections=controls, style=style, seed=seed)
    zero = plan_for(
        midi,
        result,
        cuts=cuts,
        sections={
            number: vector.model_copy(update={"ramp": 0}) if number in zeroed else vector
            for number, vector in controls.items()
        },
        controls=ControlVector(ramp=0) if song_zero else None,
        style=style,
        seed=seed,
    )

    out = rendered(midi, zero, result=result)

    assert midi_bytes(out.song) == midi_bytes(rendered(midi, unset, result=result).song)
    assert out.ramps == (None,) * count


@given(
    st.floats(0, 1),
    st.sampled_from(ARCS),
    st.floats(0.01, 1.3),
    st.integers(1, MAX_RAMP),
    st.integers(2, 64),
    STYLES,
)
def test_a_ramp_climbs_each_bar_more_than_the_last_from_the_arc_to_a_step_below_its_target(
    energy: float, arc: Arc, rise: float, ramp: int, bars: int, style: StyleName
) -> None:
    # Bar k of n plays (k / (n + 1)) ** 2 of the way from where the arc leaves the section to
    # the target: so each step, the one into the next section's downbeat too, is bigger than the
    # step before it, and the last ramp bar is a step below the target.
    styled = built_in_styles()[style]
    params = compile_section(
        styled.defaults.model_copy(update={"energy": energy, "arc": arc}), styled, 120
    )
    count = ramp_bars(ramp, bars)
    assume(count > 0)
    first = bars - count
    places = [(first + step) / bars for step in range(count)]
    begin = params.energy_at(places[0])
    target = begin + rise

    out = ramped(params, first, [bar * BAR for bar in range(first, bars + 1)], places, target)

    assert out.ramp is not None
    energies = out.ramp.energies
    steps = np.diff([begin, *energies, target])
    assert all(step > 0 for step in steps)
    assert all(later > earlier for earlier, later in pairwise(steps))
    assert begin < energies[0]
    assert energies[-1] < target
    for step, place in enumerate(places):
        within = (place + (places[step + 1] if step + 1 < count else 1.0)) / 2
        assert out.energy_at(place) == out.energy_at(within) == energies[step]
    before = places[0] / 2
    assert out.energy_at(before) == params.energy_at(before)
    assert ramped(params, first, [], places, begin) is params
    assert ramped(params, first, [], places, begin - rise) is params


@given(sectioned(), st.data())
def test_a_ramp_plays_over_its_bars_into_a_higher_next_section_that_plays_and_isn_t_skipped(
    drawn: tuple[list[Hit], list[int]], data: st.DataObject
) -> None:
    hits, cuts = drawn
    midi = song(hits)
    result = normalized(midi)
    count = len(plan_for(midi, result, cuts=cuts).sections)
    style = data.draw(STYLES, label="style")
    plan = plan_for(midi, result, cuts=cuts, sections=ramping(data, count), style=style)
    defaults = built_in_styles()[style].defaults

    out = rendered(midi, plan, result=result)

    playing = {note.section for note in out.notes}
    for number, (section, ramp) in enumerate(zip(plan.sections, out.ramps, strict=True)):
        now = plan.controls_of(section, defaults)
        bars = ramp_bars(now.ramp, section.bars)
        after = plan.sections[number + 1] if number + 1 < count else None
        then = plan.controls_of(after, defaults) if after is not None else None
        if not bars or now.skip or then is None or then.skip or number + 1 not in playing:
            assert ramp is None
            continue
        span = built_in_styles()[style].arc_span
        target = arc_energy(then.energy, then.arc, span, 0.0)
        begin = arc_energy(now.energy, now.arc, span, (section.bars - bars) / section.bars)
        if target <= begin:
            assert ramp is None
            continue
        assert ramp is not None
        assert ramp.bar == section.end - bars
        assert len(ramp.energies) == bars
        assert ramp.target == target
        assert all(begin < energy < target for energy in ramp.energies)
        assert all(later > earlier for earlier, later in pairwise(ramp.energies))


@given(sectioned(), st.data())
def test_one_section_again_leaves_every_other_as_it_was_but_a_ramp_into_new_controls(
    drawn: tuple[list[Hit], list[int]], data: st.DataObject
) -> None:
    hits, cuts = drawn
    midi = song(hits)
    result = normalized(midi)
    count = len(plan_for(midi, result, cuts=cuts).sections)
    style = data.draw(STYLES, label="style")
    controls = ramping(data, count, skip=False)
    plan = plan_for(midi, result, cuts=cuts, sections=controls, style=style)
    # Drawn from the last, so the section before it, which may ramp into it, is often there.
    changed = data.draw(st.integers(0, count - 1).map(lambda n: count - 1 - n), label="section")
    new = data.draw(st.booleans(), label="new controls")
    vector = ramping(data, 1, skip=False)[0] if new else controls[changed]
    take = data.draw(st.integers(0, 2), label="take")
    again = plan.model_copy(
        update={
            "sections": tuple(
                section.model_copy(update={"controls": vector, "take": take})
                if number == changed
                else section
                for number, section in enumerate(plan.sections)
            )
        }
    )
    defaults = built_in_styles()[style].defaults
    before = plan.sections[changed - 1] if changed else None
    # The section before follows the changed one's energy and arc when it ramps, and only then.
    follows = (
        new
        and before is not None
        and ramp_bars(plan.controls_of(before, defaults).ramp, before.bars) > 0
    )
    moved = {changed, changed - 1} if follows else {changed}

    first = {note.position: note.note for note in rendered(midi, plan, result=result).notes}
    second = rendered(midi, again, result=result).notes

    assert {
        note.position: note.note for note in second if note.section not in moved
    }.items() <= first.items()


def test_the_bars_of_a_ramp_rise_slowly_then_faster_and_stay_below_the_next_section() -> None:
    midi = song(rock(12))
    result = normalized(midi)

    for ramp in (2, 4):
        means = bar_means(midi, result, ramp, range(7 - ramp, 9))
        _, *climbing, chorus = means
        steps = np.diff(means)
        assert all(step > 0 for step in steps), means
        assert climbing[-1] < chorus
        assert steps[0] < steps[-2], means
    flat = bar_means(midi, result, 0, range(4, 8))
    assert max(flat) - min(flat) < 1.5, flat


def test_a_ramp_starts_from_where_an_arc_leaves_the_section() -> None:
    midi = song(rock(12))
    result = normalized(midi)
    build = ControlVector(energy=VERSE, arc="build")

    plan = verse_and_chorus(midi, result, 4, verse=build)
    (ramp, _) = rendered(midi, plan, result=result).ramps

    assert ramp is not None
    span = built_in_styles()["tight"].arc_span
    begin = arc_energy(VERSE, "build", span, 4 / 8)
    assert ramp.energies[0] == pytest.approx(begin + (CHORUS - begin) / 25)
    assert ramp.target == CHORUS


def test_a_ramp_aims_at_where_the_next_section_s_arc_starts_it() -> None:
    midi = song(rock(12))
    result = normalized(midi)
    building = ControlVector(energy=CHORUS, arc="build")

    plan = verse_and_chorus(midi, result, 2, chorus=building)
    (ramp, _) = rendered(midi, plan, result=result).ramps

    assert ramp is not None
    assert ramp.target == pytest.approx(CHORUS - built_in_styles()["tight"].arc_span)


def test_a_fill_in_the_last_ramp_bar_builds_with_it() -> None:
    midi = song(with_fill(12, 7))
    result = normalized(midi)

    for seed in SEEDS:
        fills = [
            mean_velocity(
                [
                    note
                    for note in rendered(
                        midi, verse_and_chorus(midi, result, ramp, seed=seed), result=result
                    ).notes
                    if note.part.role == "fill"
                ]
            )
            for ramp in (0, 2)
        ]
        flat, ramped_fill = fills
        assert flat is not None
        assert ramped_fill is not None
        assert ramped_fill > flat + 2


def test_a_fill_creative_mode_adds_builds_with_the_ramp() -> None:
    midi = song(rock(12))
    result = normalized(midi)
    creative = ControlVector(energy=VERSE, creative=True)

    for seed in SEEDS:
        added: list[float] = []
        for ramp in (0, 2):
            plan = verse_and_chorus(midi, result, ramp, verse=creative, seed=seed)
            notes = rendered(midi, plan, result=result).notes
            mean = mean_velocity([note for note in notes if note.added == "fill"])
            assert mean is not None
            added.append(mean)
        assert added[1] > added[0] + 2


def test_a_ramp_uses_at_most_half_its_section_and_8_bars() -> None:
    midi = song(rock(22))
    result = normalized(midi)

    def bars(ramp: int, cut: int) -> int:
        plan = verse_and_chorus(midi, result, ramp, cut=cut)
        (found, _) = rendered(midi, plan, result=result).ramps
        assert found is not None
        return len(found.energies)

    assert bars(8, 6) == 3
    assert bars(5, 16) == 5
    assert bars(8, 18) == 8
    assert ramp_bars(8, 1) == 0
    assert clamp(ControlInput(ramp=12)) == (
        ControlVector(ramp=8),
        (Clamped(control="ramp", given=12, used=8),),
    )
    assert clamp(ControlInput(ramp=-1))[0] == ControlVector(ramp=0)
    assert clamp(ControlInput(ramp=2.6)) == (
        ControlVector(ramp=3),
        (Clamped(control="ramp", given=2.6, used=3),),
    )
    assert clamp(ControlInput(ramp=4.0)) == (ControlVector(ramp=4), ())


def no_ramp(midi: MidiSong, result: Normalized, plan: SessionPlan) -> None:
    """The plan plays no ramp, and its bytes are those of the plan with every ramp at 0."""
    out: Rendered = rendered(midi, plan, result=result)
    zero = plan.model_copy(
        update={
            "sections": tuple(
                section.model_copy(
                    update={"controls": section.controls.model_copy(update={"ramp": 0})}
                )
                for section in plan.sections
            )
        }
    )
    assert all(ramp is None for ramp in out.ramps)
    assert midi_bytes(out.song) == midi_bytes(rendered(midi, zero, result=result).song)


def test_no_ramp_plays_into_a_skipped_silent_or_quieter_section_or_out_of_the_last() -> None:
    midi = song(rock(12))
    result = normalized(midi)
    gap = song([hit for hit in rock(16) if not 8 * BAR <= hit[0] < 12 * BAR])
    gapped = normalized(gap)
    ramp = ControlVector(energy=VERSE, ramp=4)

    no_ramp(midi, result, verse_and_chorus(midi, result, 4, chorus=ControlVector(skip=True)))
    no_ramp(midi, result, verse_and_chorus(midi, result, 4, chorus=ControlVector(energy=VERSE)))
    no_ramp(midi, result, verse_and_chorus(midi, result, 4, chorus=ControlVector(energy=0.1)))
    no_ramp(midi, result, plan_for(midi, result, controls=ramp))
    no_ramp(
        gap,
        gapped,
        plan_for(
            gap,
            gapped,
            cuts=[8, 12],
            sections={0: ramp, 1: ControlVector(energy=CHORUS), 2: ControlVector(energy=CHORUS)},
        ),
    )


def test_a_song_wide_ramp_builds_each_section_into_a_louder_next_one() -> None:
    midi = song(rock(12))
    result = normalized(midi)
    plan = plan_for(
        midi,
        result,
        cuts=[4, 8],
        controls=ControlVector(ramp=2),
        sections={0: ControlVector(energy=VERSE), 1: ControlVector(energy=CHORUS)},
    )

    ramps = rendered(midi, plan, result=result).ramps

    assert ramps[0] is not None
    assert ramps[0].bar == 2
    assert ramps[1:] == (None, None)
