# 0135. Sleep Token II's default kit and Logic Pro Drums follow their makers' published maps

- **Status:** Accepted. Its count of Logic Pro Drums' articulations and pitches is amended by [ADR 0140](0140-the-maker-based-maps-take-drumverter-s-names-for-the-notes-they-left-out-as-unclear.md)
- **Date:** 2026-11-16

- `sleep-token-ii/default` drops note 96, `crash.4.choke`, since the library's published user guide gives Crash 4 no choke note. It has 57 articulations on 67 pitches, and a note on 96 is an `unmapped_notes` request.
- `logic-pro-drums` is written by hand from the GM Standard input mapping of Drum Kit Designer, the figure on the "Drum Kit Designer mappings" page of Apple's Logic Pro User Guide, whose note names count C3 as note 60. Each entry is `mapping`, at `high` where the figure's name gives the canonical name directly and `medium` where it is interpreted, as [ADR 0055](0055-m3-adds-maps-for-four-drum-libraries.md) sets for a library's own mapping. It has 27 articulations on 29 pitches:
  - three toms, High, Mid and Low, on 48, 45 and 41, each with its edge stroke, `tom.N.edge`, on 50, 47 and 43 ([ADR 0134](0134-the-vocabulary-adds-a-tom-s-edge-stroke-a-positional-articulation-as-the-snare-s-is.md));
  - the ride's outer bow, 51, as `ride.1.bow`, its inner bow, 59, as `ride.1.bow.alt`, its edge, 52, as `ride.1.crash`, and its bell, 53;
  - the left and right crashes, 49 and 57, as crashes 1 and 2, and their stops, 28 and 29, as their chokes;
  - the snare's edge, 34, its rimshot, 40, and its sidestick, 37; the hat's pedal splash, 31; the clap, 39, the tambourine, 54, the cowbell, 56, and the shaker, 70, as `maracas.hit`;
  - 35, a second note named Kick, and 33, a second named Hi-Hat Foot Close, only read, with 36 and 44 written.
- Logic's note 32, a rimshot on the snare's edge, is left out until the vocabulary has a name for it, and note 55, blank in the figure, is left out, so a note on either is asked about. The inferred map's fourth tom, its tom rimshot on 50, its splash on 55 and its china on 52 are gone.
- `garageband-drums` and `addictive-drums-2` stay as they are, inferred and unchecked.

**Why:** A published map from the library's maker names each note, where the inferred names were guesses from where the notes sit. A note mapped to a choke the library doesn't have, or an inferred tom where the maker puts a tom's edge, sends a real hit to the wrong sound.

**Consequences:** `logic-pro-drums` is no longer built in `private/` from local sources, so the committed file is its source, and the local build of it disagrees until it is updated. [ADR 0011](0011-m1-maps-for-general-midi-and-drum-libraries.md)'s line that every library but Sleep Token II has its names inferred is amended by this ADR. `tools/calibrate.py fit --check` gives the same styles before and after.
