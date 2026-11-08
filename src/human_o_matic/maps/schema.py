"""The map file format: a library, its kits, and each kit's articulations.

A map file is TOML in `data/maps/`, one library per file. These models check its structure, and
`kit.DrumKit` checks each kit against the vocabulary, both when the file loads, so a built-in
map is never ambiguous at run time.

An articulation is a list of bindings: a note, with an optional velocity range, channel and
controller condition. `notes`, with `velocity`, `channel` and `cc` beside it, is shorthand for
one binding per note. The first binding is the one written, and the others are also read.

Channels here are 1 to 16, as instruments and drum maps show them. A `Note`'s channel counts
from 0.
"""

from typing import Annotated, Literal, Self, cast

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

type Confidence = Literal["high", "medium", "low"]
"""`high`: named by the source, or confirmed by the owner. `medium`: named by the source, with
the canonical name an interpretation. `low`: inferred."""
type SourceKind = Literal["standard", "vendor-file", "manual", "owner-check"]
type MidiNumber = Annotated[int, Field(ge=0, le=127)]
type Channel = Annotated[int, Field(ge=1, le=16)]
type Id = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]

MAX_LABEL = 40
"""A label is the source's own name for a note, a few words, never a copy of the source."""


def _range(low: int, high: int) -> AfterValidator:
    def check(value: tuple[int, int]) -> tuple[int, int]:
        if not low <= value[0] <= value[1] <= high:
            raise ValueError(f"[{value[0]}, {value[1]}] is not a range within {low} to {high}")
        return value

    return AfterValidator(check)


type VelocityRange = Annotated[tuple[int, int], _range(1, 127)]
type ValueRange = Annotated[tuple[int, int], _range(0, 127)]


class Source(BaseModel):
    """Where a map's data comes from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SourceKind
    title: str
    path: str | None = None
    """Where a vendor file is read in place. It is never copied into the repository."""


class Cc(BaseModel):
    """A controller that selects or shapes an articulation. M1 stores and checks it, and
    resolves it in M3."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["select", "shape"]
    """`select`: the controller's value at the note-on picks this articulation, when it is within
    `values`. `shape`: the controller shapes it continuously, as a hi-hat pedal does."""
    controller: MidiNumber | None = None
    """The controller number. Only `shape` may leave it out, when the source doesn't say."""
    values: ValueRange | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.mode == "select" and (self.controller is None or self.values is None):
            raise ValueError("a select controller needs `controller` and `values`")
        if self.mode == "shape" and self.values is not None:
            raise ValueError("a shape controller has no `values`")
        return self


class Binding(BaseModel):
    """A note that plays an articulation, and when."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    note: MidiNumber
    velocity: VelocityRange = (1, 127)
    """On reading, the velocities this binding takes. On writing, output stays inside it."""
    channel: Channel | None = None
    """Binds reading and writing to one channel. Unset, reading takes any channel."""
    cc: Cc | None = None


class Articulation(BaseModel):
    """One articulation of a kit: its canonical name and the notes that play it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    """A name of the vocabulary, unique in its kit."""
    bindings: tuple[Binding, ...] = Field(min_length=1)
    source: str
    """The id of one of the library's sources."""
    ref: str | None = None
    """Where in the source."""
    label: str | None = Field(default=None, min_length=1, max_length=MAX_LABEL)
    """The source's own name for it, when the source has one."""
    confidence: Confidence

    @model_validator(mode="before")
    @classmethod
    def _expand_notes(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        fields = dict(cast(dict[str, object], data))
        if "notes" not in fields:
            return fields
        if "bindings" in fields:
            raise ValueError("give `notes` or `bindings`, not both")
        notes = fields.pop("notes")
        if not isinstance(notes, list):
            raise ValueError("`notes` is a list of note numbers")
        shared = {key: fields.pop(key) for key in ("velocity", "channel", "cc") if key in fields}
        fields["bindings"] = [{"note": note, **shared} for note in cast(list[object], notes)]
        return fields


class Kit(BaseModel):
    """One kit of a library."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Id
    name: str
    channel: Channel | None = None
    """The channel written when an articulation binds none. Unset, a note keeps its channel."""
    articulations: tuple[Articulation, ...] = Field(min_length=1)


class Library(BaseModel):
    """A map file: one library and its kits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = Field(alias="schema")
    id: Id
    """The built-in library id, which maps are chosen by."""
    name: str
    sources: dict[str, Source] = Field(min_length=1)
    kits: tuple[Kit, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        kit_ids = [kit.id for kit in self.kits]
        if len(set(kit_ids)) != len(kit_ids):
            raise ValueError(f"kit ids repeat: {', '.join(kit_ids)}")
        for kit in self.kits:
            for articulation in kit.articulations:
                if articulation.source not in self.sources:
                    raise ValueError(
                        f"{kit.id}: {articulation.name} names the source {articulation.source}, "
                        "which the library doesn't list"
                    )
        return self
