# 0011. M1 ships a General MIDI map and maps built from the IOF map files and a Cubase drum map

- **Status:** Proposed
- **Date:** 2026-11-08

- M1 ships a General MIDI map, built from the General MIDI Level 1 percussion key map, and maps built from the files in the plan's Appendix B: the `.map` files bundled with IOF Drummer 6 and the Cubase drum map (`.drm`) for MixWave Sleep Token II.
- The IOF files are a data source only, never the model. Each assigns notes to 63 unnamed slots (`RemapCB1Data` to `RemapCB63Data`, value = note + 2, 1 = unset) for one library, and every file uses the same slots. Each slot gets a proposed canonical articulation, stored with low confidence. An entry is raised to high confidence once checked against the plugin.
- The Cubase drum map names its pitches, and those names give its articulations.

**Why:** These are the map files at hand. Once their slots are named, the IOF files cover several common libraries at once. General MIDI is a published standard, so it needs no vendor file.

**Consequences:** A conversion that relies on an unconfirmed slot name says so in its report until the slots are checked in the plugin. The maps are written in the project's own format, never copied from the vendor files ([ADR 0007](0007-local-only-files-live-in-private.md)).
