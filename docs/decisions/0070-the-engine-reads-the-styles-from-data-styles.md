# 0070. The engine reads the three styles from `data/styles/`, and the placeholder stays as the fit's source

- **Status:** Proposed
- **Date:** 2026-11-10

- `render/style.py` reads `tight`, `medium` and `loose` from `data/styles/<name>.toml` through `data_dir()` ([ADR 0024](0024-built-in-data-is-found-beside-the-source.md)), checking each against the `Style` model as it loads, once per run. A missing or invalid file, or one holding another style's name, is an error that names the file.
- `tight` stays the default, and the controls and `human-o-matic render --style` take the three names.
- `PLACEHOLDER`, Appendix A with the values ADR 0051 fills in, stays in the code as the source of the values calibration keeps ([ADR 0068](0068-what-calibration-fits-and-what-stays-modelled.md)), and is never rendered.

**Why:** The fit writes the files and the engine reads them, so nothing in the code repeats a fitted number, and the placeholder stays where the fit and the tests can compare against it.

**Consequences:** [ADR 0051](0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)'s rendering from the placeholders is amended by this ADR, and its values by [ADR 0068](0068-what-calibration-fits-and-what-stays-modelled.md) where they are fitted.
