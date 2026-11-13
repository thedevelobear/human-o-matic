"""`generic` mode: dynamics and timing without roles, which proves the instrument seam (ADR 0045).

Every note is `other`, on no limb of its own: it takes the style's `other` velocity row, no limb
offset, and `feel` moves every note. There are no fills, so `fill_intensity` changes nothing, and
no backbeats, riders or double kick. Soft and accent types still apply, as they do in any part.
It knows no drums, so a creative section adds nothing.
"""

import numpy as np

from human_o_matic.controls import Controls
from human_o_matic.normalize.score import Score
from human_o_matic.render.compiler import Params, compile_section
from human_o_matic.render.creative import Proposal, SectionView
from human_o_matic.render.parts import Part
from human_o_matic.render.style import Style

_PART = Part(role="other", limb="other")


class Generic:
    """Every note `other`, with no limb offset."""

    def parts(self, score: Score) -> tuple[Part, ...]:
        return tuple(_PART for _ in score.notes)

    def compile(self, controls: Controls, style: Style, bpm: float) -> Params:
        return compile_section(controls, style, bpm, roles=False)

    def additions(self, view: SectionView, rng: np.random.Generator) -> Proposal:
        return Proposal()


GENERIC = Generic()
