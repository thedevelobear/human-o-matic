"""The folders of performed MIDI in `private/midi/`, and the built-in kit that reads each one.

`private/` is never committed (ADR 0007), so what says which folder is read through which
library and kit lives there too, in `private/data/midi-folders.toml`, and no tracked file names a
folder. Its keys are paths under `private/midi/`, a folder or a folder inside one, and a file
follows the longest key its path starts with:

    schema = 1

    [folders.a-folder]
    map = "library/kit"            # or "library", for a library with one kit

    [folders."a-folder/a-subfolder"]
    exclude = "why it is left out"

A folder is found by listing `private/midi/`, and links are followed, since each folder there is
a link to where its files are installed. Only the tools in `tools/` read this module.
"""

import os
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import find_kit

PRIVATE = Path(__file__).resolve().parents[1] / "private"
MIDI = PRIVATE / "midi"
"""One folder, or a link to one, per collection of performed MIDI."""
ASSIGNMENTS = PRIVATE / "data" / "midi-folders.toml"
"""Which built-in kit reads each folder in `MIDI`, and which folders are left out."""
SUFFIXES = (".mid", ".midi")


class AssignmentError(ValueError):
    """The assignments file can't be read, or names a kit that isn't built in."""


class Entry(BaseModel):
    """One folder's entry: the kit that reads it, or why it is left out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    map: str | None = None
    """A built-in kit, as `library/kit` or `library` alone when it has one kit (ADR 0023)."""
    exclude: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.map is None) == (self.exclude is None):
            raise ValueError("give either `map` or `exclude`")
        return self


class AssignmentFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = Field(alias="schema")
    folders: dict[str, Entry]


@dataclass(frozen=True, slots=True)
class Assignment:
    """What applies to a file: the key it falls under, and that key's kit or reason."""

    key: str
    kit: DrumKit | None
    """None when the key's folder is left out."""
    exclude: str | None


class Assignments:
    """The entries of an assignments file, with each `map` checked against the built-in kits."""

    __slots__ = ("_entries",)

    def __init__(self, entries: Mapping[str, Entry]) -> None:
        """Raises `AssignmentError` for a key that isn't a relative path, or a map that isn't a
        built-in kit."""
        self._entries: dict[PurePosixPath, Assignment] = {}
        for key, entry in entries.items():
            path = PurePosixPath(key)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise AssignmentError(f"{key!r} is not a path under the folder of folders")
            kit = None
            if entry.map is not None:
                try:
                    kit = find_kit(entry.map)
                except KeyError as error:
                    raise AssignmentError(f"{key}: {error.args[0]}") from error
            self._entries[path] = Assignment(key=str(path), kit=kit, exclude=entry.exclude)

    @classmethod
    def read(cls, path: Path = ASSIGNMENTS) -> Self:
        """The assignments in a file, or none when it doesn't exist."""
        if not path.is_file():
            return cls({})
        try:
            with path.open("rb") as file:
                parsed = AssignmentFile.model_validate(tomllib.load(file))
        except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
            raise AssignmentError(f"{path}: {error}") from error
        return cls(parsed.folders)

    def __len__(self) -> int:
        return len(self._entries)

    def find(self, relative: PurePosixPath | str) -> Assignment | None:
        """What applies to a path under the folder of folders: the longest key it starts with,
        or None when no key covers it."""
        path = PurePosixPath(relative)
        for ancestor in (path, *path.parents):
            if ancestor in self._entries:
                return self._entries[ancestor]
        return None


def folders(root: Path = MIDI) -> list[Path]:
    """The folders directly in `root`, links to folders included, in name order."""
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def midi_files(folder: Path) -> Iterator[Path]:
    """Every MIDI file under `folder`, in name order, through any links on the way. A folder
    reached twice, through a link back up, is listed once."""
    seen: set[str] = set()
    for directory, subfolders, files in os.walk(folder, followlinks=True):
        real = os.path.realpath(directory)
        if real in seen:
            subfolders.clear()
            continue
        seen.add(real)
        subfolders.sort()
        for name in sorted(files):
            if name.lower().endswith(SUFFIXES):
                yield Path(directory) / name
