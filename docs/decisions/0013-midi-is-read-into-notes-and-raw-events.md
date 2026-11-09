# 0013. MIDI files are read into paired notes and raw events at absolute ticks

- **Status:** Accepted
- **Date:** 2026-11-08

- `midi/io.py` reads a format 0 or 1 file into a `MidiSong` of frozen dataclasses with absolute ticks. A `Note` has its track, channel, pitch, start and end ticks, velocity and release velocity. Every other message, including controllers, RPNs, pitch bend, aftertouch, program changes, sysex and meta events, is an `Event` that keeps its raw bytes. End of track is kept as a tick per track, and the writer adds the message.
- Note-ons and note-offs pair first in, first out, per channel and pitch. A note-off with no note to end stays an event, and a note that never ends ends with its track.
- Each note and event keeps its position in its source track, and the writer orders messages at one tick by it. A read followed by a write keeps every message at the same position and in the same order.
- A round trip drops only what MIDI gives no meaning: a note-on at velocity 0 is written as a note-off at velocity 64, running status is chosen anew, and an `F7` escape is written as sysex. Format 2 files and SMPTE time division are refused.

**Why:** Later steps work on notes, and everything else must come back out untouched, including messages the app doesn't interpret. Raw bytes keep them exactly without modelling each kind.

**Consequences:** A step that changes a note keeps its source positions. One that moves a note-off onto the tick of a later note-on of the same pitch must give the note-off the lower position.
