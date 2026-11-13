# 0102. Variants 1 to 3 are the score at one velocity, naive randomization of it, and the engine at its defaults

- **Status:** Proposed
- **Date:** 2026-11-13

- **1, quantized, one flat velocity:** every note on its grid point, as the engine places it with no timing ([ADR 0103](0103-variant-5-is-variant-4-s-plan-rendered-with-its-style-s-timing-set-to-nothing.md)), at one velocity, `--velocity`, 100 by default. Hit types aren't read, so soft notes play at it too. The velocity is held to the range of each note's articulation in the kit, so every variant plays the same articulations.
- **2, naive randomization:** variant 1 with each note moved by an offset drawn from a normal distribution of mean 0 and standard deviation 8 ms, through the tempo map and rounded to a tick, and its velocity by a whole number drawn uniformly from -12 to +12, then held to 1 to 127 and to its articulation's range. Each note's draws are its own, with no drift and no offset shared by an onset, and the engine's guards don't hold them, so a note may pass the cap or change places with another. Only what a MIDI file needs is held: a note keeps its length and starts no earlier than its file's first tick, two notes of one pitch never start on one tick, the later moving a tick on, and each ends by the time the next of its pitch starts. The draws come from a numpy `Generator` built from `SeedSequence(seed, spawn_key=(1, start))`, `--seed` and the section's first bar, one stream per section: the offsets of its notes in play order, then their velocities.
- **3, engine defaults, no questions:** the engine with nothing asked: the session's sections and seed, the default style, `tight`, no controls, and every section's first take.
- All three use the session's answers to its requests, the hit types, grids, unmapped notes and substitutions, which the score needs, and none of its controls, style or takes.

**Why:** The plan names the three. 100 is the velocity most piano rolls give a note, so variant 1 sounds as a part programmed at one velocity does. Naive randomization knows nothing of the song, so each draw is independent noise, the kind the research the plan cites finds listeners rate below correlated drift. Variant 3 with the session's sections and seed differs from variant 4 only by what the answers set.

**Consequences:** In variants 1 and 2 soft notes are as loud as the rest. Variant 1 is not matched in loudness to the engine's variants: `--velocity` sets it.
