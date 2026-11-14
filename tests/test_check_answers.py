"""`tools/check_answers.py`'s phrases and its comparison of an agent's controls with the
vocabulary's ranges (ADR 0087)."""

import json
import re
from pathlib import Path

import pytest
from pydantic import JsonValue

from check_answers import (
    BRIEF,
    CHECKS,
    EXIT_MISSES,
    EXIT_USAGE,
    Miss,
    Span,
    Vocabulary,
    compare,
    main,
    read_vocabulary,
    report,
)
from human_o_matic.render.style import built_in_styles

VOCABULARY = read_vocabulary()
DEFAULTS = built_in_styles()["tight"].defaults

type Results = dict[str, dict[str, JsonValue]]


def words(text: str) -> str:
    return " ".join(re.findall(r"[a-z']+", text.lower()))


def points(vocabulary: Vocabulary) -> Results:
    """Each phrase's controls at its row's starting points, a refinement's from the defaults."""
    found: Results = {}
    for phrase, answer in CHECKS:
        row = vocabulary.row(answer)
        controls: dict[str, JsonValue] = {}
        for name, expected in row.controls.items():
            if isinstance(expected, Span):
                base = getattr(DEFAULTS, name) if row.change else 0.0
                controls[name] = round(base + expected.value, 6)
            else:
                controls[name] = expected
        found[phrase] = controls
    return found


def phrase_of(answer: str) -> str:
    (phrase,) = (phrase for phrase, meant in CHECKS if meant == answer)
    return phrase


def test_each_answer_of_the_vocabulary_has_one_phrase_in_its_order() -> None:
    assert [answer for _, answer in CHECKS] == [row.answer for row in VOCABULARY.rows]
    assert len({phrase for phrase, _ in CHECKS}) == len(CHECKS)


def test_no_phrase_is_its_answer_s_own_words() -> None:
    for phrase, answer in CHECKS:
        assert words(phrase) != words(answer), phrase
        assert words(answer) not in words(phrase), phrase


def test_phrases_prints_the_phrases_alone(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["phrases"]) == 0

    out = capsys.readouterr().out
    assert out.splitlines() == [phrase for phrase, _ in CHECKS]
    assert "[" not in out


def test_brief_says_what_to_give_then_the_phrases(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["brief"]) == 0

    out = capsys.readouterr().out
    assert out.startswith(BRIEF)
    assert out.splitlines()[-len(CHECKS) :] == [phrase for phrase, _ in CHECKS]
    assert "[" not in out


def test_the_table_s_own_points_read_as_every_answer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = tmp_path / "results.json"
    results.write_text(json.dumps(points(VOCABULARY)), encoding="utf-8")

    assert compare(VOCABULARY, points(VOCABULARY)) == []
    assert main(["compare", str(results)]) == 0
    assert (
        capsys.readouterr().out
        == f"{len(CHECKS)} of {len(CHECKS)} answers read as the vocabulary means them\n"
    )


def test_a_value_is_clamped_as_the_server_clamps_it_and_a_default_may_be_given() -> None:
    results = points(VOCABULARY)
    results[phrase_of("full power")] = {"energy": 1.3, "arc": "steady", "style": "tight"}

    assert compare(VOCABULARY, results) == []


def test_controls_unlike_the_answer_are_misses_saying_why() -> None:
    results = points(VOCABULARY)
    full, call, tight = (
        phrase_of(answer) for answer in ("full power", "your call", "tight, modern metal")
    )
    harder, softer = phrase_of("a bit harder"), phrase_of("a little softer")
    results[full] = {"energy": 0.6, "fill_intensity": 0.8}
    results[call] = {"style": "medium"}
    results[tight] = {"tightness": 0.6}
    results[harder] = {"energy": 0.9}
    del results[softer]
    results["something else"] = {}

    misses = compare(VOCABULARY, results)

    assert misses == [
        Miss(full, "energy 0.6 is outside 0.85 to 1"),
        Miss(full, "fill_intensity 0.8 is set, where the answer leaves it at its default, 0.5"),
        Miss(tight, "tightness 0.6 is outside 0.75 to 0.95"),
        Miss(call, "style medium, where tight is meant"),
        Miss(harder, "energy 0.9 is outside 0.55 to 0.65"),
        Miss(softer, "no controls given"),
        Miss("something else", "isn't a phrase of the check"),
    ]
    lines = report(misses)
    assert (
        lines[0] == f'{json.dumps(full)} (meant as "full power"): energy 0.6 is outside 0.85 to 1'
    )
    assert lines[-2] == '"something else": isn\'t a phrase of the check'
    assert (
        lines[-1] == f"{len(CHECKS) - 5} of {len(CHECKS)} answers read as the vocabulary means them"
    )


def test_a_ramp_is_read_in_whole_bars_and_none_leaves_it_at_its_default() -> None:
    results = points(VOCABULARY)
    two, four, none = (
        phrase_of(answer)
        for answer in ("build into it over 2 bars", "a 4-bar ramp", "no ramp, straight in")
    )
    assert compare(VOCABULARY, results) == []
    results[two] = {"ramp": 2}
    results[none] = {}
    assert compare(VOCABULARY, results) == []

    results[two] = {"ramp": 3}
    results[four] = {"ramp": 2, "energy": 0.9}
    results[none] = {"ramp": 1}

    assert compare(VOCABULARY, results) == [
        Miss(two, "ramp 3 is outside 2 to 2"),
        Miss(four, "energy 0.9 is set, where the answer leaves it at its default, 0.5"),
        Miss(four, "ramp 2 is outside 4 to 4"),
        Miss(none, "ramp 1 is outside 0 to 0"),
    ]


def test_a_control_of_the_wrong_kind_or_none_is_a_miss() -> None:
    results = points(VOCABULARY)
    full, done = phrase_of("full power"), phrase_of("leave this alone, it's finished")
    results[full] = {"energy": "high", "tempo": 120}
    results[done] = {"skip": False, "style": 3}

    misses = compare(VOCABULARY, results)

    assert misses == [
        Miss(full, "energy: Input should be a valid number"),
        Miss(full, "tempo: Extra inputs are not permitted"),
        Miss(done, "style 3 isn't a built-in style"),
    ]


def test_compare_exits_1_on_a_miss_and_2_on_a_file_it_can_t_read(tmp_path: Path) -> None:
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"Maximum energy.": {"energy": 0.2}}), encoding="utf-8")
    assert main(["compare", str(results)]) == EXIT_MISSES

    results.write_text(json.dumps({"Maximum energy.": 0.95}), encoding="utf-8")
    assert main(["compare", str(results)]) == EXIT_USAGE
    results.write_text("not json", encoding="utf-8")
    assert main(["compare", str(results)]) == EXIT_USAGE
    assert main(["compare", str(tmp_path / "missing.json")]) == EXIT_USAGE
    assert (
        main(["--vocabulary", str(tmp_path / "missing.md"), "compare", str(results)]) == EXIT_USAGE
    )
