"""The error for an answer that doesn't fit the song.

An answer to a decision request is checked against the song it answers. One that names a drum
note, a beat or a family the song doesn't have is an error, never ignored, so a typo or an
answer meant for another song can't pass unnoticed. So is one the kit or the beat can't take.
"""

from typing import Literal

type AnswerArgument = Literal["unmapped", "grids", "hit_types"]


class AnswerError(ValueError):
    """An answer that names something the song doesn't have, or that doesn't fit it.

    The message says why in plain language, counting bars and beats from 1.
    """

    def __init__(
        self, argument: AnswerArgument, key: int | str | tuple[int, int], message: str
    ) -> None:
        super().__init__(message)
        self.argument: AnswerArgument = argument
        """The argument that holds the answer."""
        self.key = key
        """The answer's key in it: a pitch, a beat as `(bar, beat)` from 0, or a family."""
