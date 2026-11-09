"""Loading the vocabulary and the built-in maps, each validated as it loads.

The built-in maps are the files in `data/maps/`, and this version loads no map from the user.
`load_library` and `load_maps` take any path so the tests can build maps of their own.
"""

import tomllib
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from pydantic import ValidationError

from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.schema import Library
from human_o_matic.maps.vocabulary import MapError, Vocabulary, load_vocabulary
from human_o_matic.resources import data_dir


class MapSet:
    """Libraries loaded together, and their kits by library and kit id."""

    __slots__ = ("_kits", "libraries", "vocabulary")

    def __init__(self, vocabulary: Vocabulary, kits: tuple[DrumKit, ...]) -> None:
        """Raises `MapError` when two libraries share an id."""
        self.vocabulary = vocabulary
        self._kits: dict[str, dict[str, DrumKit]] = {}
        libraries: dict[str, Library] = {}
        for kit in kits:
            if libraries.setdefault(kit.library.id, kit.library) is not kit.library:
                raise MapError(f"two map files have the library id {kit.library.id}")
            self._kits.setdefault(kit.library.id, {})[kit.spec.id] = kit
        self.libraries = tuple(libraries.values())

    def __iter__(self) -> Iterator[DrumKit]:
        for library_kits in self._kits.values():
            yield from library_kits.values()

    def kit(self, library: str, kit: str | None = None) -> DrumKit:
        """A library's kit, or its only kit when `kit` is None. Raises `KeyError` naming what
        exists when there is no such kit."""
        library_kits = self._kits.get(library)
        if library_kits is None:
            raise KeyError(f"no library {library!r}; there are {', '.join(self._kits)}")
        if kit is None:
            if len(library_kits) == 1:
                return next(iter(library_kits.values()))
            raise KeyError(f"{library} has the kits {', '.join(library_kits)}; name one")
        found = library_kits.get(kit)
        if found is None:
            raise KeyError(f"{library} has no kit {kit!r}; it has {', '.join(library_kits)}")
        return found


def load_library(path: Path, vocabulary: Vocabulary) -> tuple[DrumKit, ...]:
    """Read and validate a map file, giving its kits. Raises `MapError` when it is not valid."""
    try:
        with path.open("rb") as file:
            library = Library.model_validate(tomllib.load(file))
        return tuple(DrumKit(library, kit, vocabulary) for kit in library.kits)
    except (OSError, tomllib.TOMLDecodeError, ValidationError, MapError) as error:
        raise MapError(f"{path}: {error}") from error


def load_maps(directory: Path, vocabulary: Vocabulary) -> MapSet:
    """Every map file (`*.toml`) in the directory, in name order."""
    files = sorted(directory.glob("*.toml"))
    kits = tuple(kit for path in files for kit in load_library(path, vocabulary))
    return MapSet(vocabulary, kits)


@cache
def built_in_vocabulary() -> Vocabulary:
    """The vocabulary in `data/vocabulary.toml`."""
    return load_vocabulary(data_dir() / "vocabulary.toml")


@cache
def built_in_maps() -> MapSet:
    """The maps in `data/maps/`, checked against the built-in vocabulary."""
    directory = data_dir() / "maps"
    if not directory.is_dir():
        raise MapError(f"the built-in maps are not at {directory}")
    return load_maps(directory, built_in_vocabulary())


def find_kit(name: str) -> DrumKit:
    """The built-in kit named `library/kit`, or `library` alone when it has one kit (ADR 0023).
    Raises `KeyError` naming what exists."""
    library, slash, kit = name.partition("/")
    return built_in_maps().kit(library, kit if slash else None)
