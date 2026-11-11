"""The controls: what the user's answers become, for the whole song and for each section.

A `ControlVector` holds the controls one answer sets, each in its range or unset. Unset means
the layer below decides: a section's controls over the song's, and the song's over the style's
defaults, which `Controls` holds with every control set. A `SectionPlan` is a run of whole bars
with its controls, and a `SessionPlan` is what a render needs besides the song and its kits: the
style, the seed, the song's controls and the sections, which cover the song's bars from 0 in
order.

Every model is frozen, takes no unknown field and is strict, so a string or a boolean is never
read as a number. Their JSON is `model_dump(mode="json", exclude_none=True)`, which leaves unset
controls out, and `model_validate_json` reads it back to an equal model.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_SEED = 2**53 - 1
"""The largest seed: every integer up to it is exact in JSON, as a double holds it."""

type Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
type Feel = Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]
type Arc = Literal["steady", "build", "drop"]
"""The energy's shape across a section: level, rising or falling."""
type StyleName = Literal["tight", "medium", "loose"]
"""The built-in styles, from the tightest (ADR 0044)."""
type Seed = Annotated[int, Field(ge=0, le=MAX_SEED)]

_STRICT = ConfigDict(frozen=True, extra="forbid", strict=True)


class Controls(BaseModel):
    """Every control set, as a style's defaults are and as a section is rendered."""

    model_config = _STRICT

    energy: Unit
    """Velocity centers and floors, and accent strength."""
    groove: Unit
    """Accent contrast, soft note presence, and the riders' strong and weak hits."""
    dynamic_range: Unit
    """Spread within a drum, and strong against weak hits."""
    tightness: Unit
    """Timing spread: 1 is the tightest."""
    feel: Feel
    """The mean offset of snare and riders: -1 pushed to +1 laid back."""
    arc: Arc
    fill_intensity: Unit
    """Fill velocity and crescendo."""
    ghost_level: Unit
    """The velocity of notes typed soft."""
    skip: bool
    """Leave the section as it came in."""


class ControlVector(BaseModel):
    """Controls of one layer, any of them unset."""

    model_config = _STRICT

    energy: Unit | None = None
    groove: Unit | None = None
    dynamic_range: Unit | None = None
    tightness: Unit | None = None
    feel: Feel | None = None
    arc: Arc | None = None
    fill_intensity: Unit | None = None
    ghost_level: Unit | None = None
    skip: bool | None = None

    def over(self, base: "ControlVector") -> "ControlVector":
        """These controls, with `base`'s wherever these are unset."""
        return base.model_copy(update=self.model_dump(exclude_none=True))

    def resolve(self, defaults: Controls) -> Controls:
        """These controls, with `defaults` wherever these are unset."""
        return defaults.model_copy(update=self.model_dump(exclude_none=True))


class SectionPlan(BaseModel):
    """A section to render: a run of whole bars and its controls."""

    model_config = _STRICT

    start: int = Field(ge=0)
    """Its first bar, counting from 0."""
    bars: int = Field(ge=1)
    group: str
    """Its repeat group."""
    controls: ControlVector = ControlVector()
    take: int = Field(default=0, ge=0)
    """Which draw: another take renders the section again with other random values."""
    note: str = ""
    """The user's words the controls were read from."""

    @property
    def end(self) -> int:
        """The bar after its last."""
        return self.start + self.bars


class SessionPlan(BaseModel):
    """What a render takes besides the song and its kits."""

    model_config = _STRICT

    style: StyleName = "tight"
    seed: Seed
    controls: ControlVector = ControlVector()
    """The song's controls, under each section's."""
    sections: tuple[SectionPlan, ...] = Field(min_length=1)
    """In order, from bar 0, each starting where the one before ends."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        expected = 0
        for section in self.sections:
            if section.start != expected:
                raise ValueError(
                    f"the section at bar {section.start} should start at bar {expected}, where "
                    "the one before it ends"
                )
            expected = section.end
        return self

    @property
    def bars(self) -> int:
        """How many bars the sections cover."""
        return self.sections[-1].end

    def controls_of(self, section: SectionPlan, defaults: Controls) -> Controls:
        """A section's controls over the song's, over `defaults`."""
        return section.controls.over(self.controls).resolve(defaults)
