# 0027. Two hits on one drum from 5 ms to under 45 ms apart are a grace and its main, unless the gap is a grid step

- **Status:** Accepted
- **Date:** 2026-11-08

- A drum is a family and piece, such as `snare` or `tom.2`, whatever the articulation, so a center hit can be the grace of a rimshot.
- Two hits in a row on one drum, at least 5 ms and under 45 ms apart, are a grace and its main, the later one being the main. Several in a row are all graces of the last one, as in a drag.
- They are two notes of the grid instead when the gap is within 15 ms of a grid candidate's step at the local tempo, as with a 32nd roll or a double kick at a fast tempo: 32nds at 200 BPM are 37.5 ms apart.
- Hits on one drum under 5 ms apart are one stroke, such as a hat pedal under a stick hit or a doubled note, and share a grid point ([ADR 0028](0028-limbs-within-20-ms-share-a-grid-point.md)).
- The main is quantized as any other hit. The grace goes before the main's tick by its performed gap in milliseconds, rounded to a tick, at least one tick before it and never before tick 0. It takes its main's beat and grid, so its offset is about its main's. The score links it to its main by the main's source note ([ADR 0031](0031-the-score-is-frozen-canonical-hits-with-their-source-notes.md)).

**Why:** A grace isn't on the grid, and snapping it there would turn a flam into two notes of a beat. Placing it by its gap keeps the spacing from grace to main, which the plan's property tests require, and the link lets the engine move both together. A gap under 5 ms is heard as one hit, not a flam. The grid-step exception keeps fast rolls and double kicks on the grid. 15 ms covers the gap error of two notes jittered by a few milliseconds each, and below about 125 BPM no grid step is within 15 ms of a gap under 45 ms, so there every such pair is a grace.

**Consequences:** At a fast tempo a wide flam, whose gap is near a 32nd, is read as two 32nds. A run of close hits off the grid, such as a buzz roll, becomes graces of its last note, however long it is.
