"""The controller guard's windows: where a controller-bound note may move and keep its value
(ADR 0053).

A note whose articulation a controller value decides or shapes, such as a hat whose openness a
pedal controller sets, plays with the value in force at its note-on. So its note-on may move only
as far as the controller events on its channel in the drum track around its source note: from
the last one before it up to the first one after it, by tick and by order at a tick. Its
controllers are those its bindings name, or every controller when one names none, as when a map's
source doesn't say. A note moved onto either event's tick keeps its order among the track's
messages, so it stays on its own side of the event (`render/output.py`).
"""

from bisect import bisect_left, bisect_right

from human_o_matic.midi.io import MidiSong
from human_o_matic.normalize.score import Score
from human_o_matic.render.target import Placement

CONTROL_CHANGE = 0xB0
LATEST = 2**62
"""The latest tick a note with no controller event after it may take."""


def windows(
    song: MidiSong, score: Score, placement: Placement
) -> tuple[tuple[int, int] | None, ...]:
    """For each of the score's notes held to its controller events, the earliest and latest
    tick its note-on may take, and None for every other note."""
    events: dict[tuple[int, int | None], list[tuple[int, int]]] = {}
    """The `(tick, order)` of each controller's events on each channel, and of every
    controller's under None."""
    for event in song.events:
        if event.track != score.track or event.status & 0xF0 != CONTROL_CHANGE or not event.data:
            continue
        channel = event.status & 0x0F
        for controller in (event.data[0], None):
            events.setdefault((channel, controller), []).append((event.tick, event.order))
    for positions in events.values():
        positions.sort()
    found: list[tuple[int, int] | None] = []
    for note, placed in zip(score.notes, placement.notes, strict=True):
        if placed is None or placed.controllers is None:
            found.append(None)
            continue
        source = note.source
        numbers = (None,) if placed.controllers == "all" else tuple(placed.controllers)
        earliest, latest = 0, LATEST
        here = (source.start, source.order)
        for number in numbers:
            positions = events.get((source.channel, number), [])
            before = bisect_left(positions, here)
            after = bisect_right(positions, here)
            if before:
                earliest = max(earliest, positions[before - 1][0])
            if after < len(positions):
                latest = min(latest, positions[after][0])
        found.append((earliest, latest))
    return tuple(found)
