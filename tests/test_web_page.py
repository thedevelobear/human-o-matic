"""The page's own files, read as they are served (the website plan's PRs 3 and 4): every decision
request kind has a form, each HTML page has `lang`, a label on every input, alt text on every image
and no inline script or style, the page's JavaScript keeps nothing in the browser's storage, writes
no number of the vocabulary, and sends a round only from its Submit button."""

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
    own = {"app.js", "fields.js", "forms.js", "questions.js", "review.js", "round.js", "tabs.js"}
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


def test_a_round_sends_only_from_its_submit_button() -> None:
    # Only Submit sends (ADR 0111): the tabs, their keys and Next draw, and never call `send`.
    text = (static_dir() / "js" / "round.js").read_text(encoding="utf-8")
    submit = text[text.index("function submitPanel()") : text.index("function asked()")]

    assert text.count("send(") == 1
    assert 'button.addEventListener("click"' in submit
    assert "await send(" in submit
    assert "send" not in (static_dir() / "js" / "tabs.js").read_text(encoding="utf-8")
