"""The engine's part of the M3 exit: raising each control moves its statistic the right way
(ADR 0052).

One groove built in code has every role: kick with a bar of double kick, backbeats with soft
notes between them, 8th hats, a crash on each downbeat and a fill at the end of every second
bar. The accents are on the kick's first beat and the snare's second backbeat, never on a
rider, so the accent contrast moves only by the accent term and not by the riders' gap.

Each control is set to a range of values with the others at their defaults, and the statistic it
mainly drives, averaged over seeds, must move strictly the right way, and by at least `MIN_RISE`
from end to end. The same seeds draw at every value, so only the control changes. Then a draw's
noise, which `dynamic_range` scales, moves a difference of means by a fraction of a step, and
the least rise keeps that from passing for the control's own effect.
"""

from collections.abc import Callable, Sequence
from functools import cache
from itertools import pairwise

import pytest

from grooves import (
    ACCENT,
    BAR,
    CRASH,
    HAT,
    KICK,
    PPQ,
    SIXTEENTH,
    SNARE,
    SOFT,
    TOM_1,
    TOM_2,
    Hit,
    normalized,
    plan_for,
    rendered,
    song,
)
from human_o_matic.controls import ControlVector, StyleName
from human_o_matic.midi.io import MidiSong
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import RenderedNote
from human_o_matic.render.measure import (
    accent_contrast,
    feel_offset,
    fill_rise,
    mean_velocity,
    rider_gap,
    timing_spread,
    velocity_spread,
    velocity_trend,
)
from human_o_matic.render.style import STYLE_NAMES, built_in_styles

SEEDS = range(1, 7)
MIN_RISE = 2.0
"""The least a statistic moves from one end of its control to the other, in velocity steps."""
UNIT = (0.0, 0.25, 0.5, 0.75, 1.0)

type Statistic = Callable[[Sequence[RenderedNote]], float | None]


@cache
def groove() -> tuple[MidiSong, Normalized]:
    hits: list[Hit] = []
    for bar in range(16):
        at = bar * BAR
        hits.append((at, CRASH))
        hits.extend([(at, KICK, ACCENT), (at + 2 * PPQ, KICK)])
        hits.extend([(at + PPQ, SNARE), (at + 3 * PPQ, SNARE, ACCENT)])
        hits.append((at + 6 * SIXTEENTH, SNARE, SOFT))
        hits.extend((at + eighth * PPQ // 2, HAT) for eighth in range(8))
        if bar % 4 == 1:
            hits.extend((at + 2 * PPQ + step * SIXTEENTH, KICK) for step in range(1, 8))
        if bar % 2 == 1:
            fill = ((4, SNARE), (3, SNARE), (2, TOM_1), (1, TOM_2))
            hits.extend((at + BAR - step * SIXTEENTH, pitch) for step, pitch in fill)
    midi = song(hits)
    return midi, normalized(midi)


@pytest.fixture(params=STYLE_NAMES)
def style(request: pytest.FixtureRequest) -> StyleName:
    """Every control moves its statistic in every style."""
    return request.param


def measured(controls: ControlVector, statistic: Statistic, style: StyleName) -> float:
    """The statistic over the whole song, averaged over the seeds."""
    midi, result = groove()
    values: list[float] = []
    for seed in SEEDS:
        plan = plan_for(midi, result, controls=controls, seed=seed, style=style)
        out = rendered(midi, plan, result=result)
        value = statistic(out.notes)
        assert value is not None
        values.append(value)
    return sum(values) / len(values)


def soft(notes: Sequence[RenderedNote]) -> float | None:
    return mean_velocity(notes, hit_types=("soft",))


def normal(notes: Sequence[RenderedNote]) -> float | None:
    return mean_velocity(notes)


def fills(notes: Sequence[RenderedNote]) -> float | None:
    return mean_velocity(notes, roles=("fill",))


def snare(notes: Sequence[RenderedNote]) -> float | None:
    return mean_velocity(notes, families=("snare",))


def rises(values: Sequence[float]) -> bool:
    return all(earlier < later for earlier, later in pairwise(values))


@pytest.mark.parametrize(
    ("control", "statistic"),
    [
        ("energy", normal),
        ("groove", accent_contrast),
        ("groove", soft),
        ("groove", rider_gap),
        ("dynamic_range", rider_gap),
        ("dynamic_range", velocity_spread),
        ("fill_intensity", fills),
        ("fill_intensity", fill_rise),
        ("ghost_level", soft),
    ],
)
def test_raising_a_control_raises_its_statistic(
    control: str, statistic: Statistic, style: StyleName
) -> None:
    values = [
        measured(ControlVector.model_validate({control: value}), statistic, style) for value in UNIT
    ]

    assert rises(values), values
    assert values[-1] - values[0] >= MIN_RISE, values


def test_raising_tightness_narrows_the_timing_spread(style: StyleName) -> None:
    values = [measured(ControlVector(tightness=value), timing_spread, style) for value in UNIT]

    assert rises(values[::-1]), values


def test_feel_moves_the_snare_and_riders_later_and_louder_when_laid_back(
    style: StyleName,
) -> None:
    feels = (-1.0, -0.5, 0.0, 0.5, 1.0)
    offsets = [measured(ControlVector(feel=value), feel_offset, style) for value in feels]
    loudness = [measured(ControlVector(feel=value), snare, style) for value in feels[2:]]
    laid_back, pushed = built_in_styles()[style].feel_ms

    assert rises(offsets), offsets
    assert rises(loudness), loudness
    # The laid-back side is to the pushed side as the style's are.
    assert offsets[-1] - offsets[2] > laid_back / pushed * (offsets[2] - offsets[0]) - 1


def test_an_arc_builds_or_drops_the_velocity_across_a_section(style: StyleName) -> None:
    trends = [
        measured(ControlVector(arc=arc), velocity_trend, style)
        for arc in ("drop", "steady", "build")
    ]

    assert rises(trends), trends
