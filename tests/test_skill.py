"""The skill: its files and frontmatter, the tools it names, and its vocabulary's tables, read by
`tools/check_answers.py` (ADRs 0087 and 0089)."""

import re
from pathlib import Path

import anyio
import pytest

from check_answers import (
    SKILL,
    SKILL_DIR,
    VOCABULARY,
    Row,
    Span,
    VocabularyError,
    read_vocabulary,
)
from human_o_matic.controls import Controls, ControlVector
from human_o_matic.mcp_server import build_server
from human_o_matic.render.style import STYLE_NAMES, built_in_styles
from human_o_matic.session import SessionStore

VOCABULARY_ROWS = read_vocabulary()
DEFAULTS = Controls(
    energy=0.5,
    groove=0.5,
    dynamic_range=0.5,
    tightness=0.75,
    feel=0.0,
    arc="steady",
    fill_intensity=0.5,
    ghost_level=0.5,
    skip=False,
    creative=False,
    ramp=0,
)
"""The defaults the vocabulary says every style has."""
PLAN_ROWS: dict[str, dict[str, float | str]] = {
    "breakdown, full power": {
        "energy": 0.95,
        "groove": 0.2,
        "dynamic_range": 0.2,
        "tightness": 0.8,
        "feel": 0.0,
        "ghost_level": 0.2,
    },
    "bridge, low energy, high groove": {
        "energy": 0.35,
        "groove": 0.85,
        "dynamic_range": 0.7,
        "tightness": 0.6,
        "feel": 0.2,
        "ghost_level": 0.7,
    },
    "big last chorus": {
        "energy": 0.9,
        "groove": 0.5,
        "dynamic_range": 0.4,
        "tightness": 0.75,
        "feel": 0.0,
        "ghost_level": 0.3,
    },
    "verse, holding back, building": {
        "energy": 0.5,
        "arc": "build",
        "groove": 0.6,
        "dynamic_range": 0.5,
        "tightness": 0.75,
        "feel": 0.1,
        "ghost_level": 0.5,
    },
}
"""The plan's four examples for the vocabulary, as the plan gives them."""
FULL_POWER = 0.85
"""Where the vocabulary says full power starts: kick and backbeats about 118 to 127."""
LOUD = 118


def frontmatter(text: str) -> dict[str, str]:
    """The `key: value` lines between a file's first two `---` lines."""
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    found: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(": ")
        assert separator, line
        found[key] = value
    return found


def test_the_skill_and_its_vocabulary_are_in_the_repository() -> None:
    assert Path(__file__).resolve().parents[1] / "skills" / "human-o-matic" == SKILL_DIR
    assert SKILL.is_file()
    assert VOCABULARY.is_file()
    assert "(references/vocabulary.md)" in SKILL.read_text(encoding="utf-8")


def test_the_skill_s_frontmatter_is_a_claude_code_skill_s() -> None:
    found = frontmatter(SKILL.read_text(encoding="utf-8"))

    assert set(found) == {"name", "description"}
    assert found["name"] == SKILL_DIR.name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", found["name"])
    description = found["description"]
    assert 0 < len(description) <= 1024
    # A plain YAML scalar: no mapping, comment, quote or indicator to read otherwise.
    assert ": " not in description
    assert " #" not in description
    assert description[0] not in "-?:,[]{}#&*!|>'\"%@`"
    assert "<" not in description


def test_the_skill_names_every_tool_the_server_serves(tmp_path: Path) -> None:
    async def listed() -> set[str]:
        server = build_server(SessionStore(tmp_path))
        return {tool.name for tool in await server.list_tools()}

    text = SKILL.read_text(encoding="utf-8")

    tools = anyio.run(listed)

    assert len(tools) == 9
    assert all(f"`{tool}`" in text for tool in tools), tools
    assert "`preview`" not in text


def test_the_vocabulary_has_about_30_answers() -> None:
    assert len(VOCABULARY_ROWS.answers) >= 30
    assert len(VOCABULARY_ROWS.rows) >= 30


@pytest.mark.parametrize(("answer", "values"), PLAN_ROWS.items())
def test_the_plan_s_four_rows_come_first_with_its_values(
    answer: str, values: dict[str, float | str]
) -> None:
    row = VOCABULARY_ROWS.row(answer)
    found = {
        name: expected.value if isinstance(expected, Span) else expected
        for name, expected in row.controls.items()
    }

    assert found == values
    assert not row.change
    assert row in VOCABULARY_ROWS.answers[: len(PLAN_ROWS)]


@pytest.mark.parametrize("row", VOCABULARY_ROWS.rows, ids=lambda row: row.answer)
def test_every_value_is_one_its_control_takes_and_lies_in_its_range(row: Row) -> None:
    for name, expected in row.controls.items():
        if name == "style":
            assert expected in STYLE_NAMES
            continue
        assert name in Controls.model_fields
        values: list[object] = [expected]
        if isinstance(expected, Span):
            assert expected.low <= expected.value <= expected.high, name
            values = [expected.value, expected.low, expected.high]
            if row.change:
                base = getattr(DEFAULTS, name)
                values = [base + expected.low, base + expected.high]
        else:
            assert not row.change, name
        for value in values:
            if name == "ramp":
                # The tables write a ramp's bars as numbers, which read as floats.
                assert isinstance(value, float)
                assert value.is_integer(), value
                value = int(value)
            ControlVector.model_validate({name: value})


def test_every_style_has_the_defaults_the_vocabulary_names() -> None:
    for style in built_in_styles().values():
        assert style.defaults == DEFAULTS, style.name


def test_full_power_plays_kick_and_backbeats_from_118_in_every_style() -> None:
    loud = {
        row.answer: energy.low
        for row in VOCABULARY_ROWS.answers
        if isinstance(energy := row.controls.get("energy"), Span) and energy.low >= FULL_POWER
    }

    assert set(loud) >= {"breakdown, full power", "big last chorus"}
    for style in built_in_styles().values():
        for role in ("kick", "backbeat"):
            for low in (FULL_POWER, *loud.values()):
                assert style.velocity[role].at(low) >= LOUD, (style.name, role, low)


TABLE = """\
## Answers

| Answer | energy | groove | dynamic_range | tightness | feel | ghost_level | Also |
|---|---|---|---|---|---|---|---|
{answers}

## Refinements

| Answer | energy | groove | dynamic_range | tightness | feel | ghost_level | Also |
|---|---|---|---|---|---|---|---|
{refinements}
"""
GOOD = '| "full power" | 0.95 [0.85, 1] | | | | +0.1 [0, 0.2] | | arc: build; skip: false |'
CHANGE = '| "a bit harder" | +0.1 [+0.05, +0.15] | | | | | | |'


def write(tmp_path: Path, answers: str = GOOD, refinements: str = CHANGE) -> Path:
    path = tmp_path / "vocabulary.md"
    path.write_text(TABLE.format(answers=answers, refinements=refinements), encoding="utf-8")
    return path


def test_a_table_reads_as_each_answer_and_the_controls_it_sets(tmp_path: Path) -> None:
    read = read_vocabulary(write(tmp_path))

    (full,) = read.answers
    (harder,) = read.refinements
    assert full.answer == "full power"
    assert full.controls == {
        "energy": Span(0.95, 0.85, 1.0),
        "feel": Span(0.1, 0.0, 0.2),
        "arc": "build",
        "skip": False,
    }
    assert harder.change
    assert harder.controls == {"energy": Span(0.1, 0.05, 0.15)}


@pytest.mark.parametrize(
    ("answers", "refinements", "why"),
    [
        ('| "loud" | 0.8 [0.85, 1] | | | | | | |', CHANGE, "outside its range"),
        ('| "loud" | 0.95 [0.85, 1.1] | | | | | | |', CHANGE, "less than or equal to 1"),
        ('| "back" | | | | | -0.4 [-1.2, 0] | | |', CHANGE, "greater than or equal to -1"),
        ('| "loud" | high | | | | | | |', CHANGE, "isn't `value [low, high]`"),
        ("| loud | 0.9 [0.8, 1] | | | | | | |", CHANGE, "isn't in double quotes"),
        ('| "loud" | 0.9 [0.8, 1] | | | | | |', CHANGE, "7 cells"),
        ('| "fill" | | | | | | | intensity: 0.8 [0.7, 1] |', CHANGE, "intensity isn't a control"),
        ('| "fill" | | | | | | | energy: 0.8 [0.7, 1] |', CHANGE, "in its own column"),
        ('| "rise" | | | | | | | arc: rise |', CHANGE, "arc 'rise'"),
        ('| "done" | | | | | | | skip: yes |', CHANGE, "isn't true or false"),
        ('| "new" | | | | | | | creative: maybe |', CHANGE, "creative 'maybe' isn't true or false"),
        ('| "tidy" | | | | | | | style: neat |', CHANGE, "isn't a built-in style"),
        (GOOD, '| "rise" | | | | | | | arc: build |', "changes numbers only"),
        (GOOD, '| "max" | +0.6 [+0.5, +0.7] | | | | | | |', "less than or equal to 1"),
        (f"{GOOD}\n{GOOD}", CHANGE, "has two rows"),
    ],
)
def test_a_value_no_control_takes_is_refused_saying_why(
    tmp_path: Path, answers: str, refinements: str, why: str
) -> None:
    with pytest.raises(VocabularyError, match=re.escape(why)):
        read_vocabulary(write(tmp_path, answers, refinements))


def test_a_missing_table_or_other_columns_are_refused(tmp_path: Path) -> None:
    path = write(tmp_path)
    text = path.read_text(encoding="utf-8")

    path.write_text(text.replace("## Refinements", "## Changes"), encoding="utf-8")
    with pytest.raises(VocabularyError, match="no '## Refinements' heading"):
        read_vocabulary(path)
    path.write_text(text.replace("| Also |", "| Other |"), encoding="utf-8")
    with pytest.raises(VocabularyError, match="the columns aren't"):
        read_vocabulary(path)
