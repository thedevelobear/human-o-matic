# 0104. A trial is its section cut from the song's whole render into a file of its own, after a bar of lead-in, at the song's tempo, holding nothing else

- **Status:** Accepted
- **Date:** 2026-11-13

- Each variant renders the whole song, so the guards and each section's stream are those of any render of it, and each section is then cut out: the notes the render gives it, moved so the file's first tick is the bar line before the section, or for the song's first section a bar of its first bar's length before it. A note played early has room, and the section starts on the file's second bar line.
- Each file is format 0, one track, at the song's working resolution ([ADR 0014](0014-work-at-a-whole-multiple-of-the-source-ppq.md)), and holds only:
  - the tempo and time signature in force at its first tick, and their changes up to its end, from the score's tempo map, so a `bpm` the session gave is written as a tempo;
  - the drum track's channel messages other than notes, controllers, program changes, pitch bend and aftertouch: the last of each before its first tick, at that tick, and those within, at their place;
  - the notes, in the target kit.
- It has no track name, marker, text or other meta event, and no sysex, so nothing in its bytes but the performance differs between a trial's variants.
- A trial's five files end on one tick, the section's end or the latest note-off of any of them, so they play the same notes, for as long, at the same tempo.

**Why:** A whole render keeps the streams and the guards as the owner heard them in the session, which a render of the section alone would change at its boundaries. The bar before gives the early notes room and keeps the DAW's bar lines on the section's. The drum part alone is what the kit plays, and its controllers keep a hi-hat's openness.
