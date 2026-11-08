from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.decisions import DecisionRequest
from human_o_matic.maps.convert import (
    DROP,
    MAX_POSITIONS,
    Conversion,
    Resolution,
    Row,
    Step,
    StepKind,
    convert,
    resolve_name,
    substitute_piece,
)
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_vocabulary, load_library
from human_o_matic.maps.vocabulary import load_vocabulary
from human_o_matic.midi.io import Note
from human_o_matic.midi.tempo import TimeSignature, TimeSignatureMap
from map_files import articulation, kit, library, write_library

PPQ = 960
FOUR_FOUR = TimeSignatureMap(PPQ, [])
SHAPE = {"mode": "shape", "controller": 4}

BIG = kit(
    articulation("kick.hit", 36),
    articulation("snare.center", 38),
    articulation("snare.flam", 39),
    articulation("snare.2.center", 40),
    articulation("sticks.hit", 31, label="Sticks"),
    articulation("hat.closed", 42),
    articulation("hat.open", 46),
    articulation("hat.open.quarter", 77),
    articulation("hat.open.quarter.tip", 83, confidence="medium"),
    articulation("hat.variable", 32, cc=SHAPE),
    *(articulation(f"tom.{n}.hit", pitch) for n, pitch in enumerate((50, 48, 47, 45, 43, 41), 1)),
    articulation("crash.1.hit", 49),
    articulation("crash.1.choke", 91),
    articulation("crash.1.mute", 61),
    articulation("crash.2.hit", 57),
    articulation("crash.3.hit", 54),
    articulation("ride.1.bow", 51),
    articulation("ride.1.crash", 59),
    articulation("stack.1.hit", 63),
    articulation("stack.1.hit.tip", 62),
    id="big",
)
SMALL = kit(
    articulation("kick.hit", 36),
    articulation("snare.center", 38, velocity=[1, 119], label="Snare"),
    articulation("snare.sidestick", 37, label="Side Stick"),
    articulation("hat.closed", 42),
    articulation("hat.open", 46, confidence="low"),
    *(articulation(f"tom.{n}.hit", pitch) for n, pitch in enumerate((48, 45, 43), 1)),
    articulation("crash.1.hit", 49),
    articulation("crash.2.hit", 57),
    articulation("ride.1.bow", 51),
    articulation("china.1.hit", 52),
    id="small",
    channel=10,
)


@pytest.fixture
def kits(tmp_path: Path) -> tuple[DrumKit, DrumKit]:
    big, small = load_library(write_library(tmp_path, library(BIG, SMALL)), built_in_vocabulary())
    return big, small


def note(pitch: int, start: int = 0, velocity: int = 100, channel: int = 9) -> Note:
    return Note(
        track=0, channel=channel, pitch=pitch, start=start, end=start + 10, velocity=velocity
    )


def one(conversion: Conversion) -> Row:
    (row,) = conversion.rows
    return row


def request(conversion: Conversion) -> DecisionRequest:
    (found,) = conversion.decisions
    return found


def test_the_exact_name_is_used_first(kits: tuple[DrumKit, DrumKit]) -> None:
    big, small = kits

    conversion = convert([note(36, velocity=90)], big, small, FOUR_FOUR)

    assert conversion.complete
    assert conversion.notes == (note(36, velocity=90),)
    assert one(conversion) == Row(
        source="kick.hit",
        target="kick.hit",
        count=1,
        source_confidence="high",
        target_confidence="high",
    )
    assert conversion.inexact == ()


@pytest.mark.parametrize(
    ("asked", "used", "steps"),
    [
        ("crash.3.hit", "crash.2.hit", [("piece", "crash.3.hit", "crash.2.hit")]),
        ("snare.2.center", "snare.center", [("piece", "snare.2.center", "snare.center")]),
        (
            "hat.open.quarter.tip",
            "hat.open",
            [
                ("variant", "hat.open.quarter.tip", "hat.open.quarter"),
                ("variant", "hat.open.quarter", "hat.open"),
            ],
        ),
        ("snare.flam", "snare.center", [("default", "snare.flam", "snare.center")]),
        ("ride.1.crash", "ride.1.bow", [("default", "ride.1.crash", "ride.1.bow")]),
        ("crash.1.mute", "crash.1.hit", [("default", "crash.1.mute", "crash.1.hit")]),
        (
            "tom.6.hit",
            "tom.3.hit",
            [("piece", "tom.6.hit", "tom.3.hit")],
        ),
    ],
)
def test_each_fallback_step_is_reported(
    kits: tuple[DrumKit, DrumKit], asked: str, used: str, steps: list[tuple[StepKind, str, str]]
) -> None:
    big, small = kits
    expected = tuple(Step(kind=kind, asked=a, used=u) for kind, a, u in steps)

    assert resolve_name(asked, big, small) == Resolution(used, expected)
    conversion = convert([note(big.write(asked).pitch)], big, small, FOUR_FOUR)
    assert one(conversion).steps == expected
    assert conversion.inexact == conversion.rows
    assert conversion.notes[0].pitch == small.write(used).pitch


def test_a_target_without_the_family_is_a_decision_request(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, small = kits
    notes = [note(31, start=PPQ * 4), note(31, start=PPQ * 9)]

    conversion = convert(notes, big, small, FOUR_FOUR)

    assert resolve_name("sticks.hit", big, small) == Resolution(None, reason="family")
    assert not conversion.complete
    assert conversion.notes == ()
    assert conversion.pending == tuple(notes)
    asked = request(conversion)
    assert asked.kind == "conversion"
    assert asked.answer_with == ("substitutions",)
    assert asked.details == {
        "source": "sticks.hit",
        "reason": "family",
        "count": 2,
        "positions": [[1, 0.0], [2, 1.0]],
    }
    assert "Sticks (sticks.hit), 2 notes from bar 2" in asked.message
    assert "has no sticks" in asked.message
    # The suggestion is offered, never applied.
    assert [option.value for option in asked.options] == ["snare.sidestick", DROP]
    assert asked.options[0].label == "Play them as snare.sidestick (Side Stick), note 37"


def test_a_suggestion_keeps_the_articulation_the_other_family_has(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, small = kits

    conversion = convert([note(62)], big, small, FOUR_FOUR)

    assert [option.value for option in request(conversion).options] == ["china.1.hit", DROP]


def test_a_hit_changes_family_only_when_the_user_picks_it(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, small = kits
    notes = [note(31), note(63, start=10), note(31, start=20)]

    conversion = convert(
        notes, big, small, FOUR_FOUR, substitutions={"sticks.hit": "snare.sidestick"}
    )

    assert [n.pitch for n in conversion.notes] == [37, 37]
    assert conversion.pending == (notes[1],)
    picked = conversion.rows[0]
    assert (picked.source, picked.target, picked.count) == ("sticks.hit", "snare.sidestick", 2)
    assert picked.steps == (Step(kind="picked", asked="sticks.hit", used="snare.sidestick"),)
    assert request(conversion).details["source"] == "stack.1.hit"


def test_a_dropped_hit_is_left_out_and_counted(kits: tuple[DrumKit, DrumKit]) -> None:
    big, small = kits

    conversion = convert(
        [note(31), note(36)], big, small, FOUR_FOUR, substitutions={"sticks.hit": DROP}
    )

    assert conversion.complete
    assert [n.pitch for n in conversion.notes] == [36]
    assert conversion.rows[0] == Row(
        source="sticks.hit",
        target=DROP,
        count=1,
        steps=(Step(kind="picked", asked="sticks.hit", used=DROP),),
        source_confidence="high",
    )


def test_a_missing_choke_is_asked_about_and_a_mute_is_not(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, small = kits

    conversion = convert([note(91), note(61)], big, small, FOUR_FOUR)

    assert resolve_name("crash.1.choke", big, small) == Resolution(None, reason="articulation")
    assert [n.pitch for n in conversion.notes] == [49]
    asked = request(conversion)
    assert asked.details["reason"] == "articulation"
    assert "has no crash.1.choke, and playing crash.1.hit instead" in asked.message
    assert [option.value for option in asked.options] == ["crash.1.hit", DROP]


def test_a_controller_driven_articulation_is_asked_about(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, small = kits

    conversion = convert([note(32)], big, small, FOUR_FOUR)

    asked = request(conversion)
    assert asked.details["reason"] == "cc"
    assert asked.details["source"] == "hat.variable"
    assert "depends on a controller value" in asked.message
    assert [option.value for option in asked.options] == ["hat.closed", DROP]


def test_notes_a_controller_value_tells_apart_are_asked_about_together(tmp_path: Path) -> None:
    def select(low: int, high: int) -> dict[str, object]:
        return {"mode": "select", "controller": 4, "values": [low, high]}

    pedal, plain = load_library(
        write_library(
            tmp_path,
            library(
                kit(
                    articulation("hat.closed", 26, cc=select(0, 63)),
                    articulation("hat.open", 26, cc=select(64, 127)),
                    id="pedal",
                ),
                kit(
                    articulation("hat.closed", 42),
                    articulation("hat.open", 30, cc=select(0, 127)),
                    id="plain",
                ),
            ),
        ),
        built_in_vocabulary(),
    )

    from_pedal = convert([note(26)], pedal, plain, FOUR_FOUR)
    to_pedal = convert([note(42), note(30)], plain, pedal, FOUR_FOUR)

    assert request(from_pedal).details["source"] == "hat.closed|hat.open"
    sources = [asked.details["source"] for asked in to_pedal.decisions]
    assert sources == ["hat.closed", "hat.open"]
    assert all(asked.details["reason"] == "cc" for asked in to_pedal.decisions)
    assert to_pedal.notes == ()
    picked = convert(
        [note(26)], pedal, plain, FOUR_FOUR, substitutions={"hat.closed|hat.open": "hat.closed"}
    )
    assert [n.pitch for n in picked.notes] == [42]
    with pytest.raises(ValueError, match="depends on a controller"):
        convert([], plain, pedal, FOUR_FOUR, substitutions={"hat.closed": "hat.open"})


def test_converting_a_kit_to_itself_keeps_every_mapped_note(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, _ = kits
    notes = [note(32), note(91), note(31, start=5)]

    conversion = convert([*notes, note(99)], big, big, FOUR_FOUR)

    assert conversion.notes == tuple(notes)
    assert [row.source for row in conversion.rows] == [
        "hat.variable",
        "crash.1.choke",
        "sticks.hit",
    ]
    assert all(row.source == row.target and not row.steps for row in conversion.rows)
    assert request(conversion).kind == "unmapped_notes"


def test_unmapped_notes_are_a_decision_request(kits: tuple[DrumKit, DrumKit]) -> None:
    big, small = kits
    signatures = TimeSignatureMap(PPQ, [(PPQ * 4, TimeSignature(7, 8))])
    many = [note(1, start=PPQ * 4 + PPQ // 2 * index) for index in range(MAX_POSITIONS + 3)]
    notes = [note(14, start=PPQ, channel=2), *many, note(36)]

    conversion = convert(notes, big, small, signatures)

    assert [n.pitch for n in conversion.notes] == [36]
    assert set(conversion.pending) == {*many, notes[0]}
    asked = request(conversion)
    assert asked.kind == "unmapped_notes"
    assert asked.answer_with == ("unmapped", "from_map")
    groups = asked.details["notes"]
    assert isinstance(groups, list)
    assert groups[0] == {
        "pitch": 1,
        "channels": [9],
        "count": MAX_POSITIONS + 3,
        "positions": [[1 + index // 7, float(index % 7)] for index in range(MAX_POSITIONS)],
    }
    assert groups[1] == {"pitch": 14, "channels": [2], "count": 1, "positions": [[0, 1.0]]}
    assert asked.details["kit"] == "test-drums/big"
    assert "12 notes on 2 pitches have no articulation in Library test-drums (Kit big)" in (
        asked.message
    )
    assert "note 1: 11 notes from bar 2; note 14: 1 note from bar 1" in asked.message
    assert DecisionRequest.model_validate_json(asked.model_dump_json()) == asked


def test_unmapped_notes_take_the_users_answer(kits: tuple[DrumKit, DrumKit]) -> None:
    big, small = kits

    conversion = convert(
        [note(1), note(2), note(1)], big, small, FOUR_FOUR, unmapped={1: "kick.hit", 2: DROP}
    )

    assert conversion.complete
    assert [n.pitch for n in conversion.notes] == [36, 36]
    assert [(row.source, row.target, row.count) for row in conversion.rows] == [
        ("note 1", "kick.hit", 2),
        ("note 2", DROP, 1),
    ]
    assert conversion.rows[0].source_confidence is None


def test_an_answer_the_target_cannot_play_is_refused(kits: tuple[DrumKit, DrumKit]) -> None:
    big, small = kits

    with pytest.raises(ValueError, match=r"has no snare\.rimshot"):
        convert([], big, small, FOUR_FOUR, substitutions={"sticks.hit": "snare.rimshot"})
    with pytest.raises(ValueError, match="has no gong"):
        convert([], big, small, FOUR_FOUR, unmapped={1: "gong"})


def test_a_velocity_outside_the_target_range_is_clamped_and_counted(
    kits: tuple[DrumKit, DrumKit],
) -> None:
    big, small = kits

    conversion = convert([note(38, velocity=127), note(38, velocity=64)], big, small, FOUR_FOUR)

    assert [n.velocity for n in conversion.notes] == [119, 64]
    assert one(conversion).clamped == 1


def test_the_target_channel_is_written(tmp_path: Path) -> None:
    source, target = load_library(
        write_library(
            tmp_path,
            library(
                kit(articulation("kick.hit", 36), articulation("snare.center", 38), id="any"),
                kit(
                    articulation("kick.hit", 36),
                    articulation("snare.center", 38, channel=2),
                    id="bound",
                ),
            ),
        ),
        built_in_vocabulary(),
    )

    there = convert([note(36, channel=5), note(38, channel=5)], source, target, FOUR_FOUR)
    back = convert(there.notes, target, source, FOUR_FOUR)

    assert [n.channel for n in there.notes] == [5, 1]
    assert [n.channel for n in back.notes] == [5, 1]


def test_confidence_below_high_is_reported(kits: tuple[DrumKit, DrumKit]) -> None:
    big, small = kits

    row = one(convert([note(83)], big, small, FOUR_FOUR))

    assert (row.source_confidence, row.target_confidence) == ("medium", "low")


def test_six_toms_go_onto_three_by_register_and_back(tmp_path: Path) -> None:
    six = kit(*(articulation(f"tom.{n}.hit", 40 + n) for n in range(1, 7)), id="six")
    three = kit(*(articulation(f"tom.{n}.hit", 60 + n) for n in range(1, 4)), id="three")
    many, few = load_library(write_library(tmp_path, library(six, three)), built_in_vocabulary())

    down = convert([note(40 + n) for n in range(1, 7)], many, few, FOUR_FOUR)
    up = convert([note(60 + n) for n in range(1, 4)], few, many, FOUR_FOUR)

    assert [n.pitch - 60 for n in down.notes] == [1, 1, 2, 2, 3, 3]
    assert [n.pitch - 40 for n in up.notes] == [1, 3, 6]
    assert down.rows[0].steps == ()
    assert all(row.steps[0].kind == "piece" for row in down.rows[1:])


@given(st.integers(1, 9), st.integers(1, 9))
def test_re_spreading_by_register_keeps_the_order_and_the_ends(source: int, target: int) -> None:
    pieces = [substitute_piece("register", piece, source, target) for piece in range(1, source + 1)]

    assert pieces == sorted(pieces)
    assert all(1 <= piece <= target for piece in pieces)
    assert pieces[0] == 1
    if source > 1:
        assert pieces[-1] == target
    if source == target:
        assert pieces == list(range(1, source + 1))


@given(st.integers(1, 9), st.integers(1, 9), st.integers(1, 9))
def test_nearest_keeps_the_piece_or_takes_the_last(piece: int, source: int, target: int) -> None:
    assert substitute_piece("nearest", piece, source, target) == min(piece, target)


def test_kits_from_different_vocabularies_are_refused(
    tmp_path: Path, kits: tuple[DrumKit, DrumKit]
) -> None:
    big, _ = kits
    copy = tmp_path / "vocabulary.toml"
    copy.write_text((Path(__file__).parents[1] / "data" / "vocabulary.toml").read_text())
    other = load_library(write_library(tmp_path, library(SMALL), "other"), load_vocabulary(copy))

    with pytest.raises(ValueError, match="different vocabularies"):
        convert([], big, other[0], FOUR_FOUR)
