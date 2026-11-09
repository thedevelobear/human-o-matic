# 0044. M3 ships the styles `tight`, `medium` and `loose` only, pooled by tightness band, with no named or numbered drummers

- **Status:** Proposed
- **Date:** 2026-11-09

- `data/styles/` holds three styles: `tight`, the default, `medium` and `loose`. There is no style for one drummer, by name or by number.
- Each style is fitted on the grooves of all the performed MIDI in `private/midi/` whose measured tightness falls in its band, pooled together, so no style is fitted on one source. Where the bands are cut is set with calibration.
- A style file holds aggregate statistics only ([ADR 0007](0007-local-only-files-live-in-private.md)), and neither its name nor its contents identify a source.

**Why:** No tracked file names what `private/` holds ([ADR 0007](0007-local-only-files-live-in-private.md)). A style named after a drummer would name a source, and a numbered one would still be one source's statistics in a file of its own. Bands of tightness pool every source and give the three styles the plan already defaults to.

**Consequences:** A style is how grooves of one tightness play, not one drummer's feel. `set_style`, in M4, takes one of the three names, and a style per drummer would need a new decision.
