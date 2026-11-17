# 0139. Krimh Drums follows the instrument's own mapping page, an octave lower than the guide was read

- **Status:** Proposed
- **Date:** 2026-11-17

- `krimh-drums` is written from the instrument's own mapping page, its "Mapping Preset" for Krimh Drums. The page names each note, with C3 as note 60, so Kick Main, C0, is note 24. Every note is 12 lower than [ADR 0055](0055-m3-adds-maps-for-four-drum-libraries.md)'s reading, which counted the guide's keyboard, drawn with no note numbers, from 36. The names and their layout are the guide's, unchanged.
- Each entry is `mapping`, at `high` where the page's name gives the canonical name directly (the kicks, the snare's strokes, the four toms, the ride, the closed hat and its tip, the pedal, the X-Hat's closed stroke and the splashes) and `medium` where it is interpreted (the open degrees, an open tip with no degree, the pedal opened, crashes and chinas numbered from their left and right). A note the page gives a second pitch for, Kick Main's 22, the X-Hat's closed 70 and its fifth opening's 71, has it as a second note, only read. 44 articulations on 50 notes.
- Left out, and asked about: 37, the page's Tom FX, until where it sits among the toms is known, and 17, which the page gives to the hat pedal's controller rather than a drum.
- Drumverter's map of Krimh Drums has the same notes, and the page wins where they differ ([ADR 0137](0137-drumverter-s-published-note-maps-are-a-source-for-the-built-in-maps-and-a-maker-s-own-map-wins.md)): 23, the page's Kick 2, which drumverter calls a left kick; 25 and 29, the page's off-center and no-wires strokes, which drumverter calls a side and an off-center stroke; 35 to 37, the page's toms 3 and 4 and Tom FX, which drumverter calls floor toms 2, 3 and 1; 50, the page's open tip, which drumverter gives the least open degree; and 17, which drumverter reads as a controller-shaped hat.

**Why:** The page is the maker's mapping inside the instrument, with note names, where the guide's keyboard has none, so it settles the octave the guide left open. Drumverter's kick on 24 agrees with it.

**Consequences:** [ADR 0055](0055-m3-adds-maps-for-four-drum-libraries.md)'s line that Krimh Drums' numbers rest on reading its kick at 36, every entry low, is amended by this ADR. `krimh-drums` still serves Krimh Drums Free, whose guide draws the same mapping. Calibration doesn't read through it, so the styles don't change.
