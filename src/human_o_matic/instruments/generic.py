"""`generic` mode: dynamics and timing without roles, which proves the instrument seam (ADR 0045).

Every note is `other`, on no limb of its own: it takes the style's `other` velocity row, no limb
offset, and `feel` moves every note. There are no fills, so `fill_intensity` changes nothing, and
no backbeats, riders or double kick. Soft and accent types still apply, as they do in any part.
"""

from human_o_matic.controls import Controls
from human_o_matic.normalize.score import Score
from human_o_matic.render.compiler import Params, compile_section
from human_o_matic.render.parts import Part
from human_o_matic.render.style import Style

_PART = Part(role="other", limb="other")


class Generic:
    @property
    def name(self) -> str:
        return "generic"

    @property
    def controls(self) -> frozenset[str]:
        return frozenset(Controls.model_fields) - {"fill_intensity"}

    def parts(self, score: Score) -> tuple[Part, ...]:
        return tuple(_PART for _ in score.notes)

    def compile(self, controls: Controls, style: Style) -> Params:
        return compile_section(controls, style, roles=False)


GENERIC = Generic()
