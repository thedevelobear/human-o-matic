# 0063. A pack, a folder's first-level subfolder, is a source

- **Status:** Proposed
- **Date:** 2026-11-10

- For [ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)'s rule that no style is fitted on one source, a source is a pack: a first-level subfolder of a folder in `private/midi/`, or the folder itself for the files directly in it. A band that pools several packs meets the rule, even when they share a folder.
- `tools/calibrate.py measure` reports, for each band, how many folders and packs feed it and the largest pack's share, and flags a band that one pack supplies alone or nearly alone, 90% or more.

**Why:** A folder of performed MIDI can hold several packs, each one drummer's or one set's playing, so a folder can pool many sources and one source is what a pack holds.

**Consequences:** What counts as one source in [ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md) is amended by this ADR. A band fed by one pack still can't be fitted.
