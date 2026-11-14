"""The check of the skill's answers: the vocabulary's tables read and checked, and an agent's
controls for each answer compared with their ranges (ADR 0087).

`skills/human-o-matic/references/vocabulary.md` maps a producer's answers to controls. Its
`Answers` table gives each answer's controls, each a starting point and the range that keeps the
answer's meaning, such as `0.95 [0.85, 1]`, and its `Refinements` table gives changes to a
control's current value the same way. `read_vocabulary` reads both and checks them: each name is
a control or `style`, each value one its control or the built-in styles take, each point lies in
its range, and each range in its control's, a change's from the style's defaults.

The check puts the answers to an agent that has only the skill. `CHECKS` words each answer of the
tables as a user might, apart from the tables, and `phrases` prints them alone, so the agent
reads no range beside them. The agent gives the controls it would set for each, for a section
whose own controls and the song's are still unset, as a JSON object from each phrase to its
controls, with `style` and the song's `tightness` for an answer about the whole song's drummer.
`compare` reads that file and checks each answer's controls, clamped as the server clamps them,
with those left out taking the style's defaults:
- a control the answer's row gives lies in its range, or for a refinement, in its range of
  changes from the default;
- a control the row leaves out stays at its default.

Run from the repository root:
    uv run python tools/check_answers.py phrases            the phrases alone, one per line
    uv run python tools/check_answers.py brief              what the agent is asked, and the phrases
    uv run python tools/check_answers.py compare RESULTS    an agent's controls against the ranges
"""

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from human_o_matic.controls import ControlInput, Controls, ControlVector, StyleName, clamp
from human_o_matic.render.style import STYLE_NAMES, built_in_styles

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "human-o-matic"
SKILL = SKILL_DIR / "SKILL.md"
VOCABULARY = SKILL_DIR / "references" / "vocabulary.md"
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
EPSILON = 1e-9
EXIT_MISSES = 1
EXIT_USAGE = 2

RESULTS = TypeAdapter(dict[str, dict[str, JsonValue]])

CHECKS: tuple[tuple[str, str], ...] = (
    ("It's the breakdown, so hit as hard as you can.", "breakdown, full power"),
    ("The bridge is quiet, but it should really groove.", "bridge, low energy, high groove"),
    ("This is the final chorus, the biggest moment of the song.", "big last chorus"),
    ("In this verse, hold back and let it build up.", "verse, holding back, building"),
    ("The intro is soft, just setting the mood.", "quiet intro"),
    ("Just a solid verse, nothing fancy.", "verse, steady and solid"),
    ("The pre-chorus should lift us into the chorus.", "pre-chorus, lifting into the chorus"),
    ("A big, open chorus.", "chorus, big and open"),
    ("This part is halftime, and heavy.", "halftime, heavy"),
    ("This is the drop, everything comes in at once.", "the drop, everything hits"),
    ("The outro winds the song down.", "outro, winding down"),
    ("Maximum energy.", "full power"),
    ("Pretty hard, but leave some headroom.", "fairly hard, not all out"),
    ("Bring the ghost notes up so you can hear them.", "soft notes more present"),
    ("Keep the ghost notes in the background.", "soft notes tucked away"),
    ("Keep it even, every hit about the same.", "steady and even"),
    (
        "Make it groovier, with more difference between strong and weak hits.",
        "more groove, more light and shade",
    ),
    ("The fill should explode into the chorus.", "fill, big into the chorus"),
    ("Just a little fill, nothing flashy.", "small fill, just a turnaround"),
    ("Sit a bit behind the beat.", "laid back"),
    ("Really lazy, dragging well behind the beat.", "way behind the beat, lazy"),
    ("It should push ahead, on top of the beat.", "pushing, on top of the beat"),
    ("It should keep rising all the way through.", "building"),
    ("Let it die away by the end.", "dropping down towards the end"),
    ("Overall, tight, polished modern metal drumming.", "tight, modern metal"),
    ("Overall, loose, like a real drummer playing live in a room.", "loose, like a live drummer"),
    ("Overall, not too tight and not too loose.", "somewhere in between"),
    ("Overall, as tight as it gets, almost on the grid.", "machine tight, nearly quantized"),
    ("Whatever you think is best.", "your call"),
    ("Don't touch this one, I already finished it.", "leave this alone, it's finished"),
    ("Be more inventive with it, add some touches of your own.", "make it more creative"),
    ("Put some ghost notes into the verses.", "add ghost notes"),
    ("Add a fill wherever one section goes into the next.", "fill in the transitions"),
    ("Don't add anything, only play the notes I wrote.", "no added notes, keep what's there"),
    ("Push into the chorus across the last two bars.", "build into it over 2 bars"),
    ("Give it four bars to climb.", "a 4-bar ramp"),
    ("No build-up, just hit the chorus.", "no ramp, straight in"),
    ("Hit a little harder than that.", "a bit harder"),
    ("Ease off slightly.", "a little softer"),
    ("Tighten the timing up a little.", "a touch tighter"),
)
"""Each phrase the agent is given, and the answer of the vocabulary it means."""

BRIEF = """\
Read skills/human-o-matic/SKILL.md and skills/human-o-matic/references/vocabulary.md, and nothing
else. Each line after this paragraph is a user's whole answer to a question that skill asks. For
each, give the controls you would set: `style` and `tightness` as set_style takes them, for an
answer about the whole song's drummer, and otherwise the controls set_section_controls takes, for
a section whose own controls and the song's are still unset, at the style's defaults. Leave out
every control you would leave unset. Reply with one JSON object only, from each phrase, exactly as
written, to an object of control names and values, such as {"<phrase>": {"energy": 0.6}}.
"""


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


@dataclass(frozen=True, slots=True)
class Miss:
    """A phrase whose controls don't read as its answer does, and why."""

    phrase: str
    why: str


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


def compare(vocabulary: Vocabulary, results: Mapping[str, Mapping[str, JsonValue]]) -> list[Miss]:
    """What reads unlike its answer in an agent's controls for each phrase of `CHECKS`, in their
    order, then the phrases given that aren't checks."""
    misses: list[Miss] = []
    for phrase, answer in CHECKS:
        given = results.get(phrase)
        if given is None:
            misses.append(Miss(phrase, "no controls given"))
            continue
        misses.extend(Miss(phrase, why) for why in _problems(vocabulary.row(answer), given))
    checked = {phrase for phrase, _ in CHECKS}
    unknown = [phrase for phrase in results if phrase not in checked]
    misses.extend(Miss(phrase, "isn't a phrase of the check") for phrase in unknown)
    return misses


def _problems(row: Row, given: Mapping[str, JsonValue]) -> list[str]:
    """Why the controls given don't read as `row` does, if they don't."""
    style = given.get(STYLE)
    if style is None:
        style = DEFAULT_STYLE
    defaults_of: dict[str, Controls] = {
        name: found.defaults for name, found in built_in_styles().items()
    }
    defaults = defaults_of.get(style) if isinstance(style, str) else None
    if defaults is None:
        return [f"style {json.dumps(style)} isn't a built-in style"]
    try:
        controls = ControlInput.model_validate({k: v for k, v in given.items() if k != STYLE})
    except ValidationError as error:
        return [
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors(include_url=False)
        ]
    used = clamp(controls)[0].resolve(defaults)
    problems: list[str] = []
    meant = row.controls.get(STYLE, DEFAULT_STYLE)
    if style != meant:
        problems.append(f"style {style}, where {meant} is meant")
    for name in Controls.model_fields:
        value = getattr(used, name)
        default = getattr(defaults, name)
        expected = row.controls.get(name)
        if isinstance(expected, Span):
            span = expected.shifted(default) if row.change else expected
            if not span.low - EPSILON <= value <= span.high + EPSILON:
                problems.append(f"{name} {value:g} is outside {span.low:g} to {span.high:g}")
        elif expected is None and value != default:
            problems.append(
                f"{name} {json.dumps(value)} is set, where the answer leaves it at its default, "
                f"{json.dumps(default)}"
            )
        elif expected is not None and value != expected:
            problems.append(f"{name} {json.dumps(value)}, where {json.dumps(expected)} is meant")
    return problems


def report(misses: Sequence[Miss]) -> list[str]:
    """A line per miss, its phrase, the answer it means and why, then how many answers read as
    the vocabulary means them."""
    answers = dict(CHECKS)
    lines: list[str] = []
    for miss in misses:
        answer = answers.get(miss.phrase)
        meant = f" (meant as {json.dumps(answer)})" if answer is not None else ""
        lines.append(f"{json.dumps(miss.phrase)}{meant}: {miss.why}")
    missed = {miss.phrase for miss in misses if miss.phrase in answers}
    read = len(CHECKS) - len(missed)
    lines.append(f"{read} of {len(CHECKS)} answers read as the vocabulary means them")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The check of the skill's answers against the vocabulary's ranges."
    )
    parser.add_argument(
        "--vocabulary", type=Path, default=VOCABULARY, help="the vocabulary to check against"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("phrases", help="print the phrases alone, one per line")
    commands.add_parser("brief", help="print what the agent is asked, then the phrases")
    comparing = commands.add_parser(
        "compare", help="compare an agent's controls for each phrase with the ranges"
    )
    comparing.add_argument(
        "results", type=Path, help="a JSON file: an object from each phrase to its controls"
    )
    args = parser.parse_args(argv)
    if args.command in ("phrases", "brief"):
        if args.command == "brief":
            print(BRIEF)
        print("\n".join(phrase for phrase, _ in CHECKS))
        return 0
    try:
        vocabulary = read_vocabulary(args.vocabulary)
        for _, answer in CHECKS:
            vocabulary.row(answer)
        results = RESULTS.validate_json(args.results.read_bytes())
    except (OSError, VocabularyError, ValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    except KeyError as error:
        print(f"error: {error.args[0]}", file=sys.stderr)
        return EXIT_USAGE
    misses = compare(vocabulary, results)
    print("\n".join(report(misses)))
    return EXIT_MISSES if misses else 0


if __name__ == "__main__":
    sys.exit(main())
