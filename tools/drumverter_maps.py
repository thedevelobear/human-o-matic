"""Build the built-in maps that come from drumverter's note maps (ADRs 0137 and 0138).

Drumverter publishes a note map of every drum engine it converts between, under the MIT licence,
in its source's `engines/` folder, the same maps as the `.txt` files of its drum maps page. This
downloads that source at the commit `tools/drumverter_maps.toml` pins into `build/drumverter/`,
gitignored, checked by its SHA-256, names each engine's notes in the vocabulary by `named`, and
writes `data/maps/<library>.toml` for each library the file lists. It refuses a map the loader
rejects. `--check` writes nothing, and exits 1 when a committed map differs from what it builds.

Run from the repository root:
    uv run python tools/drumverter_maps.py [--check]
"""

import argparse
import re
import sys
import tarfile
import textwrap
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from build_site import Pin, fetched
from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_vocabulary
from human_o_matic.maps.schema import Library
from human_o_matic.maps.vocabulary import MapError, Vocabulary

ROOT = Path(__file__).resolve().parents[1]
PINS = ROOT / "tools" / "drumverter_maps.toml"
DOWNLOADS = ROOT / "build" / "drumverter"
MAPS = ROOT / "data" / "maps"
WIDTH = 100

DEGREES = {0.25: "open.quarter", 0.5: "open.half", 0.75: "open.three_quarter", 1.0: "open"}
"""A hat's openings in the vocabulary, by how open each is."""
PERCUSSION = {
    "perc.cowbell": "cowbell.hit",
    "perc.clap": "clap.hit",
    "perc.shaker": "maracas.hit",
    "perc.sticks": "sticks.hit",
    "perc.tambourine": "tambourine.hit",
    "perc.vibraslap": "vibraslap.hit",
    "perc.claves": "claves.hit",
    "perc.bongo.high": "bongo.1.hit",
    "perc.bongo.low": "bongo.2.hit",
    "perc.conga.high": "conga.1.open",
    "perc.conga.high.mute": "conga.1.mute",
    "perc.conga.low": "conga.2.open",
    "perc.timbale.high": "timbale.1.hit",
    "perc.timbale.low": "timbale.2.hit",
    "perc.agogo.high": "agogo.1.hit",
    "perc.agogo.low": "agogo.2.hit",
    "perc.woodblock.high": "woodblock.1.hit",
    "perc.woodblock.low": "woodblock.2.hit",
    "perc.whistle.short": "whistle.short",
    "perc.whistle.long": "whistle.long",
    "perc.guiro.short": "guiro.short",
    "perc.guiro.long": "guiro.long",
    "perc.cuica": "cuica.open",
    "perc.cuica.mute": "cuica.mute",
    "perc.triangle": "triangle.open",
    "perc.triangle.mute": "triangle.mute",
}
SNARE = {
    "hit": "center",
    "rimshot": "rimshot",
    "sidestick": "sidestick",
    "rim": "rim",
    "flam": "flam",
    "off": "offcenter",
}
HATS = {"hat": "hat", "aux1": "hat.2", "aux2": "hat.3"}
"""The main hi-hat, and drumverter's auxiliary hats as the kit's second and third."""
HAT = {"closed": "closed", "tight": "tight", "pedal": "pedal", "pedalsplash": "pedal.splash"}
CYMBAL = {"hit": "hit", "mute": "choke", "bowtip": "hit.tip"}
RIDE = {"bell": "bell", "belltip": "bell.tip", "edge": "crash", "mute": "choke"}


class Note(BaseModel):
    """A note of a drumverter engine map, and the drum it names in drumverter's own canon."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    note: int
    canon: str
    primary: bool = False


class Engine(BaseModel):
    """A drumverter engine map, `engines/<id>.toml` in its source."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    name: str
    notes: tuple[Note, ...]


class KitPin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    engine: str


class Maker(BaseModel):
    """What the library's maker publishes about its notes, which wins over drumverter's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document: str
    high: tuple[int, ...] = ()
    """Notes the maker names as the vocabulary does, the same as drumverter's."""
    leave_out: dict[str, str] = {}
    """Notes the maker names otherwise than drumverter, and the vocabulary can't name."""


class LibraryPin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    kits: tuple[KitPin, ...]
    maker: Maker | None = None


class Pins(BaseModel):
    """`tools/drumverter_maps.toml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Pin
    """drumverter's source at one commit, its `version`."""
    libraries: tuple[LibraryPin, ...]


@dataclass(frozen=True)
class Named:
    """An engine's notes in the vocabulary: each name with its notes, the written one first, and
    each note left out with why."""

    names: dict[str, tuple[int, ...]]
    left_out: dict[int, str]

    def without(self, left_out: dict[int, str]) -> "Named":
        """The same, with these notes left out for these reasons."""
        names = {
            name: kept
            for name, notes in self.names.items()
            if (kept := tuple(note for note in notes if note not in left_out))
        }
        return Named(names, dict(sorted((self.left_out | left_out).items())))


def read_pins(path: Path = PINS) -> Pins:
    with path.open("rb") as file:
        return Pins.model_validate(tomllib.load(file))


def read_engines(archive: Path) -> dict[str, Engine]:
    """Every engine map in drumverter's source archive, by its id."""
    engines: dict[str, Engine] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile() and re.fullmatch(r"[^/]+/engines/[^/]+\.toml", member.name):
                file = tar.extractfile(member)
                if file is not None:
                    engine = Engine.model_validate(tomllib.loads(file.read().decode()))
                    engines[engine.id] = engine
    return engines


def _rung(canon: str) -> tuple[str, int, str] | None:
    """A hat played loose or open: the hat, its rung counted from loose as 0, and the zone."""
    found = re.fullmatch(r"(hat|aux1|aux2)\.(loose|open(\d))(?:\.(tip|edge|bell))?", canon)
    if found is None:
        return None
    return found[1], int(found[3] or 0), found[4] or "edge"


def _openings(canons: Sequence[str]) -> dict[tuple[str, int], str]:
    """Each rung of each hat as the vocabulary's opening: the rungs spread from the least open,
    the most open being fully open, each at the nearest opening (ADR 0137)."""
    rungs: dict[str, set[int]] = {}
    for canon in canons:
        if (found := _rung(canon)) is not None:
            rungs.setdefault(found[0], set()).add(found[1])
    openings: dict[tuple[str, int], str] = {}
    for hat, numbers in rungs.items():
        for index, rung in enumerate(sorted(numbers)):
            share = (index + 1) / len(numbers)
            openings[hat, rung] = DEGREES[min(DEGREES, key=lambda d: (abs(d - share), d))]
    return openings


def _name(
    canon: str, canons: Sequence[str], toms: dict[str, int], openings: dict[tuple[str, int], str]
) -> str:
    """The vocabulary's name for a drumverter canon, or `!` and why it has none."""
    parts = canon.split(".")
    head = parts[0]
    if canon in PERCUSSION:
        return PERCUSSION[canon]
    if head == "perc":
        return "!percussion"
    if head == "kick":
        return {"main": "kick.hit", "left": "kick.hit.left"}.get(parts[1], "!alternate kick")
    if head in ("snare1", "snare2"):
        stroke = SNARE.get(parts[1])
        prefix = "snare" if head == "snare1" else "snare.2"
        return f"{prefix}.{stroke}" if stroke else f"!snare {parts[1]}"
    if head == "tom":
        return f"tom.{toms[parts[1]]}.{parts[2]}"
    if head in HATS:
        if (rung := _rung(canon)) is not None:
            opening, zone = openings[rung[0], rung[1]], rung[2]
        elif parts[1] == "cc":
            opening, zone = "variable", parts[2] if len(parts) > 2 else "edge"
        else:
            opening, zone = HAT[parts[1]], parts[2] if len(parts) > 2 else "edge"
        if zone == "bell":
            return "!hi-hat bell"
        if zone == "tip" and opening == "open.three_quarter":
            return "!three-quarter-open hi-hat tip"
        return f"{HATS[head]}.{opening}" + (".tip" if zone == "tip" else "")
    if head == "ride":
        stroke = parts[2] if len(parts) > 2 else "bow"
        if stroke == "bow" or (stroke == "bowtip" and f"ride.{parts[1]}" not in canons):
            return f"ride.{parts[1]}.bow"
        return f"ride.{parts[1]}.{RIDE[stroke]}" if stroke in RIDE else "!ride bow tip"
    if head in ("crash", "china", "splash", "stack"):
        stroke = CYMBAL.get(parts[2])
        allowed = {"crash": ("hit", "choke", "hit.tip"), "stack": ("hit", "hit.tip")}
        if stroke is None or stroke not in allowed.get(head, ("hit", "choke")):
            return f"!{head} {parts[2]}"
        return f"{head}.{parts[1]}.{stroke}"
    return f"!{head}"


def named(engine: Engine, vocabulary: Vocabulary) -> Named:
    """The engine's notes in the vocabulary (ADR 0137). Toms are numbered along the kit, rack
    toms then floor toms, and the pieces of every family from 1 in drumverter's order. A tip
    stroke a kit has without its plain stroke is that plain stroke, and a stroke whose piece has
    no default stroke is left out."""
    canons = list(dict.fromkeys(note.canon for note in engine.notes))
    toms = sorted(
        {canon.split(".")[1] for canon in canons if canon.startswith("tom.")},
        key=lambda tom: (tom.startswith("floor"), int(tom[-1])),
    )
    openings = _openings(canons)
    numbers = {tom: index + 1 for index, tom in enumerate(toms)}
    names: dict[str, list[int]] = {}
    left_out: dict[int, str] = {}
    for note in sorted(engine.notes, key=lambda note: not note.primary):
        name = _name(note.canon, canons, numbers, openings)
        if name.startswith("!"):
            left_out[note.note] = name[1:]
        else:
            names.setdefault(name, []).append(note.note)
    names = _renumbered(names, vocabulary)
    # Longest first, so a tip stroke reaches its plain stroke before that is looked at.
    for name in sorted(names, key=len, reverse=True):
        parsed = vocabulary.parse(name)
        parent = vocabulary.name(parsed.family, parsed.piece, parsed.path[:-1] or parsed.path).text
        if parsed.variants[-1:] == ("tip",) and parent not in names:
            names[parent] = names.pop(name)
    # A hat with a tight stroke and no closed one plays its tight stroke as its closed one.
    tight = [name for name in names if name.startswith("hat") and ".tight" in name]
    for name in [name for name in tight if f"{name.split('.tight')[0]}.closed" not in names]:
        names[name.replace(".tight", ".closed")] = names.pop(name)
    for name in sorted(names, key=len):
        parsed = vocabulary.parse(name)
        parent = vocabulary.name(parsed.family, parsed.piece, parsed.path[:-1] or parsed.path).text
        default = vocabulary.default(parsed.family, parsed.piece).text
        missing = parent if parsed.variants and parent not in names else default
        if missing not in names:
            left_out.update(dict.fromkeys(names.pop(name), f"{name} without {missing}"))
    order = {note.note: index for index, note in enumerate(engine.notes)}
    return Named(
        names={
            name: (notes[0], *sorted(notes[1:], key=order.__getitem__))
            for name, notes in names.items()
        },
        left_out=dict(sorted(left_out.items())),
    )


def _renumbered(names: dict[str, list[int]], vocabulary: Vocabulary) -> dict[str, list[int]]:
    """The names with each family's pieces numbered from 1, keeping their order."""
    parsed = {name: vocabulary.parse(name) for name in names}
    pieces: dict[str, list[int]] = {}
    for name in parsed.values():
        pieces.setdefault(name.family, [])
        if name.piece not in pieces[name.family]:
            pieces[name.family].append(name.piece)
    renumbered: dict[str, list[int]] = {}
    for text, name in parsed.items():
        piece = sorted(pieces[name.family]).index(name.piece) + 1
        renumbered.setdefault(vocabulary.name(name.family, piece, name.path).text, []).extend(
            names[text]
        )
    return renumbered


def _sort_key(name: str, vocabulary: Vocabulary) -> tuple[int, int, int]:
    parsed = vocabulary.parse(name)
    family = vocabulary.families[parsed.family]
    return (
        list(vocabulary.families).index(parsed.family),
        parsed.piece,
        family.articulations.index(".".join(parsed.path)),
    )


def _comment(text: str, indent: str = "") -> str:
    return "\n".join(
        textwrap.wrap(text, WIDTH, initial_indent=f"{indent}# ", subsequent_indent=f"{indent}# ")
    )


def _left_out(named: Named) -> str:
    reasons: dict[str, list[int]] = {}
    for note, reason in named.left_out.items():
        reasons.setdefault(reason, []).append(note)
    return "; ".join(f"{reason}, {', '.join(map(str, notes))}" for reason, notes in reasons.items())


def render(
    library: LibraryPin, engines: dict[str, Engine], pins: Pins, vocabulary: Vocabulary
) -> str:
    """The map file of a library, from its engines' maps."""
    maker = library.maker
    header = (
        f"{library.name}, from drumverter's note map of it (ADRs 0137 and 0138), at its source's "
        f"commit {pins.source.version[:12]}. Each name is drumverter's, read into the "
        "vocabulary, so it is medium confidence"
        + (
            f", or high where {maker.document} names the same stroke as the vocabulary does. "
            "Where it names a note otherwise and the vocabulary has no name for it, the note is "
            "left out"
            if maker
            else ""
        )
        + ". Where an articulation has several notes, the first is the one written and the "
        "others are only read. A note left out is asked about. Built by "
        "tools/drumverter_maps.py: change it there and build it again, rather than editing this "
        "file."
    )
    lines = [_comment(header), "schema = 1", f'id = "{library.id}"', f'name = "{library.name}"']
    high: set[int] = set(maker.high) if maker else set()
    for kit in library.kits:
        engine = engines[kit.engine]
        built = named(engine, vocabulary).without(
            {int(note): reason for note, reason in maker.leave_out.items()} if maker else {}
        )
        count = sum(len(notes) for notes in built.names.values())
        about = (
            f"{kit.name}: drumverter's {engine.id}, {engine.name}. {len(engine.notes)} notes, of "
            f"which {count} are named here as {len(built.names)} articulations."
        )
        if built.left_out:
            about += f" Left out: {_left_out(built)}."
        lines += ["", _comment(about), "[[kits]]", f'id = "{kit.id}"', f'name = "{kit.name}"']
        for name in sorted(built.names, key=lambda name: _sort_key(name, vocabulary)):
            notes = built.names[name]
            confidence = "high" if set(notes) <= high else "medium"
            lines += ["", "  [[kits.articulations]]", f'  name = "{name}"']
            lines.append(f"  notes = [{', '.join(map(str, notes))}]")
            if vocabulary.parse(name).articulation == "variable":
                lines.append('  cc = { mode = "shape" }')
            lines += ['  source = "mapping"', f'  confidence = "{confidence}"']
    text = "\n".join(lines) + "\n"
    spec = Library.model_validate(tomllib.loads(text))
    for kit in spec.kits:
        DrumKit(spec, kit, vocabulary)
    return text


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the maps that come from drumverter's.")
    parser.add_argument("--check", action="store_true", help="compare, and write nothing")
    args = parser.parse_args(argv)
    try:
        pins = read_pins()
        engines = read_engines(fetched(pins.source, DOWNLOADS))
        vocabulary = built_in_vocabulary()
        built = {pin.id: render(pin, engines, pins, vocabulary) for pin in pins.libraries}
    except (OSError, ValueError, KeyError, MapError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    differing = 0
    for library, text in built.items():
        path = MAPS / f"{library}.toml"
        same = path.is_file() and path.read_text(encoding="utf-8") == text
        if args.check:
            if not same:
                differing += 1
                print(f"differs: {path.relative_to(ROOT)}")
        elif not same:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    print(f"{len(built)} maps, {differing} differing" if args.check else f"{len(built)} maps")
    return 1 if differing else 0


if __name__ == "__main__":
    sys.exit(main())
