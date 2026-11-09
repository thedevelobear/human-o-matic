# Type stubs for the part of mido 1.3 that human-o-matic uses. mido ships no types, and pyright
# is strict on src/. Only src/human_o_matic/midi/io.py imports mido in the package, and it
# reads and writes raw message bytes, so the stub declares no per-type attributes such as
# `note` or `tempo`. Extend it only for what the code calls.

from collections.abc import Iterable
from os import PathLike
from typing import BinaryIO

class KeySignatureError(Exception): ...

# mido.messages.BaseMessage, which the top-level package does not export.
class _BaseMessage:
    type: str
    time: int
    is_meta: bool
    def bytes(self) -> list[int]: ...

class Message(_BaseMessage):
    def __init__(self, type: str, skip_checks: bool = ..., **args: object) -> None: ...
    @classmethod
    def from_bytes(cls, data: Iterable[int], time: int = ...) -> Message: ...

class MetaMessage(_BaseMessage):
    def __init__(self, type: str, skip_checks: bool = ..., **kwargs: object) -> None: ...

class UnknownMetaMessage(MetaMessage):
    type_byte: int
    data: tuple[int, ...]
    def __init__(
        self, type_byte: int, data: Iterable[int] | None = ..., time: int = ...
    ) -> None: ...

class MidiTrack(list[Message | MetaMessage]):
    @property
    def name(self) -> str: ...

class MidiFile:
    type: int
    ticks_per_beat: int
    tracks: list[MidiTrack]
    def __init__(
        self,
        filename: str | PathLike[str] | None = ...,
        file: BinaryIO | None = ...,
        type: int = ...,
        ticks_per_beat: int = ...,
        charset: str = ...,
        debug: bool = ...,
        clip: bool = ...,
        tracks: list[MidiTrack] | None = ...,
    ) -> None: ...
    def save(
        self, filename: str | PathLike[str] | None = ..., file: BinaryIO | None = ...
    ) -> None: ...
