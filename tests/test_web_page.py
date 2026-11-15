"""The page's own files, read as they are served (the website plan's PRs 3 and 4): every decision
request kind has a form, each HTML page has `lang`, a label on every input, alt text on every image
and no inline script or style, the page's JavaScript keeps nothing in the browser's storage, writes
no number of the vocabulary, applies a round only as the page moves on, and keeps its drafts
until the song is opened again."""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import get_args

import pytest

from human_o_matic.decisions import DecisionKind
from human_o_matic.presets import Span, read_vocabulary
from human_o_matic.web import static_dir

PAGES = sorted(static_dir().glob("*.html"))
MODULES = sorted((static_dir() / "js").glob("*.js"))
UNLABELLED = {"hidden", "submit", "button", "reset", "image"}
"""Input types that are buttons or hold nothing to fill in, so need no label."""


def requests_with_forms() -> list[str]:
    """The kinds `REQUESTS` in `js/forms.js` gives a form, each a key at its first indent."""
    text = (static_dir() / "js" / "forms.js").read_text(encoding="utf-8")
    block = re.search(r"^export const REQUESTS = \{\n(.*?)^\};", text, re.MULTILINE | re.DOTALL)
    assert block is not None
    return re.findall(r"^  (\w+): \{", block.group(1), re.MULTILINE)


def test_every_decision_request_kind_has_a_form_of_its_own() -> None:
    # A new kind fails this until forms.js gives it a form; until then the page shows its
    # message and options.
    assert sorted(requests_with_forms()) == sorted(get_args(DecisionKind.__value__))


class Page(HTMLParser):
    """A page's elements, by tag and attributes, with the labels that name its inputs."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str]]] = []
        self.labelled: set[str] = set()
        """The ids a `<label for>` names."""
        self.wrapped: list[tuple[str, dict[str, str]]] = []
        """The inputs inside a `<label>`."""
        self.scripts: list[str] = []
        """The text inside each `<script>`."""
        self.labels = 0
        self.script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        self.elements.append((tag, attributes))
        if tag == "label":
            self.labels += 1
            if "for" in attributes:
                self.labelled.add(attributes["for"])
        elif self.labels and tag in ("input", "select", "textarea"):
            self.wrapped.append((tag, attributes))
        if tag == "script":
            self.script = True
            self.scripts.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self.labels -= 1
        if tag == "script":
            self.script = False

    def handle_data(self, data: str) -> None:
        if self.script:
            self.scripts[-1] += data


def parsed(path: Path) -> Page:
    page = Page()
    page.feed(path.read_text(encoding="utf-8"))
    page.close()
    return page


def test_the_pages_are_index_html_and_the_engine_check() -> None:
    assert [path.name for path in PAGES] == ["check.html", "index.html"]


@pytest.mark.parametrize("path", PAGES, ids=lambda path: path.name)
def test_a_page_has_lang_a_label_on_every_input_and_alt_text_on_every_image(path: Path) -> None:
    page = parsed(path)

    assert [attributes.get("lang") for tag, attributes in page.elements if tag == "html"] == ["en"]
    inputs = [
        (tag, attributes)
        for tag, attributes in page.elements
        if tag in ("select", "textarea")
        or (tag == "input" and attributes.get("type", "text") not in UNLABELLED)
    ]
    for tag, attributes in inputs:
        named = (
            attributes.get("id") in page.labelled
            or (tag, attributes) in page.wrapped
            or attributes.get("aria-label")
            or attributes.get("aria-labelledby")
        )
        assert named, (path.name, tag, attributes)
    for tag, attributes in page.elements:
        if tag == "img":
            assert attributes.get("alt"), (path.name, attributes)


@pytest.mark.parametrize("path", PAGES, ids=lambda path: path.name)
def test_a_page_has_no_inline_script_or_style(path: Path) -> None:
    page = parsed(path)

    assert page.scripts, path.name
    assert [text.strip() for text in page.scripts] == [""] * len(page.scripts)
    for tag, attributes in page.elements:
        assert tag != "style", path.name
        assert "style" not in attributes, (path.name, tag)
        assert not [name for name in attributes if name.startswith("on")], (path.name, tag)
        if tag == "script":
            assert attributes.get("type") == "module", path.name
            assert attributes["src"].startswith("js/"), path.name
        if tag == "link":
            assert attributes == {"rel": "stylesheet", "href": "site.css"}, path.name


STORAGE = re.compile(r"\b(localStorage|sessionStorage|indexedDB|caches)\b")
"""The browser's storage, which the page never uses (the website plan's section 8)."""


def test_the_page_s_javascript_keeps_nothing_in_the_browser_s_storage() -> None:
    own = {"app.js", "fields.js", "forms.js", "questions.js", "review.js", "round.js"}
    assert own <= {path.name for path in MODULES}
    for path in MODULES:
        found = STORAGE.findall(path.read_text(encoding="utf-8"))
        assert found == [], path.name


STYLED = re.compile(r"\.style\s*[.=[]|setAttribute\(.style.|(?:inner|outer)HTML|insertAdjacentHTML")
"""A style set from script, which the CSP allows only from site.css, or HTML written as text."""


def test_the_page_s_javascript_sets_no_style_and_writes_no_html() -> None:
    for path in MODULES:
        assert STYLED.findall(path.read_text(encoding="utf-8")) == [], path.name


COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
DECIMAL = re.compile(r"(?<![\w.])\d*\.\d+")


def test_the_page_writes_no_number_of_the_vocabulary() -> None:
    # The rows' numbers reach the page through the worker's `presets` call alone (the website
    # plan's section 6). Whole numbers such as 0, 1 and a ramp's bars are too common to tell
    # apart, so the scan reads the numbers with a decimal point in each module's code.
    numbers = {
        number
        for row in read_vocabulary().rows
        for value in row.controls.values()
        if isinstance(value, Span)
        for number in (value.value, value.low, value.high)
        if not float(number).is_integer()
    }
    assert numbers
    for path in MODULES:
        code = COMMENT.sub("", path.read_text(encoding="utf-8"))
        found = {float(text) for text in DECIMAL.findall(code)}
        assert found & {abs(number) for number in numbers} == set(), path.name


def test_a_round_sends_nothing_itself() -> None:
    # A round's answers are a draft it hands the page (ADR 0124): only app.js calls the engine.
    text = (static_dir() / "js" / "round.js").read_text(encoding="utf-8")

    assert not re.search(r"\bsend\b|\bask\(|postMessage", text)
    assert "keep(tabs, now)" in text


FUNCTION = re.compile(r"^(?:async )?function (\w+)\(.*?^\}", re.MULTILINE | re.DOTALL)
CALL = re.compile(r"\bask\(\s*([^,)]+)")


def test_app_js_applies_a_round_only_as_the_page_moves_on() -> None:
    # The rounds' controls go to the engine through songCalls and groupCalls, from sendSong and
    # sendGroup, which are a drawn round's `send`, called by applyRound in leave() alone, which
    # moveOn() alone calls; every handler at the top level that changes the step or the group goes
    # through moveOn, and none calls the engine itself (ADR 0124). The page's other calls read,
    # edit sections, take or check.
    text = (static_dir() / "js" / "app.js").read_text(encoding="utf-8")
    functions = {found.group(1): found.group(0) for found in FUNCTION.finditer(text)}
    calls = {name: CALL.findall(body) for name, body in functions.items()}
    top = FUNCTION.sub("", text)

    assert "set_section_controls" not in text
    assert CALL.findall(top) == []
    assert {name for name, made in calls.items() if "call" in made} == {
        "ask",
        "confirmCheck",
        "sendSong",
        "sendGroup",
    }
    rounds = re.compile(r"\b(song|group)Calls\(")
    assert {name for name, body in functions.items() if rounds.search(body)} == {
        "sendSong",
        "sendGroup",
    }
    # Each is named twice: where it is defined, and as a drawn round's `send`.
    assert text.count("sendSong") == 2
    assert "send: sendSong," in text
    assert text.count("sendGroup") == 2
    assert "send: (tabs, draft) => sendGroup(" in text
    using = {
        called: {name for name, body in functions.items() if f"{called}(" in body} - {called}
        for called in ("applyRound", "leave", "drawRound")
    }
    assert using == {"applyRound": {"leave"}, "leave": {"moveOn"}, "drawRound": {"drawShown"}}
    assert top.count("go(") == len(re.findall(r"moveOn\((?:true|false), \(\) => go\(", top)) > 0
    assert "pick(" not in top.replace("moveOn(false, () => pick(", "").replace("return pick(", "")
    styled = [
        (name, re.search(r'ask\("set_style", \{([^}]*)\}', body))
        for name, body in functions.items()
        if '"set_style"' in body
    ]
    assert [(name, found and found.group(1).strip()) for name, found in styled] == [
        ("drawDrummer", "session_id: page.session"),
        ("songTake", "session_id: page.session, seed: page.seed + 1"),
    ]


def test_app_js_keeps_the_drafts_until_the_song_is_opened_again() -> None:
    # The rounds' drafts are dropped only when the song is opened again, or by "Delete my file
    # now" through fresh(), and a section edit keeps them, and what a round set, over the sections
    # it leaves as they were, once the engine has taken it (ADRs 0122 and 0124).
    text = (static_dir() / "js" / "app.js").read_text(encoding="utf-8")
    functions = {found.group(1): found.group(0) for found in FUNCTION.finditer(text)}

    emptied = {name for name, body in functions.items() if "rounds: {}" in body}
    assert emptied == {"fresh", "openSong"}
    assert {name for name, body in functions.items() if "page.rounds =" in body} == {"edit"}
    edit = functions["edit"]
    sent = edit.find("page.sent = keptAfterEdit(page.sent, sections, reply.sections)")
    kept = edit.find("page.rounds = roundsAfterEdit(page.rounds, sections, reply.sections)")
    assert 0 <= edit.index('ask("update_sections"') < edit.index("if (failed(reply))") < sent < kept
