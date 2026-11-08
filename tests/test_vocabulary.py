from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from human_o_matic.maps.vocabulary import CanonicalName, MapError, load_vocabulary
from human_o_matic.resources import data_dir

VOCABULARY = load_vocabulary(data_dir() / "vocabulary.toml")


def every_name(pieces: int = 3) -> list[str]:
    """Every name of the built-in vocabulary, on up to `pieces` pieces of each family."""
    names: list[str] = []
    for family, rule in VOCABULARY.families.items():
        count = 1 if rule.pieces == "single" else pieces
        for piece in range(1, count + 1):
            names.extend(
                VOCABULARY.name(family, piece, tuple(path.split("."))).text
                for path in rule.articulations
            )
    return names


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "vocabulary.toml"
    path.write_text(text)
    return path


def test_the_built_in_vocabulary_is_in_the_data_directory() -> None:
    assert (data_dir() / "vocabulary.toml").is_file()
    assert data_dir().parent == Path(__file__).resolve().parents[1]


def test_every_family_has_its_default_first_and_listed() -> None:
    for family, rule in VOCABULARY.families.items():
        assert rule.default in rule.articulations, family
        assert VOCABULARY.default(family, 1).path == (rule.default,)


@pytest.mark.parametrize(
    ("text", "family", "piece", "path"),
    [
        ("snare.center", "snare", 1, ("center",)),
        ("snare.2.center", "snare", 2, ("center",)),
        ("kick.2.hit", "kick", 2, ("hit",)),
        ("crash.1.choke", "crash", 1, ("choke",)),
        ("hat.open.quarter.tip", "hat", 1, ("open", "quarter", "tip")),
        ("tom.6.rimshot", "tom", 6, ("rimshot",)),
        ("ride.1.bow.alt2", "ride", 1, ("bow", "alt2")),
        ("clap.hit", "clap", 1, ("hit",)),
    ],
)
def test_names_are_taken_apart(text: str, family: str, piece: int, path: tuple[str, ...]) -> None:
    name = VOCABULARY.parse(text)

    assert name == CanonicalName(text=text, family=family, piece=piece, path=path)
    assert VOCABULARY.name(family, piece, path) == name
    assert name.articulation == path[0]
    assert name.variants == path[1:]


@pytest.mark.parametrize(
    "text",
    [
        "snare.1.center",  # the first snare has no number
        "tom.hit",  # a tom always has one
        "crash.choke",
        "clap.2.hit",  # a clap never has one
        "tom.0.hit",
        "tom.01.hit",
        "hat.open.tip.quarter",  # not an articulation and variants of hat
        "hat.open.three_quarter.tip",
        "snare.centre",
        "Snare.center",
        "gong.hit",
        "snare",
        "snare.",
        "snare.center.",
        "",
    ],
)
def test_names_outside_the_grammar_are_refused(text: str) -> None:
    with pytest.raises(ValueError, match=r"snare|tom|crash|clap|hat|family|piece|articulation"):
        VOCABULARY.parse(text)


@given(st.sampled_from(every_name()))
def test_every_name_is_written_as_it_is_read(text: str) -> None:
    name = VOCABULARY.parse(text)

    assert VOCABULARY.name(name.family, name.piece, name.path).text == text
    assert str(name) == text


def test_hat_openness_is_in_words_and_falls_back_to_fully_open() -> None:
    hats = VOCABULARY.families["hat"].articulations

    assert {"open", "open.quarter", "open.half", "open.three_quarter"} <= set(hats)
    assert VOCABULARY.parse("hat.open.half").path[:-1] == ("open",)


def test_a_choke_has_no_fallback_and_suggestions_name_other_families() -> None:
    assert VOCABULARY.ask_if_missing == ("choke",)
    for family, substitutes in VOCABULARY.suggestions.items():
        assert all(not substitute.startswith(f"{family}.") for substitute in substitutes)


VALID = """
schema = 1
[families.snare]
pieces = "second"
default = "center"
articulations = ["center", "rimshot", "rimshot.tip"]
"""


def test_a_small_vocabulary_loads(tmp_path: Path) -> None:
    vocabulary = load_vocabulary(write(tmp_path, VALID))

    assert vocabulary.parse("snare.2.rimshot.tip").piece == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("rimshot.tip", "rim.tip"), "without its parent rim"),
        (('default = "center"', 'default = "head"'), "default head"),
        (('default = "center"', 'default = "rimshot.tip"'), "default rimshot.tip"),
        (('"rimshot", ', '"rimshot", "rimshot", '), "listed twice"),
        (('"center", ', '"Center", '), "lower-case"),
        (("[families.snare]", "[families.Snare]"), "lower-case word"),
        (('pieces = "second"', 'pieces = "many"'), "pieces"),
        (("schema = 1", "schema = 2"), "schema"),
        (("schema = 1", 'schema = 1\nask_if_missing = ["choke"]'), "no family has"),
        (("schema = 1", "schema = 1\nextra = 1"), "extra"),
        (("schema = 1", 'schema = 1\nsuggestions = { snare = ["snare"] }'), "another family"),
        (("schema = 1", 'schema = 1\nsuggestions = { kick = ["snare"] }'), "kick"),
    ],
)
def test_an_invalid_vocabulary_is_refused(
    tmp_path: Path, change: tuple[str, str], message: str
) -> None:
    assert change[0] in VALID
    path = write(tmp_path, VALID.replace(*change))

    with pytest.raises(MapError, match=message):
        load_vocabulary(path)


def test_a_vocabulary_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MapError, match=r"vocabulary\.toml"):
        load_vocabulary(write(tmp_path, "schema = = 1"))
