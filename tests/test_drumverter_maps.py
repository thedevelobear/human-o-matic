"""tools/drumverter_maps.py: how drumverter's note maps are named in the vocabulary, and the maps
it built (ADRs 0137 and 0138). Its download isn't run here: the engines are written in code."""

import pytest

from drumverter_maps import Engine, Note, named, read_pins
from human_o_matic.maps.loader import built_in_maps, built_in_vocabulary
from human_o_matic.resources import data_dir

VOCABULARY = built_in_vocabulary()


def engine(*notes: tuple[int, str] | tuple[int, str, bool]) -> Engine:
    return Engine(
        id="test",
        name="Test",
        notes=tuple(
            Note(note=n[0], canon=n[1], primary=n[2] if len(n) > 2 else False) for n in notes
        ),
    )


def test_toms_are_numbered_along_the_kit_and_pieces_from_one() -> None:
    built = named(
        engine(
            (36, "kick.main"),
            (41, "tom.floor2.hit"),
            (43, "tom.floor1.hit"),
            (47, "tom.rack2.hit"),
            (48, "tom.rack1.rimshot"),
            (50, "tom.rack1.hit"),
            (57, "crash.2.hit"),
            (58, "crash.2.mute"),
            (59, "crash.4.hit"),
        ),
        VOCABULARY,
    )

    assert built.names == {
        "kick.hit": (36,),
        "tom.4.hit": (41,),
        "tom.3.hit": (43,),
        "tom.2.hit": (47,),
        "tom.1.rimshot": (48,),
        "tom.1.hit": (50,),
        "crash.1.hit": (57,),
        "crash.1.choke": (58,),
        "crash.2.hit": (59,),
    }


def test_a_hat_s_rungs_spread_from_the_least_open_to_fully_open() -> None:
    four = named(
        engine(
            (42, "hat.closed.edge"),
            (54, "hat.loose"),
            (55, "hat.open1"),
            (56, "hat.open2"),
            (57, "hat.open3"),
        ),
        VOCABULARY,
    )
    one = named(engine((42, "hat.closed"), (46, "hat.open2")), VOCABULARY)

    assert [four.names[n] for n in ("hat.open.quarter", "hat.open.half")] == [(54,), (55,)]
    assert [four.names[n] for n in ("hat.open.three_quarter", "hat.open")] == [(56,), (57,)]
    assert one.names["hat.open"] == (46,)


def test_a_tip_without_its_plain_stroke_is_it_and_a_tight_hat_without_a_closed_one_is_closed() -> (
    None
):
    built = named(
        engine(
            (42, "hat.tight.tip"),
            (44, "hat.pedal"),
            (46, "hat.open1.tip"),
            (51, "ride.1.bowtip"),
            (53, "ride.1.belltip"),
        ),
        VOCABULARY,
    )

    assert built.names == {
        "hat.closed": (42,),
        "hat.pedal": (44,),
        "hat.open": (46,),
        "ride.1.bow": (51,),
        "ride.1.bell": (53,),
    }


def test_the_written_note_is_drumverter_s_primary_and_the_others_are_read() -> None:
    built = named(
        engine((35, "snare1.hit"), (38, "snare1.hit", True), (40, "snare1.hit"), (36, "kick.main")),
        VOCABULARY,
    )

    assert built.names["snare.center"] == (38, 35, 40)


def test_what_the_vocabulary_can_t_name_is_left_out_with_why() -> None:
    built = named(
        engine(
            (36, "kick.main"),
            (38, "snare1.hit"),
            (39, "snare1.ruff"),
            (42, "hat.closed"),
            (53, "hat.closed.bell"),
            (60, "perc.misc"),
            (73, "china.2.mute"),
        ),
        VOCABULARY,
    )

    assert built.left_out == {
        39: "snare ruff",
        53: "hi-hat bell",
        60: "percussion",
        73: "china.1.choke without china.1.hit",
    }


def test_every_map_built_from_drumverter_s_is_a_mapping_at_medium_or_high() -> None:
    maps = built_in_maps()
    for library in read_pins().libraries:
        text = (data_dir() / "maps" / f"{library.id}.toml").read_text(encoding="utf-8")
        assert "tools/drumverter_maps.py" in text.split("schema = 1")[0], library.id
        for pin in library.kits:
            kit = maps.kit(library.id, pin.id)
            levels = {(entry.source, entry.confidence) for entry in kit.articulations}
            expected = (
                {("mapping", "medium"), ("mapping", "high")}
                if library.maker
                else {("mapping", "medium")}
            )
            assert levels <= expected, kit.ref


@pytest.mark.parametrize("note", [3, 4, 6, 41, 43])
def test_addictive_drums_2_leaves_out_what_xln_s_keymap_names_otherwise(note: int) -> None:
    kit = built_in_maps().kit("addictive-drums-2")

    assert kit.read(note, 100, 9) == ()


def test_addictive_drums_2_is_high_only_where_xln_s_keymap_names_the_same_stroke() -> None:
    kit = built_in_maps().kit("addictive-drums-2")
    high = {entry.name for entry in kit.articulations if entry.confidence == "high"}

    assert {"kick.hit", "snare.rimshot", "ride.1.bell", "tom.4.rimshot"} <= high
    assert not {"hat.closed", "crash.1.hit", "snare.center"} & high
    # XLN's Cymbal 6 is the kit's fifth crash, as drumverter names no fifth.
    assert kit.write("crash.5.hit").pitch == 93
