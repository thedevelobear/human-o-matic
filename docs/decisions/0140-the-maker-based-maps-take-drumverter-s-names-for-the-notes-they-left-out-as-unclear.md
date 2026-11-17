# 0140. The maker-based maps take drumverter's names for the notes they left out as unclear

- **Status:** Accepted
- **Date:** 2026-11-17

- Where a map written from its maker's own mapping left a note out because the mapping names it unclearly, and drumverter names it, the map takes drumverter's name, at `medium` ([ADR 0137](0137-drumverter-s-published-note-maps-are-a-source-for-the-built-in-maps-and-a-maker-s-own-map-wins.md)):
  - `counterkit`: 64 and 65, the mapping's hi-hat strokes marked "OC", as `hat.variable` and `hat.variable.tip`, a controller-shaped hat's edge and tip strokes, each bound with `cc = { mode = "shape" }`, as a controller-shaped hat is in the other maps. 22 articulations on 22 notes.
  - `ni-drum-lab`: 62 and 63, the mapping's snare "Kang" and "Shot", as second notes of `snare.center`, only read, so `snare.center` is `medium`, an entry taking the lowest of its notes' ([ADR 0025](0025-proposed-names-ship-at-low-confidence.md)). 32 articulations on 39 notes.
  - `logic-pro-drums`: 75, which Apple's figure doesn't show, as `sticks.hit`. 28 articulations on 30 notes.
- Every other note of these maps, and all of `sleep-token-ii`, keep their maker's names where drumverter names them otherwise: Sleep Token II's cymbal mutes and tom rimshots, Logic's tom edges and inner bow, and NI Drum Lab's damped kick and snare.
- Calibration reads Counterkit's 64 and NI Drum Lab's 62 and 63 as it did while they were unmapped, leaving them out, so the fitted styles stay as they are until they are fitted again with them read.

**Why:** A note left out is asked about on every conversion, and drumverter's name for it is a reading the maker's map doesn't contradict, where a maker's own name for a note still wins over drumverter's.

**Consequences:** [ADR 0055](0055-m3-adds-maps-for-four-drum-libraries.md)'s notes left out of Counterkit and NI Drum Lab, and [ADR 0135](0135-sleep-token-ii-s-default-kit-and-logic-pro-drums-follow-their-makers-published-maps.md)'s count of Logic Pro Drums' articulations and pitches, are amended by this ADR. Reading those three notes in calibration moves the styles slightly, so they are read only when the styles are fitted again and heard.
