# 0103. Variant 5 is variant 4's plan rendered with its style's timing set to nothing

- **Status:** Accepted
- **Date:** 2026-11-13

- `render()` takes an optional `style`, which it renders with in place of the built-in style the plan names. Left out, as every caller but the blind test leaves it, a render is as before.
- `make_ab.untimed(style)` is the session's style with what moves a note in time set to 0: each tempo band's `shared_sd`, the offset an onset's hits share, `jitter_sd`, each hit's own offset, and its clip, `jitter_clip`, and `limb_ms`, each limb's mean offset, which puts the snare and the riders behind, and the style's `feel_ms`, how far `feel` lays back or pushes, and `drift_sd`, the song's slow timing drift. A note's offset is its limb's, with `feel`'s, plus the onset's shared offset and its own jitter, plus the drift ([ADR 0049](0049-each-section-draws-from-its-own-seeded-stream.md)), so each of its terms is then 0. The style is made in memory, never written to `data/styles/`.
- The controls are variant 4's, every velocity control as it set them: `energy`, `groove`, `dynamic_range`, `arc`, `fill_intensity`, `ghost_level` and `skip`. `tightness` scales only the shared offset and the jitter, so it then moves nothing, and `feel` keeps only the louder snare it brings when laid back.
- The backend draws the same numbers whatever they are scaled by, and the velocity guards read no timing, so variant 5's velocities are variant 4's, note for note, and every note starts on its grid point. The guards still move what they would with no offset anywhere: a note a tick from another the kit puts on its pitch at one grid point, a main note after its grace on the song's first tick ([ADR 0050](0050-guards-hold-every-backend-and-keep-each-section-independent.md)), and the notes next to a section played as it came in, which keeps its own timing in variants 4 and 5 alike.
- Variant 1's notes come from variant 3's plan rendered the same way, so variant 5's notes start where variant 1's do.

**Why:** The gate's "if 5 matches 4" asks what the timing adds, so variant 5 differs from variant 4 in timing alone. No control can give that: at any value of `tightness` and `feel`, the style's timing spreads and offsets are not 0.

**Consequences:** `render()` has one more argument, which only the blind test passes. A test holds, over grooves, controls, styles, tempos and seeds that `hypothesis` draws, every note on its grid point at the velocity the timed render gives it.
