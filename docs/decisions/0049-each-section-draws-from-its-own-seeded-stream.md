# 0049. Each section draws from its own seeded stream, and the song's drifts from streams of their own

- **Status:** Accepted. Its streams are amended by [ADR 0093](0093-added-notes-draw-from-a-stream-of-their-own-through-their-section-s-parameters.md)
- **Date:** 2026-11-09

- All randomness comes from `numpy.random.Generator`s built with `numpy.random.default_rng(SeedSequence(seed, spawn_key=...))` from the plan's seed ([ADR 0046](0046-controls-are-layered-pydantic-models-with-a-json-round-trip.md)). Nothing uses `random` or numpy's global state, and a render needs the seed: there is no default.
- A section's stream has the spawn key `(1, start, take)`: its first bar and its take. Keying by the first bar, not by the section's number, means splitting or merging one section leaves the others' streams as they were.
- The song's timing drift has the key `(0, 0)` and its energy drift `(0, 1)`. Each is drawn once, at every tick of the score in quarter notes, so they change only with the seed. A drift is a sum of Ornstein-Uhlenbeck processes, one per time constant, sampled exactly at those ticks, each with an equal share of the spread.
- The parametric backend draws a section's values in a fixed order whatever the notes' roles and types: one normal value per onset, then per note one for its jitter, one for its velocity and one uniform value for a rider's label. So a section's draws depend only on how many notes and onsets it has. Notes are taken in play order ([ADR 0048](0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).
- Values are worked out in float64 and rounded to ticks and velocities once, at the end. The same song, answers, plan, seed and `uv.lock` give the same bytes on one platform. numpy doesn't promise the same `Generator` streams across its versions, so an upgrade of numpy can change a render.

**Why:** A stream per section is what lets a section be rendered again without moving the others, and a song-wide drift is the long memory the research asks for. Keying streams by what identifies a section, rather than by its place in a list, keeps them stable under edits. The exact version pins of [ADR 0004](0004-exact-dependency-versions.md) are what make "the same session and seed" a promise.
