# 0009. M1 resolves notes, channels and velocity ranges, and CC-driven articulations wait for M3

- **Status:** Accepted. Its line that controllers are resolved in M3 is amended by [ADR 0053](0053-a-controller-bound-note-keeps-its-controller-value.md)
- **Date:** 2026-11-08

- The map schema has every field of [ADR 0008](0008-library-neutral-drum-maps.md) from the start.
- M1 reads and writes articulations by note, channel and velocity range. Velocity behavior is a velocity range that selects one articulation among several on the same note. Rendered output for that articulation stays inside its range.
- CC behavior is a controller value that selects or shapes an articulation, such as hi-hat pedal openness. M1 stores it, validates it, and preserves the controller events in the file. CC-driven articulations are resolved in M3, when the engine needs them.

**Why:** Notes, channels and velocity ranges are enough to read and write most library files correctly. Resolving controllers means following their values over time, which belongs with the engine. Having every field from the start keeps the map files stable.

**Consequences:** Until M3, converting cannot settle an articulation that depends on a controller value. The render guards keep each note's velocity inside its articulation's range.
