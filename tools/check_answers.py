"""The check of the skill's answers: an agent's controls for each answer of the vocabulary
compared with their ranges (ADR 0087).

`skills/human-o-matic/references/vocabulary.md` maps a producer's answers to controls, each a
starting point and the range that keeps the answer's meaning, such as `0.95 [0.85, 1]`.
`human_o_matic.presets.read_vocabulary` reads its tables and checks every row.

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
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from human_o_matic.controls import ControlInput, Controls, clamp
from human_o_matic.presets import (
    DEFAULT_STYLE,
    STYLE,
    VOCABULARY,
    Row,
    Span,
    Vocabulary,
    VocabularyError,
    read_vocabulary,
)
from human_o_matic.render.style import built_in_styles
from human_o_matic.resources import skill_dir

SKILL_DIR = skill_dir()
SKILL = SKILL_DIR / "SKILL.md"
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


@dataclass(frozen=True, slots=True)
class Miss:
    """A phrase whose controls don't read as its answer does, and why."""

    phrase: str
    why: str


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
