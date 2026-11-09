"""What each note plays in the performance: its role, its limb, and what its role draws on.

An instrument gives every note of the score a `Part` (`instruments/drums.py`, or one role for all
in `generic`). The role picks the velocity row of the style, and the limb the timing offset. The
other fields are set only for the roles that use them.
"""

from dataclasses import dataclass
from typing import Literal

from human_o_matic.normalize.score import ScoreNote

type Role = Literal[
    "kick", "double_kick", "backbeat", "snare", "rider", "accent_cymbal", "fill", "other"
]
"""`snare` is a snare that is no backbeat and in no fill. `other` is anything without a role of
its own: toms outside fills, the hat pedal, percussion and sample layers."""
type Limb = Literal["snare", "rider", "other"]
"""Which timing offset a note takes: the snare's, the riders', or none."""
type RiderShape = Literal["center", "alternate", "weak"]
"""A rider hit's place in its run: `center` alone, `alternate` on a quarter note of a run, where
hits alternate strong and weak, or `weak` between quarter notes."""

ROLES: tuple[Role, ...] = (
    "kick",
    "double_kick",
    "backbeat",
    "snare",
    "rider",
    "accent_cymbal",
    "fill",
    "other",
)
LIMBS: tuple[Limb, ...] = ("snare", "rider", "other")
METRIC_LEVELS = 4
"""A fill note is on a quarter note (0), an 8th (1), a 16th (2) or none of them (3)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Part:
    """What one note plays."""

    role: Role
    limb: Limb
    rider: RiderShape = "center"
    strong: bool = False
    """For an `alternate` rider hit, whether it lands where the run's strong hits are, by the
    vote of where the snare plays."""
    foot: int = 0
    """For double kick, +1 for the right foot and -1 for the left."""
    metric: int = 0
    """For a fill note, its metric level, from 0 for a quarter note."""
    hand: int = 0
    """For a fill note, +1 and -1 by turns."""
    crescendo: float = 0.0
    """For a fill note, how far it is into the fill's crescendo, from 0 to 1."""


def play_key(note: ScoreNote) -> tuple[int, str, int, str, int, int]:
    """The order the engine takes notes in: by tick, then by drum, name, channel and pitch. The
    score orders notes on one grid point by when they were played, and this never depends on
    it, so input timing can't change a render through the order of its draws."""
    source = note.source
    return note.tick, note.family, note.piece, note.articulation, source.channel, source.pitch
