"""Drum songs built in code for the engine's tests: notes at ticks, read through the GM map."""

from collections.abc import Iterable, Mapping, Sequence
from itertools import pairwise

from hypothesis import strategies as st

from human_o_matic.analyze.sections import drum_bars
from human_o_matic.controls import Arc, ControlVector, SectionPlan, SessionPlan
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiSong, parse_midi
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.pipeline import normalize
from human_o_matic.normalize.score import Normalized
from human_o_matic.render.engine import Rendered, render
from human_o_matic.render.target import place_score
from midi_files import MidoMessage, build, end, name, off, on, signature, tempo, track

GM = find_kit("gm")
PPQ = 960
SIXTEENTH = PPQ // 4
BAR = 4 * PPQ
KICK, SNARE, SIDESTICK, HAT, PEDAL, OPEN_HAT = 36, 38, 37, 42, 44, 46
RIDE, BELL, CRASH, CHINA, COWBELL = 51, 53, 49, 52, 56
TOM_1, TOM_2, TOM_3 = 50, 48, 47
SOFT, NORMAL, ACCENT = 30, 90, 120
"""Input velocities that `TYPED` reads as soft, normal and accent."""
TYPED = HitTypeBounds(soft_below=50, accent_from=110)
FAMILIES = ("kick", "snare", "hat", "ride", "crash", "china", "tom", "cowbell")

type Hit = tuple[int, int] | tuple[int, int, int]
"""`(tick, pitch)` at `NORMAL`, or `(tick, pitch, velocity)`."""


def midi_file(
    hits: Iterable[Hit],
    *,
    bpm: float = 120,
    tempos: Sequence[tuple[int, float]] = (),
    signatures: Sequence[tuple[int, int, int]] = (),
    length: int = 10,
    events: Sequence[tuple[int, MidoMessage]] = (),
) -> bytes:
    """The bytes of a one-track song at 960 PPQ. `tempos` are `(tick, bpm)` changes after the
    first, `signatures` are `(tick, numerator, denominator)`, each note lasts `length` ticks, and
    `events` are other messages at their ticks."""
    items: list[tuple[int, int, MidoMessage]] = [(0, 0, name("Drums")), (0, 0, tempo(bpm))]
    items.extend((tick, 0, tempo(value)) for tick, value in tempos)
    items.extend((tick, 0, signature(top, bottom)) for tick, top, bottom in signatures)
    items.extend((tick, 1, message) for tick, message in events)
    for hit in hits:
        tick, pitch = hit[0], hit[1]
        velocity = hit[2] if len(hit) == 3 else NORMAL
        items.extend([(tick, 3, on(pitch, velocity)), (tick + length, 2, off(pitch))])
    items.sort(key=lambda item: (item[0], item[1]))
    messages = [(tick, message) for tick, _, message in items]
    return build(track(*messages, (messages[-1][0], end())), ppq=PPQ)


def song(
    hits: Iterable[Hit],
    *,
    bpm: float = 120,
    tempos: Sequence[tuple[int, float]] = (),
    signatures: Sequence[tuple[int, int, int]] = (),
    length: int = 10,
    events: Sequence[tuple[int, MidoMessage]] = (),
) -> MidiSong:
    """`midi_file`'s song, read back."""
    data = midi_file(
        hits, bpm=bpm, tempos=tempos, signatures=signatures, length=length, events=events
    )
    return parse_midi(data)


def normalized(midi: MidiSong, kit: DrumKit = GM) -> Normalized:
    """The song normalized with every family it has typed by `TYPED`, so no request is open."""
    families = {note.family for note in normalize(midi, kit).score.notes}
    result = normalize(midi, kit, hit_types=dict.fromkeys(families, TYPED))
    assert result.complete
    return result


def rock(bars: int, *, start: int = 0) -> list[Hit]:
    """Kick on 1 and 3, snare on 2 and 4, 8th hats, from bar `start`."""
    hits: list[Hit] = []
    for bar in range(start, start + bars):
        at = bar * BAR
        hits.extend([(at, KICK), (at + 2 * PPQ, KICK), (at + PPQ, SNARE), (at + 3 * PPQ, SNARE)])
        hits.extend((at + eighth * PPQ // 2, HAT) for eighth in range(8))
    return hits


def plan_for(
    midi: MidiSong,
    result: Normalized,
    *,
    cuts: Iterable[int] = (),
    sections: Mapping[int, ControlVector] | None = None,
    controls: ControlVector | None = None,
    seed: int = 1,
) -> SessionPlan:
    """A plan whose sections start at bar 0 and at each cut inside the drums' bars, with the
    controls `sections` gives by section number."""
    bars = drum_bars(midi, result.score)
    edges = sorted({0, bars, *(cut for cut in cuts if 0 < cut < bars)})
    given = sections or {}
    return SessionPlan(
        seed=seed,
        controls=controls or ControlVector(),
        sections=tuple(
            SectionPlan(
                start=start,
                bars=end - start,
                group="A",
                controls=given.get(number, ControlVector()),
            )
            for number, (start, end) in enumerate(pairwise(edges))
        ),
    )


def rendered(
    midi: MidiSong,
    plan: SessionPlan,
    *,
    kit: DrumKit = GM,
    target: DrumKit = GM,
    substitutions: Mapping[str, str] | None = None,
    result: Normalized | None = None,
) -> Rendered:
    """The song rendered by the plan, read with `kit` and written to `target`."""
    result = result or normalized(midi, kit)
    placement = place_score(result.score, kit, target, substitutions)
    assert placement.complete, placement.decisions
    return render(midi, result, placement, plan)


PITCHES = (KICK, SNARE, SIDESTICK, HAT, PEDAL, OPEN_HAT, RIDE, BELL, CRASH, CHINA, TOM_1, TOM_2)


@st.composite
def grooves(
    draw: st.DrawFn,
    pitches: Sequence[int] = PITCHES,
    max_bars: int = 6,
    velocities: Sequence[int] = (SOFT, NORMAL, ACCENT),
    per_bar: int = 12,
) -> list[Hit]:
    """Hits on the 16th grid of up to `max_bars` bars, at most `per_bar` to a bar, each soft,
    normal or accent."""
    bars = draw(st.integers(1, max_bars))
    hits = draw(
        st.lists(
            st.tuples(
                st.integers(0, 16 * bars - 1),
                st.sampled_from(pitches),
                st.sampled_from(velocities),
            ),
            min_size=1,
            max_size=per_bar * bars,
            unique_by=lambda hit: (hit[0], hit[1]),
        )
    )
    return [(step * SIXTEENTH, pitch, velocity) for step, pitch, velocity in hits]


GRACE_GAPS = st.integers(10, 86)
"""A grace's gap before its main, in ticks: 5 to 45 ms at 120 BPM."""
FIRST_GAPS = st.integers(10, 40)
"""A flam's gap on the song's first tick, in ticks: 5 to 21 ms at 120 BPM, on either side of
the cap."""


@st.composite
def flams(draw: st.DrawFn, groove: st.SearchStrategy[list[Hit]]) -> list[Hit]:
    """A groove with a soft grace before up to 4 of its hits, on their pitch, and half the time
    a flam on the song's first tick. A grace can't go before tick 0, so that flam's grace is on
    tick 0 and its main is played late by the gap, which the score reads on tick 0 as well."""
    hits = draw(groove)
    graced = draw(st.sets(st.integers(0, len(hits) - 1), max_size=4))
    out: list[Hit] = []
    for number, hit in enumerate(hits):
        if number in graced and hit[0] > 0:
            out.append((hit[0] - draw(GRACE_GAPS), hit[1], SOFT))
        out.append(hit)
    if draw(st.booleans()):
        pitch = draw(st.sampled_from(sorted({hit[1] for hit in hits})))
        out = [hit for hit in out if (hit[0], hit[1]) != (0, pitch)]
        out.extend([(0, pitch, SOFT), (draw(FIRST_GAPS), pitch, NORMAL)])
    return out


TEMPOS = st.just(600.0) | st.floats(60, 600)
"""Tempos up to 600 BPM, half of them at 600, where a 16th is 25 ms and the 60% gap binds."""
LENGTHS = st.sampled_from((10, 2 * BAR)) | st.integers(1, 2 * BAR)
"""Note lengths up to 2 bars, so notes on one pitch overlap and their ends are trimmed."""


_units = st.none() | st.floats(0, 1)
_corners = st.none() | st.sampled_from((0.0, 1.0)) | st.floats(0, 1)
"""Controls that reach their ends often, where the guards bind."""
ARCS: tuple[Arc, ...] = ("steady", "build", "drop")


@st.composite
def control_vectors(draw: st.DrawFn, skip: bool = True, corners: bool = False) -> ControlVector:
    """Any controls, each maybe unset, with `skip` drawn only when `skip` is set, and each at
    its ends often when `corners` is set."""
    units = _corners if corners else _units
    feel = st.none() | st.sampled_from((-1.0, 1.0)) | st.floats(-1, 1) if corners else None
    return ControlVector(
        energy=draw(units),
        groove=draw(units),
        dynamic_range=draw(units),
        tightness=draw(units),
        feel=draw(feel if feel is not None else st.none() | st.floats(-1, 1)),
        arc=draw(st.none() | st.sampled_from(ARCS)),
        fill_intensity=draw(units),
        ghost_level=draw(units),
        skip=draw(st.none() | st.booleans()) if skip else None,
    )
