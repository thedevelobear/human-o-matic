"""Decision requests: what the pipeline returns when the input leaves something unclear.

The pipeline never guesses at something only the user knows, such as a missing tempo or which
of several tracks holds the drums. A step that cannot go on raises `DecisionRequired`, carrying
a `DecisionRequest`. The MCP layer turns that into compact JSON with `model_dump(mode="json")`,
the agent asks the user, and the call is repeated with the answer passed as one of the
arguments in `answer_with`. A step that can go on but wants something confirmed returns its
requests alongside its result instead.

Indices in the data are those the code uses: tracks and channels count from 0. Messages and
labels are plain language for the user, so they show channels counting from 1, as instruments
and DAWs do.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

type DecisionKind = Literal["tempo", "drum_track", "unmapped_notes", "conversion"]
"""What is being asked. Later steps add their own kinds."""


class DecisionOption(BaseModel):
    """One possible answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: int | float | str
    """What to pass back as the answer."""
    label: str
    """The option in plain language."""
    details: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])


class DecisionRequest(BaseModel):
    """A question for the user, with what is needed to answer it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: DecisionKind
    message: str
    """The question in plain language, saying why it is asked."""
    answer_with: tuple[str, ...] = ()
    """The arguments that settle it, such as `bpm` or `track`."""
    options: tuple[DecisionOption, ...] = ()
    """The possible answers, when they can be listed."""
    details: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])


class DecisionRequired(Exception):  # noqa: N818 (it is not an error in the input, but a question)
    """Raised by a step that cannot go on without the user's answer."""

    def __init__(self, request: DecisionRequest) -> None:
        super().__init__(request.message)
        self.request = request
