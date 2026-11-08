"""The built-in maps in `data/maps/`. They are in the repository, so these are ordinary tests."""

from collections import Counter
from itertools import product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.maps.convert import Row, convert
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_maps
from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import TimeSignatureMap

MAPS = built_in_maps()
KITS = list(MAPS)
GM = MAPS.kit("gm", "default")
SLEEP_TOKEN = MAPS.kit("sleep-token-ii", "default")
FOUR_FOUR = TimeSignatureMap(960, [])


def family(kit: DrumKit, note: Note) -> str:
    """The family of what the kit reads the note as. A note a controller value decides is one of
    several articulations, all in one family."""
    families = {
        kit.canonical(match.articulation.name).family
        for match in kit.read(note.pitch, note.velocity, note.channel)
    }
    assert len(families) == 1, (kit.ref, note)
    return families.pop()


def every_binding_note(kit: DrumKit) -> list[Note]:
    """A note for every binding of every articulation, at the middle of its velocity range."""
    notes: list[Note] = []
    for entry in kit.articulations:
        for binding in entry.bindings:
            channel = binding.channel or kit.spec.channel or 10
            notes.append(
                Note(
                    track=0,
                    channel=channel - 1,
                    pitch=binding.note,
                    start=len(notes) * 240,
                    end=len(notes) * 240 + 120,
                    velocity=sum(binding.velocity) // 2,
                    order=len(notes),
                )
            )
    return notes


def test_the_shipped_maps_load() -> None:
    assert {"gm", "sleep-token-ii"} <= {library.id for library in MAPS.libraries}
    assert all(library.schema_version == 1 for library in MAPS.libraries)


def test_every_general_midi_note_has_exactly_one_articulation() -> None:
    names = set()
    for pitch in range(35, 82):
        found = GM.resolve(pitch, 100, 9)
        assert found is not None, pitch
        assert found.label
        assert found.bindings[0].note == pitch
        names.add(found.name)
    assert len(names) == 47
    assert {binding.note for entry in GM.articulations for binding in entry.bindings} == set(
        range(35, 82)
    )
    assert GM.write("snare.2.center").pitch == 40
    assert GM.write("kick.2.hit").pitch == 35
    assert GM.write("hat.open").channel == 9


def test_the_sleep_token_map_has_its_68_pitches_as_58_articulations() -> None:
    pitches = [binding.note for entry in SLEEP_TOKEN.articulations for binding in entry.bindings]

    assert len(SLEEP_TOKEN.articulations) == 58
    assert len(pitches) == len(set(pitches)) == 68
    assert all(SLEEP_TOKEN.write(entry.name).channel == 9 for entry in SLEEP_TOKEN.articulations)
    assert all(entry.label for entry in SLEEP_TOKEN.articulations)
    flam, rimshot = SLEEP_TOKEN.resolve(39, 100, 9), SLEEP_TOKEN.resolve(40, 100, 9)
    assert (flam and flam.name, rimshot and rimshot.name) == ("snare.flam", "snare.rimshot")
    assert (SLEEP_TOKEN.pieces("tom"), SLEEP_TOKEN.pieces("crash")) == (3, 4)


@pytest.mark.parametrize("kit", KITS, ids=lambda kit: kit.ref)
def test_every_shipped_articulation_reads_back_from_what_is_written(kit: DrumKit) -> None:
    for entry in kit.articulations:
        output = kit.write(entry.name)
        channel = output.channel if output.channel is not None else 9
        if output.cc is None:
            assert kit.resolve(output.pitch, output.velocity[0], channel) == entry
        else:
            assert [match.articulation for match in kit.read(output.pitch, 100, channel)] == [entry]


def check_report(rows: tuple[Row, ...]) -> None:
    """Every inexact conversion lists its steps, and they lead from the source to the target."""
    for row in rows:
        if row.source == row.target:
            assert row.steps == (), row
            continue
        assert row.steps, row
        assert row.steps[0].asked == row.source
        assert row.steps[-1].used == row.target
        for step, following in zip(row.steps, row.steps[1:], strict=False):
            assert step.used == following.asked


@pytest.mark.parametrize(("source", "target"), list(product(KITS, KITS)), ids=lambda kit: kit.ref)
def test_converting_between_shipped_maps_never_changes_family(
    source: DrumKit, target: DrumKit
) -> None:
    notes = every_binding_note(source)

    conversion = convert(notes, source, target, FOUR_FOUR)

    held = {note.order for note in conversion.pending}
    kept = [note for note in notes if note.order not in held]
    assert len(conversion.notes) == len(kept)
    for before, after in zip(kept, conversion.notes, strict=True):
        assert family(source, before) == family(target, after), (before, after)
    check_report(conversion.rows)
    # Every note held back is in a decision request, and only those.
    asked_about = sum(int(str(request.details.get("count", 0))) for request in conversion.decisions)
    assert asked_about == len(conversion.pending)
    assert all(request.kind == "conversion" for request in conversion.decisions)


def test_general_midi_onto_sleep_token_ii_reports_each_step() -> None:
    notes = every_binding_note(GM)

    conversion = convert(notes, GM, SLEEP_TOKEN, FOUR_FOUR)

    moved = {row.source: row.target for row in conversion.inexact}
    assert moved == {
        "kick.2.hit": "kick.hit",
        "snare.2.center": "snare.center",
        "tom.2.hit": "tom.1.hit",
        "tom.3.hit": "tom.2.hit",
        "tom.4.hit": "tom.2.hit",
        "tom.5.hit": "tom.3.hit",
        "tom.6.hit": "tom.3.hit",
        "ride.2.bow": "ride.1.bow",
    }
    reasons = Counter(str(request.details["reason"]) for request in conversion.decisions)
    assert reasons == {"family": 26}


def test_sleep_token_ii_onto_general_midi_asks_about_chokes_cc_hats_and_missing_families() -> None:
    conversion = convert(every_binding_note(SLEEP_TOKEN), SLEEP_TOKEN, GM, FOUR_FOUR)

    asked = {str(request.details["source"]): request for request in conversion.decisions}
    assert {name for name in asked if asked[name].details["reason"] == "articulation"} == {
        "crash.1.choke",
        "crash.2.choke",
        "crash.3.choke",
        "crash.4.choke",
        "china.1.choke",
        "splash.1.choke",
        "splash.2.choke",
    }
    assert {name for name in asked if asked[name].details["reason"] == "cc"} == {
        "hat.variable",
        "hat.variable.tip",
    }
    families = {name for name in asked if asked[name].details["reason"] == "family"}
    assert families == {
        "sticks.hit",
        "stack.1.hit",
        "stack.1.hit.tip",
        "stack.2.hit",
        "stack.2.hit.tip",
    }
    assert [option.value for option in asked["sticks.hit"].options] == ["snare.sidestick", "drop"]
    assert [option.value for option in asked["stack.2.hit"].options] == ["china.1.hit", "drop"]
    flam = next(row for row in conversion.rows if row.source == "snare.flam")
    assert (flam.target, flam.steps[0].kind) == ("snare.center", "default")


@given(st.data())
def test_random_hits_never_change_family(data: st.DataObject) -> None:
    source = data.draw(st.sampled_from(KITS))
    target = data.draw(st.sampled_from(KITS))
    pool = every_binding_note(source)
    picked = data.draw(st.lists(st.sampled_from(pool), max_size=40))
    notes = [
        Note(
            track=0,
            channel=note.channel,
            pitch=note.pitch,
            start=index * 120,
            end=index * 120 + 60,
            velocity=data.draw(st.integers(1, 127)),
            order=index,
        )
        for index, note in enumerate(picked)
    ]

    conversion = convert(notes, source, target, FOUR_FOUR)

    assert len(conversion.notes) + len(conversion.pending) == len(notes)
    by_order = {note.order: note for note in notes}
    for after in conversion.notes:
        before = by_order[after.order]
        assert family(source, before) == family(target, after), (before, after)
        assert (after.start, after.end, after.track) == (before.start, before.end, before.track)
    check_report(conversion.rows)
