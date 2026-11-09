"""Writing the rendered notes back into the song (ADR 0048).

Only the drum track's notes change. Every other track, and every event of the drum track, its
controllers, meta events and the file's own tempo, stays as it was read. Each rendered note keeps
its source note's track and release velocity. A note played as it came in, or held to its
controller events (ADR 0053), keeps its order among the track's messages too. Any other takes
its place in play order after them, so at a shared tick the writer puts events first, and the
order never depends on how the notes were played (`midi/io.py`).

The drum track ends with its last note or event, as rendered. An end the file sets after every
one of its notes and events is kept, since then it isn't the last note's end but the track's.
"""

from collections.abc import Sequence
from dataclasses import replace

from human_o_matic.midi.io import MidiSong, Note


def with_drums(song: MidiSong, track: int, drums: Sequence[Note]) -> MidiSong:
    """The song with the drum track's notes replaced, and every other note and event as it
    was."""
    notes = [note for note in song.notes if note.track != track]
    notes.extend(drums)
    notes.sort(key=lambda note: (note.start, note.track, note.order))
    events = [event.tick for event in song.events if event.track == track]
    played = [note.end for note in song.notes if note.track == track]
    end = max([*events, *(note.end for note in drums)], default=0)
    if song.track_ends[track] > max([*events, *played], default=0):
        end = max(end, song.track_ends[track])
    ends = list(song.track_ends)
    ends[track] = end
    return replace(song, notes=tuple(notes), track_ends=tuple(ends))
