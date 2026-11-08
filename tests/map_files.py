"""Map files built in code for the tests, written as TOML to a temporary directory."""

import json
from pathlib import Path

from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import built_in_vocabulary, load_library
from human_o_matic.maps.vocabulary import Vocabulary

type Table = dict[str, object]


def articulation(
    name: str, *notes: int, confidence: str = "high", source: str = "mapping", **fields: object
) -> Table:
    """An articulation on `notes`, or on `bindings=[...]` when no notes are given."""
    table: Table = {"name": name}
    if notes:
        table["notes"] = list(notes)
    table |= fields
    return table | {"source": source, "confidence": confidence}


def kit(*articulations: Table, id: str = "kit", **fields: object) -> Table:
    return {"id": id, "name": f"Kit {id}"} | fields | {"articulations": list(articulations)}


def library(*kits: Table, id: str = "test-drums", **fields: object) -> Table:
    return {"schema": 1, "id": id, "name": f"Library {id}"} | fields | {"kits": list(kits)}


def toml(table: Table) -> str:
    """The TOML of a library table: its keys, then `[[kits]]` and each kit's
    `[[kits.articulations]]`."""
    lines = [f"{key} = {_value(value)}" for key, value in table.items() if key != "kits"]
    for kit_table in _list(table.get("kits", [])):
        fields = _table(kit_table)
        lines.append("[[kits]]")
        lines.extend(f"{k} = {_value(v)}" for k, v in fields.items() if k != "articulations")
        for entry in _list(fields.get("articulations", [])):
            lines.append("[[kits.articulations]]")
            lines.extend(f"{key} = {_value(value)}" for key, value in _table(entry).items())
    return "\n".join(lines) + "\n"


def write_library(directory: Path, table: Table, name: str | None = None) -> Path:
    path = directory / f"{name or table['id']}.toml"
    path.write_text(toml(table))
    return path


def load_kit(
    directory: Path, *articulations: Table, vocabulary: Vocabulary | None = None, **fields: object
) -> DrumKit:
    """A one-kit library with these articulations, written to `directory` and loaded."""
    kit_id = str(fields.pop("id", "kit"))
    path = write_library(directory, library(kit(*articulations, id=kit_id, **fields), id=kit_id))
    (loaded,) = load_library(path, vocabulary or built_in_vocabulary())
    return loaded


def _value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        # A JSON string is a TOML basic string: the same quotes and escapes.
        return json.dumps(value)
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_value(item) for item in _list(value)) + "]"
    if isinstance(value, dict):
        items = _table(value).items()
        return "{ " + ", ".join(f"{key} = {_value(item)}" for key, item in items) + " }"
    raise TypeError(f"{value!r} has no TOML form here")


def _table(value: object) -> Table:
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def _list(value: object) -> list[object]:
    assert isinstance(value, list | tuple)
    return list(value)
