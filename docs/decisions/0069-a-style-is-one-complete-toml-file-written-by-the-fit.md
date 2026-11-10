# 0069. A style is one complete TOML file in `data/styles/`, written by the fit

- **Status:** Proposed
- **Date:** 2026-11-10

- Each style is one file, `data/styles/<name>.toml`, holding every field of the `Style` model, so a file alone is the whole style. The shared velocities ([ADR 0065](0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md)) are written in each of the three, the same in all.
- `tools/calibrate.py fit` writes the files, with a header comment saying so, and `fit --check` compares them with a fit run again and writes nothing. They are never edited by hand.
- Fitted numbers are rounded to hundredths, and kept ones are the placeholder's exactly ([ADR 0068](0068-what-calibration-fits-and-what-stays-modelled.md)), so the same grooves always give the same bytes.
- A file holds aggregate statistics only, and neither its name nor its contents name a folder, a pack, a library or a file ([ADRs 0007](0007-local-only-files-live-in-private.md) and [0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)).

**Why:** One file per style loads by its name with nothing to assemble, and the fit writing the shared part three times costs nothing, where a separate shared file would make every style two files to read and keep in step.

**Consequences:** A change to the shared velocities changes all three files at once, which `fit --check` shows.
