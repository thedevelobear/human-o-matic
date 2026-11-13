"""The instrument seam: what the engine asks of one kind of part (ADR 0045).

An instrument gives each note of a score its part, compiles a section's controls with a style,
and says what a creative section adds (ADR 0091): the three things `render()` calls.
Normalizing, hit typing and the facts the agent reads are the drums' own for now, and join the
seam when a second real instrument needs them.
"""

from typing import Protocol

import numpy as np

from human_o_matic.controls import Controls
from human_o_matic.normalize.score import Score
from human_o_matic.render.compiler import Params
from human_o_matic.render.creative import Proposal, SectionView
from human_o_matic.render.parts import Part
from human_o_matic.render.style import Style


class Instrument(Protocol):
    def parts(self, score: Score) -> tuple[Part, ...]:
        """Each note's part, in the order of `Score.notes`."""
        ...

    def compile(self, controls: Controls, style: Style, bpm: float) -> Params:
        """A section's parameters at its tempo, `bpm`."""
        ...

    def additions(self, view: SectionView, rng: np.random.Generator) -> Proposal:
        """What a creative section adds, drawing any choice from `rng`, its own stream."""
        ...
