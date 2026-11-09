"""The controller guard: a controller-bound note keeps its controller's value (ADR 0053)."""

from pathlib import Path

import pytest

from grooves import BAR, PPQ, Hit, normalized, plan_for, rendered, song
from human_o_matic.controls import ControlVector
from human_o_matic.maps.kit import DrumKit
from human_o_matic.midi.io import MidiSong
from human_o_matic.render.engine import Rendered
from map_files import articulation, load_kit
from midi_files import cc

KICK, SNARE, VARIABLE, SELECTED = 36, 38, 32, 33


def value_at(midi: MidiSong, controller: int, tick: int, order: int) -> int | None:
    """The controller's value in force at a note-on at that tick and order on the drum track."""
    value: int | None = None
    for event in sorted(midi.events, key=lambda event: (event.tick, event.order)):
        ours = event.status & 0xF0 == 0xB0 and event.data[0] == controller
        if ours and (event.tick, event.order) < (tick, order):
            value = event.data[1]
    return value


def pedalled(pitch: int, *, extra: int = 1) -> MidiSong:
    """8th notes of `pitch` over a kick and snare, each played 20 ticks late, with a CC4 just
    before its grid point and another 100 ticks after it, and CC `extra` events between."""
    hits: list[Hit] = []
    events = []
    for eighth in range(32):
        at = eighth * PPQ // 2
        hits.append((at + 20, pitch))
        events.append((at - 2 if at else 0, cc(4, (eighth * 37) % 128)))
        events.append((at + 100, cc(4, (eighth * 53 + 7) % 128)))
        events.append((at + 60, cc(extra, eighth)))
    for bar in range(4):
        hits.extend([(bar * BAR, KICK), (bar * BAR + PPQ, SNARE)])
    return song(hits, events=sorted(events, key=lambda item: item[0]))


@pytest.fixture
def shaped(tmp_path: Path) -> DrumKit:
    return load_kit(
        tmp_path,
        articulation("kick.hit", KICK),
        articulation("snare.center", SNARE),
        articulation("hat.closed", 42),
        articulation("hat.variable", VARIABLE, cc={"mode": "shape"}),
        id="shaped",
    )


@pytest.fixture
def selected(tmp_path: Path) -> DrumKit:
    return load_kit(
        tmp_path,
        articulation("kick.hit", KICK),
        articulation("snare.center", SNARE),
        articulation(
            "hat.closed", SELECTED, cc={"mode": "select", "controller": 4, "values": [0, 63]}
        ),
        articulation(
            "hat.open", SELECTED, cc={"mode": "select", "controller": 4, "values": [64, 127]}
        ),
        id="selected",
    )


def render_loose(midi: MidiSong, kit: DrumKit, seed: int) -> Rendered:
    result = normalized(midi, kit)
    loose = ControlVector(tightness=0.0, feel=-1.0)
    return rendered(midi, plan_for(midi, result, controls=loose, seed=seed), kit=kit, target=kit)


@pytest.mark.parametrize("seed", range(6))
def test_a_note_a_controller_shapes_keeps_the_value_set_for_it(shaped: DrumKit, seed: int) -> None:
    midi = pedalled(VARIABLE)

    out = render_loose(midi, shaped, seed)

    sources = {(note.start, note.order): note for note in midi.notes if note.pitch == VARIABLE}
    played = [note for note in out.notes if note.note.pitch == VARIABLE]
    assert len(played) == len(sources)
    for note in played:
        source = next(s for s in sources.values() if s.order == note.note.order)
        for controller in (4, 1):
            assert value_at(midi, controller, note.note.start, note.note.order) == value_at(
                midi, controller, source.start, source.order
            )


def test_the_guard_moves_notes_that_would_cross_their_controller_events(shaped: DrumKit) -> None:
    midi = pedalled(VARIABLE)

    held = sum(render_loose(midi, shaped, seed).guards.controller for seed in range(6))

    assert held > 0


@pytest.mark.parametrize("seed", range(6))
def test_a_note_a_controller_selects_keeps_that_controller_s_value_only(
    selected: DrumKit, seed: int
) -> None:
    midi = pedalled(SELECTED)

    out = render_loose(midi, selected, seed)

    names = {note.articulation for note in normalized(midi, selected).score.notes}
    assert "hat.closed|hat.open" in names
    for note in out.notes:
        if note.note.pitch == SELECTED:
            source = next(s for s in midi.notes if s.order == note.note.order)
            assert value_at(midi, 4, note.note.start, note.note.order) == value_at(
                midi, 4, source.start, source.order
            )


def test_a_note_bound_to_no_controller_is_not_held(shaped: DrumKit) -> None:
    midi = pedalled(42)

    held = [render_loose(midi, shaped, seed).guards.controller for seed in range(6)]

    assert held == [0] * 6
