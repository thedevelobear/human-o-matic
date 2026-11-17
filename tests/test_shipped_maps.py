"""The built-in maps in `data/maps/`. They are in the repository, so these are ordinary tests."""

from collections import Counter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from drumverter_maps import read_pins
from human_o_matic.maps.convert import DROP, Row, convert
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_maps
from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import TimeSignatureMap
from human_o_matic.resources import data_dir

MAPS = built_in_maps()
KITS = list(MAPS)
GM = MAPS.kit("gm", "default")
SLEEP_TOKEN = MAPS.kit("sleep-token-ii", "default")
LOGIC = MAPS.kit("logic-pro-drums", "default")
DRUMMER = MAPS.kit("iof-drummer", "default")
FOUR_FOUR = TimeSignatureMap(960, [])
FROM_DRUMVERTER = {
    library.id: tuple(kit.id for kit in library.kits) for library in read_pins().libraries
}
"""The libraries tools/drumverter_maps.py builds from drumverter's note maps (ADR 0137)."""
SHIPPED = {
    "gm": ("default",),
    "sleep-token-ii": ("default", "groove-pack"),
    "iof-drummer": ("default", "old"),
    "logic-pro-drums": ("default",),
    "garageband-drums": ("default",),
    "counterkit": ("default",),
    "ni-drum-lab": ("default",),
    "krimh-drums": ("default",),
    "ggd-matt-halpern": ("default",),
} | FROM_DRUMVERTER
NEW_IN_M3 = {
    # library: (articulations, pitches, the notes of its mapping it leaves out) (ADR 0055).
    # Counterkit's 64 and 65 and NI Drum Lab's 62 and 63 take drumverter's names (ADR 0140), and
    # Krimh Drums follows the instrument's mapping page (ADR 0139).
    "counterkit": (22, 22, ()),
    "ni-drum-lab": (32, 39, ()),
    "krimh-drums": (44, 50, (17, 37)),
    "ggd-matt-halpern": (22, 22, ()),
}


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


def note(pitch: int, start: int = 0, channel: int = 9) -> Note:
    return Note(track=0, channel=channel, pitch=pitch, start=start, end=start + 120, velocity=100)


def test_the_shipped_maps_load_one_library_per_file() -> None:
    kits = {library.id: tuple(kit.id for kit in library.kits) for library in MAPS.libraries}

    assert kits == SHIPPED
    assert len(SHIPPED) == 117
    assert len(sorted((data_dir() / "maps").glob("*.toml"))) == len(SHIPPED)
    assert all(library.schema_version == 1 for library in MAPS.libraries)


@pytest.mark.parametrize("kit", KITS, ids=lambda kit: kit.ref)
def test_an_inferred_name_ships_at_low_confidence(kit: DrumKit) -> None:
    for entry in kit.articulations:
        if entry.source == "inferred":
            assert entry.confidence == "low", entry.name


@pytest.mark.parametrize("kit", KITS, ids=lambda kit: kit.ref)
def test_a_shipped_note_has_a_label_only_when_a_standard_names_it(kit: DrumKit) -> None:
    for entry in kit.articulations:
        assert (entry.label is not None) == (entry.source == "standard"), entry.name


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


def test_the_sleep_token_map_has_its_67_pitches_as_57_articulations() -> None:
    pitches = [binding.note for entry in SLEEP_TOKEN.articulations for binding in entry.bindings]

    assert len(SLEEP_TOKEN.articulations) == 57
    assert len(pitches) == len(set(pitches)) == 67
    # Crash 4 has no choke note in the library's published user guide.
    assert not SLEEP_TOKEN.read(96, 100, 9)
    assert "crash.4.choke" not in SLEEP_TOKEN
    assert all(SLEEP_TOKEN.write(entry.name).channel == 9 for entry in SLEEP_TOKEN.articulations)
    assert all(entry.source == "mapping" for entry in SLEEP_TOKEN.articulations)
    flam, rimshot = SLEEP_TOKEN.resolve(39, 100, 9), SLEEP_TOKEN.resolve(40, 100, 9)
    assert (flam and flam.name, rimshot and rimshot.name) == ("snare.flam", "snare.rimshot")
    assert (SLEEP_TOKEN.pieces("tom"), SLEEP_TOKEN.pieces("crash")) == (3, 4)


def test_logic_pro_drums_has_its_published_mapping_but_note_32_and_drumverter_s_sticks() -> None:
    pitches = [binding.note for entry in LOGIC.articulations for binding in entry.bindings]
    found = [LOGIC.resolve(pitch, 100, 9) for pitch in (35, 33, 50, 52, 59, 70, 75)]

    assert len(LOGIC.articulations) == 28
    assert len(pitches) == len(set(pitches)) == 30
    assert set(pitches) == set(range(28, 55)) - {30, 32} | {56, 57, 59, 70, 75}
    assert all(entry.source == "mapping" for entry in LOGIC.articulations)
    assert LOGIC.articulation("sticks.hit").confidence == "medium"
    assert [entry and entry.name for entry in found] == [
        "kick.hit",
        "hat.pedal",
        "tom.1.edge",
        "ride.1.crash",
        "ride.1.bow.alt",
        "maracas.hit",
        "sticks.hit",
    ]
    assert (LOGIC.write("kick.hit").pitch, LOGIC.write("hat.pedal").pitch) == (36, 44)
    # A tom's edge goes to its tom, re-spread by register, on a kit without edges.
    moved = {
        row.source: row.target
        for row in convert(every_binding_note(LOGIC), LOGIC, GM, FOUR_FOUR).rows
    }
    assert [moved[f"tom.{n}.edge"] for n in (1, 2, 3)] == ["tom.1.hit", "tom.3.hit", "tom.6.hit"]


@pytest.mark.parametrize("library", NEW_IN_M3)
def test_the_maps_added_in_m3_have_their_counts_and_leave_out_what_they_say(library: str) -> None:
    kit = MAPS.kit(library)
    articulations, pitches, left_out = NEW_IN_M3[library]
    notes = [binding.note for entry in kit.articulations for binding in entry.bindings]

    assert (len(kit.articulations), len(notes)) == (articulations, pitches)
    assert len(set(notes)) == pitches
    assert not set(notes) & set(left_out)
    assert all(kit.read(pitch, 100, 9) == () for pitch in left_out)


def test_sleep_token_ii_s_groove_pack_kit_is_inferred_throughout() -> None:
    kit = MAPS.kit("sleep-token-ii", "groove-pack")
    notes = [binding.note for entry in kit.articulations for binding in entry.bindings]

    assert (len(kit.articulations), len(set(notes))) == (15, 15)
    assert {(entry.source, entry.confidence) for entry in kit.articulations} == {
        ("inferred", "low")
    }


def test_krimh_drums_follows_the_instrument_s_page_and_the_inferred_map_is_inferred() -> None:
    # The instrument's mapping page puts Kick Main on C0, note 24 (ADR 0139).
    krimh = MAPS.kit("krimh-drums")
    assert {(entry.source, entry.confidence) for entry in krimh.articulations} == {
        ("mapping", "high"),
        ("mapping", "medium"),
    }
    assert (krimh.write("kick.hit").pitch, krimh.write("ride.1.bow").pitch) == (24, 62)
    assert all(binding.note < 89 for entry in krimh.articulations for binding in entry.bindings)
    # The page's second notes are only read, after the note written.
    notes = {entry.name: [b.note for b in entry.bindings] for entry in krimh.articulations}
    assert notes["kick.hit"] == [24, 22]
    assert notes["hat.2.closed"] == [82, 70]
    assert notes["hat.2.open.three_quarter"] == [86, 87, 71]
    # Medium where the page's name is interpreted: an opening, an open tip, the pedal opened, and
    # the crashes and chinas numbered from their left and right.
    medium = {entry.name for entry in krimh.articulations if entry.confidence == "medium"}
    interpreted = ("hat.open", "hat.2.open", "hat.pedal.splash", "crash.", "china.")
    assert medium == {name for name in notes if name.startswith(interpreted)}
    assert {"kick.2.hit", "snare.center.wires_off", "tom.4.hit", "hat.closed.tip"} <= (
        notes.keys() - medium
    )
    ggd = MAPS.kit("ggd-matt-halpern")
    assert {(entry.source, entry.confidence) for entry in ggd.articulations} == {
        ("inferred", "low")
    }


def test_the_notes_the_maker_based_maps_left_out_read_as_drumverter_names_them() -> None:
    # ADR 0140: at medium, the maker's other names kept.
    counterkit, drum_lab = MAPS.kit("counterkit"), MAPS.kit("ni-drum-lab")
    for pitch, name in ((64, "hat.variable"), (65, "hat.variable.tip")):
        (match,) = counterkit.read(pitch, 100, 9)
        (binding,) = match.articulation.bindings
        assert (match.articulation.name, match.articulation.confidence) == (name, "medium")
        assert binding.cc is not None
        assert binding.cc.mode == "shape"
    center = drum_lab.articulation("snare.center")
    assert ([b.note for b in center.bindings], center.confidence) == ([38, 62, 63], "medium")
    assert all(drum_lab.resolve(pitch, 100, 9) == center for pitch in (62, 63))
    assert drum_lab.write("snare.center").pitch == 38


@pytest.mark.parametrize("kit", KITS, ids=lambda kit: kit.ref)
def test_every_shipped_articulation_reads_back_from_what_is_written(kit: DrumKit) -> None:
    for entry in kit.articulations:
        output = kit.write(entry.name)
        channel = output.channel if output.channel is not None else 9
        if output.cc is None:
            assert kit.resolve(output.pitch, output.velocity[0], channel) == entry
        else:
            assert [match.articulation for match in kit.read(output.pitch, 100, channel)] == [entry]


def check_report(rows: tuple[Row, ...], source: DrumKit, target: DrumKit) -> None:
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
        check_fallback_order(row, source, target)


FALLBACK_ORDER = ("piece", "variant", "default")
"""The steps after the exact name, in the order a conversion tries them (ADR 0021)."""


def check_fallback_order(row: Row, source: DrumKit, target: DrumKit) -> None:
    """The steps of an inexact row come in the fallback order, each within the family and taken
    only when the name before it won't do: the exact name, then piece substitution, then the
    name without its last variant, one at a time, then the piece's default.

    The exception is a family the vocabulary re-spreads by register, as toms are: piece
    substitution re-spreads its pieces whenever the kits have different numbers of them, even
    when the target has the exact name, so 6 toms onto 3 go 1, 1, 2, 2, 3, 3 (ADR 0021)."""
    vocabulary = target.vocabulary
    kinds = [step.kind for step in row.steps]
    assert set(kinds) <= set(FALLBACK_ORDER), row
    assert kinds == sorted(kinds, key=FALLBACK_ORDER.index), row
    assert kinds.count("piece") <= 1, row
    assert kinds.count("default") <= 1, row
    assert row.target in target, row
    for step in row.steps:
        asked, used = vocabulary.parse(step.asked), vocabulary.parse(step.used)
        assert asked.family == used.family, step
        match step.kind:
            case "piece":
                # Only when the target lacks the piece, or a family spread by register has a
                # different number of pieces in each kit.
                pieces = target.pieces(asked.family)
                respread = vocabulary.families[asked.family].piece_substitution == "register"
                assert asked.piece > pieces or (respread and source.pieces(asked.family) != pieces)
                assert used.path == asked.path, step
                assert used.piece <= pieces, step
            case "variant":
                assert step.asked not in target, step
                assert (used.piece, used.path) == (asked.piece, asked.path[:-1]), step
            case "default":
                assert step.asked not in target, step
                assert asked.variants == (), step
                assert asked.articulation not in vocabulary.ask_if_missing, step
                assert step.used == vocabulary.default(asked.family, asked.piece).text, step


@pytest.mark.parametrize("source", KITS, ids=lambda kit: kit.ref)
def test_converting_between_shipped_maps_never_changes_family(source: DrumKit) -> None:
    for target in KITS:
        check_conversion(source, target)


def check_conversion(source: DrumKit, target: DrumKit) -> None:
    notes = every_binding_note(source)

    conversion = convert(notes, source, target, FOUR_FOUR)

    held = {note.order for note in conversion.pending}
    kept = [note for note in notes if note.order not in held]
    assert len(conversion.notes) == len(kept)
    for before, after in zip(kept, conversion.notes, strict=True):
        assert family(source, before) == family(target, after), (before, after)
    check_report(conversion.rows, source, target)
    # Every note held back is in a decision request, and only those, and that includes every
    # note of a family the target lacks.
    asked_about = sum(int(str(request.details.get("count", 0))) for request in conversion.decisions)
    assert asked_about == len(conversion.pending)
    assert all(request.kind == "conversion" for request in conversion.decisions)
    lacking = {note.order for note in notes if not target.pieces(family(source, note))}
    assert lacking <= held
    for request in conversion.decisions:
        if request.details["reason"] == "family":
            name = str(request.details["source"]).split("|")[0]
            assert not target.pieces(source.canonical(name).family), request
    # Every note starts at its own tick, so none can meet another.
    assert conversion.collisions == ()


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
    check_report(conversion.rows, source, target)


@pytest.mark.parametrize(
    "target", [kit for kit in KITS if kit.pieces("snare")], ids=lambda kit: kit.ref
)
def test_note_39_of_the_default_layout_is_a_snare_on_every_kit_with_one_and_never_a_flam(
    target: DrumKit,
) -> None:
    hit = note(39)

    conversion = convert([hit], DRUMMER, target, FOUR_FOUR)

    assert family(DRUMMER, hit) == "snare"
    assert conversion.complete
    (row,) = conversion.rows
    (after,) = conversion.notes
    assert target.canonical(row.target).family == family(target, after) == "snare"
    assert "snare.flam" not in {
        row.target,
        *(m.articulation.name for m in target.read(after.pitch, after.velocity, after.channel)),
    }


def test_a_sample_layer_is_asked_about_on_every_kit_without_one() -> None:
    layers = [entry.name for entry in DRUMMER.articulations if entry.name.startswith("sample.")]
    notes = [note(DRUMMER.write(name).pitch, index * 240) for index, name in enumerate(layers)]
    without = [kit for kit in KITS if not kit.pieces("sample")]

    assert len(layers) == 6
    # The two layouts of iof-drummer, and ni-drum-lab's percussion slots.
    assert len(without) == len(KITS) - 3
    for target in without:
        conversion = convert(notes, DRUMMER, target, FOUR_FOUR)
        assert conversion.notes == ()
        assert {str(request.details["source"]) for request in conversion.decisions} == set(layers)
        for request in conversion.decisions:
            assert request.details["reason"] == "family"
            assert [option.value for option in request.options] == [DROP]
