"""A kit of a loaded map: its articulations checked against the vocabulary, read and written.

Reading takes a note, its velocity and channel to the articulations it can be. Writing takes an
articulation back to a note, a channel and a velocity range. A kit is checked when it is built,
so a built-in map that breaks a rule never loads:
- every name is in the vocabulary and unique in the kit;
- a variant's parent is in the kit (`hat.open.quarter.tip` needs `hat.open.quarter`), and every
  piece has its default (a kit with `crash.2.choke` has `crash.2.hit`);
- a family's pieces are numbered from 1 with no gaps;
- no two bindings overlap: for any channel, note and velocity, at most one matches, unless they
  are told apart by `select` ranges of one controller that don't overlap either.
"""

from dataclasses import dataclass
from itertools import combinations

from human_o_matic.maps.schema import Articulation, Binding, Cc, Kit, Library
from human_o_matic.maps.vocabulary import CanonicalName, MapError, Vocabulary


@dataclass(frozen=True, slots=True)
class Match:
    """An articulation a note can be, and the binding the note matched."""

    articulation: Articulation
    binding: Binding


@dataclass(frozen=True, slots=True)
class Output:
    """How an articulation is written."""

    pitch: int
    channel: int | None
    """0 to 15, or None when the note keeps its own channel."""
    velocity: tuple[int, int]
    """The velocities the written note may have."""
    cc: Cc | None
    """A controller the articulation depends on, which writing would need to set (ADR 0053)."""


class DrumKit:
    """One kit of a library, checked against the vocabulary and indexed for reading."""

    __slots__ = ("_by_name", "_by_note", "_names", "_pieces", "library", "spec", "vocabulary")

    def __init__(self, library: Library, spec: Kit, vocabulary: Vocabulary) -> None:
        """Raises `MapError` when the kit breaks one of the module's rules."""
        self.library = library
        self.spec = spec
        self.vocabulary = vocabulary
        self._by_name: dict[str, Articulation] = {}
        self._names: dict[str, CanonicalName] = {}
        self._by_note: dict[int, list[Match]] = {}
        for articulation in spec.articulations:
            if articulation.name in self._by_name:
                raise self._error(f"{articulation.name} is listed twice")
            try:
                self._names[articulation.name] = vocabulary.parse(articulation.name)
            except ValueError as error:
                raise self._error(str(error)) from error
            self._by_name[articulation.name] = articulation
            for binding in articulation.bindings:
                self._by_note.setdefault(binding.note, []).append(Match(articulation, binding))
        self._pieces = self._check_pieces()
        self._check_closure()
        self._check_overlaps()

    @property
    def ref(self) -> str:
        """`library/kit`, such as `gm/default`."""
        return f"{self.library.id}/{self.spec.id}"

    @property
    def label(self) -> str:
        """The library and kit in plain language."""
        return f"{self.library.name} ({self.spec.name})"

    @property
    def articulations(self) -> tuple[Articulation, ...]:
        return self.spec.articulations

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def articulation(self, name: str) -> Articulation:
        """The articulation of that name. Raises `KeyError` when the kit lacks it."""
        return self._by_name[name]

    def canonical(self, name: str) -> CanonicalName:
        """The name of one of the kit's articulations, taken apart."""
        return self._names[name]

    def pieces(self, family: str) -> int:
        """How many pieces of the family the kit has: 0 when it has none."""
        return self._pieces.get(family, 0)

    def read(self, pitch: int, velocity: int, channel: int) -> tuple[Match, ...]:
        """Every articulation a note can be, with `channel` counted from 0.

        None means the kit doesn't map the note. One match without a controller condition is
        the articulation. Anything else depends on a controller value, which isn't followed:
        several matches are told apart by `select` ranges, and one with a condition needs it.
        """
        return tuple(
            match
            for match in self._by_note.get(pitch, ())
            if (match.binding.channel is None or match.binding.channel == channel + 1)
            and match.binding.velocity[0] <= velocity <= match.binding.velocity[1]
        )

    def resolve(self, pitch: int, velocity: int, channel: int) -> Articulation | None:
        """The one articulation a note is, or None when it is unmapped or depends on a
        controller value."""
        matches = self.read(pitch, velocity, channel)
        if len(matches) == 1 and matches[0].binding.cc is None:
            return matches[0].articulation
        return None

    def write(self, name: str) -> Output:
        """How the articulation is written: its first binding's note, that binding's channel or
        else the kit's, and that binding's velocity range."""
        binding = self._by_name[name].bindings[0]
        channel = binding.channel if binding.channel is not None else self.spec.channel
        return Output(
            pitch=binding.note,
            channel=channel - 1 if channel is not None else None,
            velocity=binding.velocity,
            cc=binding.cc,
        )

    def _error(self, message: str) -> MapError:
        return MapError(f"{self.library.id}/{self.spec.id}: {message}")

    def _check_pieces(self) -> dict[str, int]:
        pieces: dict[str, set[int]] = {}
        for name in self._names.values():
            pieces.setdefault(name.family, set()).add(name.piece)
        for family, numbers in pieces.items():
            if numbers != set(range(1, len(numbers) + 1)):
                listed = ", ".join(str(number) for number in sorted(numbers))
                raise self._error(f"the {family} pieces {listed} are not numbered from 1")
        return {family: len(numbers) for family, numbers in pieces.items()}

    def _check_closure(self) -> None:
        for name in self._names.values():
            if name.variants:
                parent = self.vocabulary.name(name.family, name.piece, name.path[:-1])
                if parent.text not in self._by_name:
                    raise self._error(f"{name} needs {parent}")
            default = self.vocabulary.default(name.family, name.piece)
            if default.text not in self._by_name:
                raise self._error(f"{name} needs its piece's default, {default}")

    def _check_overlaps(self) -> None:
        for matches in self._by_note.values():
            for first, second in combinations(matches, 2):
                if _overlap(first.binding, second.binding):
                    raise self._error(
                        f"{first.articulation.name} and {second.articulation.name} overlap on "
                        f"note {first.binding.note}: {_describe(first.binding)} and "
                        f"{_describe(second.binding)}"
                    )


def _overlap(first: Binding, second: Binding) -> bool:
    """Whether a note on the same pitch could match both bindings."""
    if first.channel is not None and second.channel is not None and first.channel != second.channel:
        return False
    if not _intersect(first.velocity, second.velocity):
        return False
    a, b = first.cc, second.cc
    if (
        a is not None
        and b is not None
        and a.mode == b.mode == "select"
        and a.controller == b.controller
        and a.values is not None
        and b.values is not None
    ):
        return _intersect(a.values, b.values)
    return True


def _intersect(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return first[0] <= second[1] and second[0] <= first[1]


def _describe(binding: Binding) -> str:
    channel = f"channel {binding.channel}" if binding.channel is not None else "any channel"
    text = f"{channel}, velocity {binding.velocity[0]} to {binding.velocity[1]}"
    if binding.cc is not None:
        controller = f"CC{binding.cc.controller}" if binding.cc.controller is not None else "CC"
        values = binding.cc.values
        text += f", {controller} {binding.cc.mode}"
        text += f" {values[0]} to {values[1]}" if values is not None else ""
    return text
