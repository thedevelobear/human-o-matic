"""The canonical articulation vocabulary: the names maps use as the pivot between libraries.

A name is `family[.piece].articulation[.variant...]`, in lower case with `_` inside a word, such
as `snare.center`, `crash.1.choke` or `hat.open.quarter.tip`. The family is the kind of drum or
cymbal, which a conversion never leaves. The piece numbers a family's drums or cymbals from 1,
the highest-pitched tom or the first cymbal of a kind. The articulation is what is played, and
each variant refines it and can be dropped. A bare name is the library's ordinary stroke.

The vocabulary is data, in `data/vocabulary.toml`, and is validated when it loads.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

WORD = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
"""One part of a name other than the piece number."""
PIECE = re.compile(r"[0-9]+")

type PieceRule = Literal["numbered", "second", "single"]
type PieceSubstitution = Literal["nearest", "register"]


class MapError(ValueError):
    """The vocabulary or a map file is not valid."""


@dataclass(frozen=True, slots=True)
class CanonicalName:
    """A name of the vocabulary, taken apart."""

    text: str
    """The name as it is written."""
    family: str
    piece: int
    """1 for the first drum or cymbal of its family, whether or not the name writes it."""
    path: tuple[str, ...]
    """The articulation, then its variants."""

    @property
    def articulation(self) -> str:
        return self.path[0]

    @property
    def variants(self) -> tuple[str, ...]:
        return self.path[1:]

    def __str__(self) -> str:
        return self.text


class Family(BaseModel):
    """A kind of drum or cymbal, and the articulations it allows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pieces: PieceRule
    """`numbered`: every name has a piece number (`tom.1.hit`). `second`: only a second drum has
    one (`snare.center`, `snare.2.center`). `single`: a kit has one at most (`clap.hit`)."""
    default: str
    """The articulation a hit falls back to when nothing closer is in the kit."""
    articulations: tuple[str, ...] = Field(min_length=1)
    """Every articulation and variant allowed, as the part of the name after the family and the
    piece. A variant's parent is listed too: `open.quarter.tip` needs `open.quarter`."""
    piece_substitution: PieceSubstitution = "nearest"
    """How a conversion chooses a piece. `nearest` keeps the piece, or takes the nearest one when
    the target lacks it. `register` re-spreads the pieces by register when the two kits have
    different numbers of them, as toms are."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        listed: set[str] = set()
        for path in self.articulations:
            if not all(WORD.fullmatch(part) for part in path.split(".")):
                raise ValueError(f"{path!r} is not a lower-case articulation and variants")
            if path in listed:
                raise ValueError(f"{path} is listed twice")
            listed.add(path)
        for path in self.articulations:
            parent = path.rpartition(".")[0]
            if parent and parent not in listed:
                raise ValueError(f"{path} is listed without its parent {parent}")
        if self.default not in listed or "." in self.default:
            raise ValueError(f"the default {self.default} is not a listed articulation")
        return self


class Vocabulary(BaseModel):
    """Every family and articulation a map may name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = Field(alias="schema")
    ask_if_missing: tuple[str, ...] = ()
    """Articulations with no fallback to the family default: a conversion asks instead."""
    suggestions: dict[str, tuple[str, ...]] = Field(default_factory=dict[str, tuple[str, ...]])
    """Per family, the substitutes from other families a conversion may offer, never apply, when
    the target kit lacks the family. Each is a family, or a family and articulation."""
    families: dict[str, Family] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        for family in self.families:
            if not WORD.fullmatch(family):
                raise ValueError(f"family {family!r} is not a lower-case word")
        articulations = {
            path.split(".")[0] for family in self.families.values() for path in family.articulations
        }
        for articulation in self.ask_if_missing:
            if articulation not in articulations:
                raise ValueError(f"ask_if_missing names {articulation}, which no family has")
        for family, substitutes in self.suggestions.items():
            if family not in self.families:
                raise ValueError(f"suggestions name the family {family}, which doesn't exist")
            for substitute in substitutes:
                other, _, path = substitute.partition(".")
                if other == family or other not in self.families:
                    raise ValueError(f"{substitute} is not another family to suggest for {family}")
                if path and path not in self.families[other].articulations:
                    raise ValueError(f"{substitute} is not an articulation of {other}")
        return self

    def parse(self, text: str) -> CanonicalName:
        """The name taken apart. Raises `ValueError` when it is not a name of the vocabulary."""
        parts = text.split(".")
        family = self.families.get(parts[0])
        if family is None:
            raise ValueError(f"{text}: {parts[0]!r} is not a family of the vocabulary")
        rest = parts[1:]
        written = rest[0] if rest and PIECE.fullmatch(rest[0]) else None
        if written is not None and (written != str(int(written)) or int(written) < 1):
            raise ValueError(f"{text}: the piece {written!r} is not a number from 1")
        if family.pieces == "numbered" and written is None:
            raise ValueError(f"{text}: a {parts[0]} name has a piece number, as in {parts[0]}.1")
        if family.pieces == "single" and written is not None:
            raise ValueError(f"{text}: a {parts[0]} name has no piece number")
        if family.pieces == "second" and written == "1":
            raise ValueError(f"{text}: the first {parts[0]} has no piece number")
        path = rest[1:] if written is not None else rest
        if ".".join(path) not in family.articulations:
            raise ValueError(f"{text}: {'.'.join(path)!r} is not an articulation of {parts[0]}")
        piece = int(written) if written is not None else 1
        return CanonicalName(text=text, family=parts[0], piece=piece, path=tuple(path))

    def name(self, family: str, piece: int, path: tuple[str, ...]) -> CanonicalName:
        """The name of `path` on the given piece of `family`, written as the family writes it."""
        if self.families[family].pieces == "numbered" or piece > 1:
            return self.parse(".".join((family, str(piece), *path)))
        return self.parse(".".join((family, *path)))

    def default(self, family: str, piece: int) -> CanonicalName:
        """The default articulation of a piece, such as `snare.center` or `crash.2.hit`."""
        return self.name(family, piece, (self.families[family].default,))


def load_vocabulary(path: Path) -> Vocabulary:
    """Read and validate a vocabulary file. Raises `MapError` when it is not valid."""
    try:
        with path.open("rb") as file:
            return Vocabulary.model_validate(tomllib.load(file))
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise MapError(f"{path}: {error}") from error
