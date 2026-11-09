"""Drum songs built in code for the engine's tests: notes at ticks, read through the GM map."""

from collections.abc import Iterable, Sequence

from human_o_matic.maps.kit import DrumKit
from human_o_matic.maps.loader import find_kit
from human_o_matic.midi.io import MidiSong, parse_midi
from human_o_matic.normalize.hit_types import HitTypeBounds
from human_o_matic.normalize.pipeline import normalize
from human_o_matic.normalize.score import Normalized
from midi_files import MidoMessage, build, end, name, off, on, signature, tempo, track

GM = find_kit("gm")
PPQ = 960
SIXTEENTH = PPQ // 4
BAR = 4 * PPQ
KICK, SNARE, SIDESTICK, HAT, PEDAL, OPEN_HAT = 36, 38, 37, 42, 44, 46
RIDE, BELL, CRASH, CHINA, COWBELL = 51, 53, 49, 52, 56
TOM_1, TOM_2, TOM_3 = 50, 48, 47
SOFT, NORMAL, ACCENT = 30, 90, 120
"""Input velocities that `TYPED` reads as soft, normal and accent."""
TYPED = HitTypeBounds(soft_below=50, accent_from=110)
FAMILIES = ("kick", "snare", "hat", "ride", "crash", "china", "tom", "cowbell")

type Hit = tuple[int, int] | tuple[int, int, int]
"""`(tick, pitch)` at `NORMAL`, or `(tick, pitch, velocity)`."""


def song(
    hits: Iterable[Hit],
    *,
    bpm: float = 120,
    tempos: Sequence[tuple[int, float]] = (),
    signatures: Sequence[tuple[int, int, int]] = (),
    length: int = 10,
    events: Sequence[tuple[int, MidoMessage]] = (),
) -> MidiSong:
    """A one-track song at 960 PPQ, read back. `tempos` are `(tick, bpm)` changes after the
    first, `signatures` are `(tick, numerator, denominator)`, each note lasts `length` ticks, and
    `events` are other messages at their ticks."""
    items: list[tuple[int, int, MidoMessage]] = [(0, 0, name("Drums")), (0, 0, tempo(bpm))]
    items.extend((tick, 0, tempo(value)) for tick, value in tempos)
    items.extend((tick, 0, signature(top, bottom)) for tick, top, bottom in signatures)
    items.extend((tick, 1, message) for tick, message in events)
    for hit in hits:
        tick, pitch = hit[0], hit[1]
        velocity = hit[2] if len(hit) == 3 else NORMAL
        items.extend([(tick, 3, on(pitch, velocity)), (tick + length, 2, off(pitch))])
    items.sort(key=lambda item: (item[0], item[1]))
    messages = [(tick, message) for tick, _, message in items]
    return parse_midi(build(track(*messages, (messages[-1][0], end())), ppq=PPQ))


def normalized(midi: MidiSong, kit: DrumKit = GM) -> Normalized:
    """The song normalized with every family it has typed by `TYPED`, so no request is open."""
    families = {
        match.articulation.name.split(".")[0]
        for note in midi.notes
        for match in kit.read(note.pitch, note.velocity, note.channel)
    }
    result = normalize(midi, kit, hit_types=dict.fromkeys(families, TYPED))
    assert result.complete
    return result


def rock(bars: int, *, start: int = 0) -> list[Hit]:
    """Kick on 1 and 3, snare on 2 and 4, 8th hats, from bar `start`."""
    hits: list[Hit] = []
    for bar in range(start, start + bars):
        at = bar * BAR
        hits.extend([(at, KICK), (at + 2 * PPQ, KICK), (at + PPQ, SNARE), (at + 3 * PPQ, SNARE)])
        hits.extend((at + eighth * PPQ // 2, HAT) for eighth in range(8))
    return hits
