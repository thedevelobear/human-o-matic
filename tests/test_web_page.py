"""The page's own files, read as they are served (the website plan's PRs 3 and 4): every decision
request kind has a form, each HTML page has `lang`, a label on every input, alt text on every image
and no inline script or style, the page's JavaScript keeps nothing in the browser's storage, writes
no number of the vocabulary, applies a round only as the page moves on, and keeps its drafts
until the song is opened again."""

import gzip
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
VOID = {"meta", "link", "input", "br", "hr", "img", "source", "wbr"}
"""Elements with no end tag, so never anyone's ancestor."""
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
        self.within: dict[str, list[str]] = {}
        """Each id's ancestors' ids."""
        self.open: list[str] = []
        self.labels = 0
        self.script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        self.elements.append((tag, attributes))
        if "id" in attributes:
            self.within[attributes["id"]] = [found for found in self.open if found]
        if tag not in VOID:
            self.open.append(attributes.get("id", ""))
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
        if tag not in VOID:
            self.open.pop()
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


FONTS = (
    "https://fonts.googleapis.com/css2?family=Fredoka:wght@600;700&family=Space+Grotesk:wght@500;"
    "600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap"
)
SCRIPTS = {
    "check.html": [{"type": "module", "src": "js/check.js"}],
    "index.html": [{"type": "module", "src": "js/app.js"}],
}
LINKS = {
    "check.html": [],
    "index.html": [
        {"rel": "stylesheet", "href": FONTS},
        {"rel": "stylesheet", "href": "tailwind.css"},
    ],
}
"""What each page loads (ADR 0126): of others', Google Fonts' stylesheet alone, and the rest its own
files, Tailwind's CSS among them."""


@pytest.mark.parametrize("path", PAGES, ids=lambda path: path.name)
def test_a_page_loads_only_its_own_files_and_google_fonts_and_holds_no_inline_code(
    path: Path,
) -> None:
    page = parsed(path)

    assert [text.strip() for text in page.scripts] == [""] * len(page.scripts)
    assert [attributes for tag, attributes in page.elements if tag == "script"] == SCRIPTS[
        path.name
    ]
    assert [attributes for tag, attributes in page.elements if tag == "link"] == LINKS[path.name]
    for tag, attributes in page.elements:
        assert tag != "style", path.name
        assert "style" not in attributes, (path.name, tag)
        assert not [name for name in attributes if name.startswith("on")], (path.name, tag)


INDEX = static_dir() / "index.html"
TAILWIND = static_dir().parent / "tailwind"
"""The input stylesheet and configuration of `tailwind.css` (ADR 0126)."""


def test_every_drawing_of_the_page_is_hidden_from_assistive_technology() -> None:
    page = parsed(INDEX)
    drawings = [attributes for tag, attributes in page.elements if tag == "svg"]
    uses = [attributes["href"] for tag, attributes in page.elements if tag == "use"]

    assert drawings
    assert [attributes for attributes in drawings if attributes.get("aria-hidden") != "true"] == []
    # The owner's mascot, defined once, on the loading view and in the top bar.
    assert uses.count("#mascot") == 2


def test_the_page_shows_the_loading_view_alone_until_the_engine_is_ready() -> None:
    page = parsed(INDEX)
    by_id = {
        attributes["id"]: (tag, attributes)
        for tag, attributes in page.elements
        if "id" in attributes
    }
    loading = (static_dir() / "js" / "app.js").read_text(encoding="utf-8")
    shown = loading[
        loading.index("function loading(") : loading.index("/** One call of the worker API")
    ]

    assert "hidden" not in by_id["loading"][1]
    assert {"hidden", "inert"} <= set(by_id["app"][1])
    # The bar starts empty, before the page's script runs, until the engine's first step says
    # how far it is.
    assert by_id["engine"][0] == "progress"
    assert by_id["engine"][1].get("value") == "0"
    assert "app" not in page.within["engine"]
    for inside in ("steps", "status", "file", "kits", "check", "drummer", "sections", "review"):
        assert "app" in page.within[inside], inside
    for inside in ("download", "delete-box", "toast", "delete-dialog"):
        assert "app" in page.within[inside], inside
    assert '$("#app").inert = !ready;' in shown
    assert '$("#app").hidden = !ready;' in shown
    assert loading.count(".inert") == 1


def luminance(colour: str) -> float:
    channels = [int(colour[at : at + 2], 16) / 255 for at in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(one: str, other: str) -> float:
    light, dark = sorted((luminance(one), luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def over(colour: str, under: str, alpha: float) -> str:
    mixed = [
        round(alpha * int(colour[at : at + 2], 16) + (1 - alpha) * int(under[at : at + 2], 16))
        for at in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def test_the_palette_s_text_is_at_least_4_5_to_1_and_its_focus_ring_3_to_1() -> None:
    # WCAG 2's contrast of each text colour on each surface it sits on, from the tokens of
    # Tailwind's input stylesheet and the colours of its configuration (ADRs 0125 and 0126).
    css = (TAILWIND / "input.css").read_text(encoding="utf-8")
    root = re.search(r":root \{(.*?)\}", css, re.DOTALL)
    assert root is not None
    token = {
        name: value.lower()
        for name, value in re.findall(r"--([\w-]+): (#[0-9a-f]{6});", root.group(1))
    }
    config = (TAILWIND / "tailwind.config.js").read_text(encoding="utf-8")
    tailwind = {
        name: value.lower() for name, value in re.findall(r'(\w+): "(#[0-9A-F]{6})"', config)
    }
    ink = tailwind["ink"]
    surfaces = ["bg-parchment", "surface-cream", "surface-well", "soft-1", "soft-2", "soft-3"]
    opacities = {
        int(found) for found in re.findall(r"text-ink/(\d+)", INDEX.read_text(encoding="utf-8"))
    }

    assert ink == token["ink-black"]
    for surface in (token[name] for name in surfaces):
        assert contrast(ink, surface) >= 4.5, surface
        assert contrast(token["ink-muted"], surface) >= 4.5, surface
        assert contrast(token["focus-violet"], surface) >= 3, surface
        for alpha in opacities:
            assert contrast(over(ink, surface, alpha / 100), surface) >= 4.5, (surface, alpha)
    for under in ("pill-start", "sunset-orange", "vibrant-magenta", "pill-end"):
        assert contrast(ink, token[under]) >= 4.5, under
    for surface in (token["surface-cream"], token["bg-parchment"], "#fde8ec"):
        assert contrast(token["error-red"], surface) >= 4.5, surface
    assert opacities
    assert min(opacities) >= 75


REDUCED = "@media (prefers-reduced-motion: no-preference) {"


def without_block(text: str, opening: str) -> str:
    """`text` without the block that `opening` starts, to its matching brace."""
    start = text.index(opening)
    depth = 0
    for end, char in enumerate(text[start:], start):
        depth += {"{": 1, "}": -1}.get(char, 0)
        if char == "}" and depth == 0:
            return text[:start] + text[end + 1 :]
    raise ValueError(opening)


def test_nothing_moves_unless_the_reader_allows_motion() -> None:
    # Every animation and transition is inside `prefers-reduced-motion: no-preference`, in
    # Tailwind's input stylesheet, and the page uses none of Tailwind's own (ADR 0125).
    css = (TAILWIND / "input.css").read_text(encoding="utf-8")
    outside = without_block(css, REDUCED)
    classes = re.findall(r'class="([^"]*)"', INDEX.read_text(encoding="utf-8"))
    tailwind = [
        name
        for found in classes
        for name in found.split()
        if re.match(r"(animate|transition|duration)-", name)
    ]

    assert css.count(REDUCED) == 1
    assert not re.search(r"\b(animation|transition)\s*:|@keyframes", COMMENT.sub("", outside))
    assert set(tailwind) == {"animate-bob", "animate-sparkle"}


def test_the_page_s_own_files_are_within_300_kb_compressed() -> None:
    # Tailwind's CSS is the page's own (ADR 0126); Google's fonts come from their host, outside
    # this count.
    own = [path for path in static_dir().rglob("*") if path.is_file()]
    compressed = sum(len(gzip.compress(path.read_bytes(), 9)) for path in own)

    assert compressed <= 300_000, compressed


STORAGE = re.compile(r"\b(localStorage|sessionStorage|indexedDB|caches)\b")
"""The browser's storage, which the page never uses (the website plan's section 8)."""


def test_the_page_s_javascript_keeps_nothing_in_the_browser_s_storage() -> None:
    own = {
        "app.js",
        "fields.js",
        "forms.js",
        "loading.js",
        "questions.js",
        "review.js",
        "round.js",
    }
    assert own <= {path.name for path in MODULES}
    for path in MODULES:
        found = STORAGE.findall(path.read_text(encoding="utf-8"))
        assert found == [], path.name


STYLED = re.compile(r"\.style\s*[.=[]|setAttribute\(.style.|(?:inner|outer)HTML|insertAdjacentHTML")
"""A style set from script, which the CSP allows only from tailwind.css, or HTML written as text."""


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
