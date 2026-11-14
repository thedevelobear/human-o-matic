"""The presets: the vocabulary's answers and the controls each sets (ADRs 0087, 0097).

`skills/human-o-matic/references/vocabulary.md` maps a producer's answers to controls. Its
`Answers` table gives each answer's controls, each a starting point and the range that keeps the
answer's meaning, such as `0.95 [0.85, 1]`, and its `Refinements` table gives changes to a
control's current value the same way. `read_vocabulary` reads both and checks them: each name is
a control or `style`, each value one its control or the built-in styles take, each point lies in
its range, and each range in its control's, a change's from the style's defaults.

The file is the one source of the presets' numbers: `tools/check_answers.py` checks an agent's
reading of it, and the site's page offers its rows as answers through `starting_points`.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue, ValidationError

from human_o_matic.controls import Controls, ControlVector, StyleName
from human_o_matic.render.style import STYLE_NAMES, built_in_styles
from human_o_matic.resources import skill_dir

VOCABULARY = skill_dir() / "references" / "vocabulary.md"
ANSWERS = "## Answers"
REFINEMENTS = "## Refinements"
"""The headings of the two tables: absolute values, and changes to a control's current value."""
COLUMNS = (
    "Answer",
    "energy",
    "groove",
    "dynamic_range",
    "tightness",
    "feel",
    "ghost_level",
    "Also",
)
"""Each table's columns: the answer, the controls most answers set, and the rest as `name: value`
entries, separated by `; `."""
STYLE = "style"
"""`set_style`'s style, the one name a row gives that isn't a control."""
DEFAULT_STYLE: StyleName = "tight"
"""The style of a session that `set_style` hasn't changed."""
NUMBER = r"[+-]?\d+(?:\.\d+)?"
SPAN = re.compile(rf"({NUMBER}) \[({NUMBER}), ({NUMBER})\]")
ENTRY = re.compile(r"([a-z_]+): (.+)")
CHOICES = {"true": True, "false": False}
"""How `skip` and `creative` are written."""
SWITCHES = ("skip", "creative")
"""The controls that are true or false."""
WHOLE = ("ramp",)
"""The controls that are whole numbers, which the tables write as numbers like any other."""


class VocabularyError(ValueError):
    """The vocabulary's tables can't be read, or give a value no control takes."""


@dataclass(frozen=True, slots=True)
class Span:
    """A number and the range about it that keeps the answer's meaning."""

    value: float
    low: float
    high: float

    def shifted(self, by: float) -> "Span":
        return Span(self.value + by, self.low + by, self.high + by)


type Expected = Span | str | bool


@dataclass(frozen=True, slots=True)
class Row:
    """One answer and the controls it sets."""

    answer: str
    controls: Mapping[str, Expected]
    change: bool = False
    """A refinement: each number is a change to the control's current value."""


@dataclass(frozen=True, slots=True)
class Vocabulary:
    answers: tuple[Row, ...]
    refinements: tuple[Row, ...]

    @property
    def rows(self) -> tuple[Row, ...]:
        return self.answers + self.refinements

    def row(self, answer: str) -> Row:
        """The row of an answer. Raises `KeyError` when there is none."""
        for row in self.rows:
            if row.answer == answer:
                return row
        raise KeyError(f"the vocabulary has no answer {answer!r}")


def read_vocabulary(path: Path = VOCABULARY) -> Vocabulary:
    """The vocabulary's two tables, each row checked. Raises `VocabularyError`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    answers = _table(path, lines, ANSWERS, change=False)
    refinements = _table(path, lines, REFINEMENTS, change=True)
    seen: set[str] = set()
    for row in answers + refinements:
        if row.answer in seen:
            raise VocabularyError(f"{path.name}: the answer {row.answer!r} has two rows")
        seen.add(row.answer)
    return Vocabulary(answers, refinements)


def _table(path: Path, lines: Sequence[str], heading: str, *, change: bool) -> tuple[Row, ...]:
    """The rows of the table under `heading`."""
    if heading not in lines:
        raise VocabularyError(f"{path.name} has no {heading!r} heading")
    number = lines.index(heading) + 1
    while number < len(lines) and not lines[number].startswith(("|", "## ")):
        number += 1
    if number >= len(lines) or not lines[number].startswith("|"):
        raise VocabularyError(f"{path.name} has no table under {heading!r}")
    if tuple(_cells(lines[number])) != COLUMNS:
        raise VocabularyError(f"{path.name}, line {number + 1}: the columns aren't {COLUMNS}")
    rows: list[Row] = []
    number += 2
    while number < len(lines) and lines[number].startswith("|"):
        try:
            rows.append(_row(_cells(lines[number]), change=change))
        except VocabularyError as error:
            raise VocabularyError(f"{path.name}, line {number + 1}: {error}") from error
        number += 1
    return tuple(rows)


def _cells(line: str) -> list[str]:
    if not line.rstrip().endswith("|"):
        raise VocabularyError(f"the row {line!r} doesn't end with |")
    return [cell.strip() for cell in line.strip().split("|")[1:-1]]


def _row(cells: Sequence[str], *, change: bool) -> Row:
    if len(cells) != len(COLUMNS):
        raise VocabularyError(f"{len(cells)} cells, where the columns are {len(COLUMNS)}")
    quoted, *values, also = cells
    if len(quoted) < 3 or not (quoted.startswith('"') and quoted.endswith('"')):
        raise VocabularyError(f"the answer {quoted!r} isn't in double quotes")
    found: dict[str, Expected] = {}
    for name, cell in zip(COLUMNS[1:-1], values, strict=True):
        if cell:
            found[name] = _span(name, cell)
    for entry in also.split("; ") if also else ():
        matched = ENTRY.fullmatch(entry)
        if matched is None:
            raise VocabularyError(f"{entry!r} isn't `name: value`")
        name, text = matched.groups()
        if name in found or name in COLUMNS:
            raise VocabularyError(f"{name} is given in its own column or twice")
        found[name] = _expected(name, text)
    row = Row(quoted[1:-1], found, change)
    _check(row)
    return row


def _expected(name: str, text: str) -> Expected:
    if name in (STYLE, "arc"):
        return text
    if name in SWITCHES:
        if text not in CHOICES:
            raise VocabularyError(f"{name} {text!r} isn't true or false")
        return CHOICES[text]
    return _span(name, text)


def _span(name: str, text: str) -> Span:
    matched = SPAN.fullmatch(text)
    if matched is None:
        raise VocabularyError(f"{name} {text!r} isn't `value [low, high]`")
    value, low, high = (float(group) for group in matched.groups())
    if not low <= value <= high:
        raise VocabularyError(f"{name} {value:g} is outside its range, {low:g} to {high:g}")
    return Span(value, low, high)


def _check(row: Row) -> None:
    """Checks each value against its control's model, or the built-in styles."""
    defaults = built_in_styles()[DEFAULT_STYLE].defaults
    for name, expected in row.controls.items():
        if name == STYLE:
            if row.change or expected not in STYLE_NAMES:
                raise VocabularyError(f"style {expected!r} isn't a built-in style")
            continue
        if name not in Controls.model_fields:
            raise VocabularyError(f"{name} isn't a control")
        if isinstance(expected, Span):
            if row.change:
                default = getattr(defaults, name)
                if not isinstance(default, float):
                    raise VocabularyError(f"{name} isn't a number to change")
                values = (default + expected.low, default + expected.high)
            else:
                values = (expected.value, expected.low, expected.high)
        elif row.change:
            raise VocabularyError(f"a refinement changes numbers only, not {name}")
        else:
            values = (expected,)
        for value in values:
            if name in WHOLE and isinstance(value, float) and value.is_integer():
                value = int(value)
            try:
                ControlVector.model_validate({name: value})
            except ValidationError as error:
                problem = error.errors(include_url=False)[0]["msg"]
                raise VocabularyError(f"{name} {value!r}: {problem}") from error


def starting_points(vocabulary: Vocabulary) -> dict[str, JsonValue]:
    """Each row of the tables as its answer and the controls it sets at their starting points: a
    number at its point, a ramp in whole bars, and a style, an arc or a switch as it is. A
    refinement's numbers are changes to a control's current value."""

    def point(name: str, expected: Expected) -> JsonValue:
        if not isinstance(expected, Span):
            return expected
        return int(expected.value) if name in WHOLE else expected.value

    def rows(found: Sequence[Row]) -> list[JsonValue]:
        return [
            {
                "answer": row.answer,
                "controls": {name: point(name, value) for name, value in row.controls.items()},
            }
            for row in found
        ]

    return {"answers": rows(vocabulary.answers), "refinements": rows(vocabulary.refinements)}
