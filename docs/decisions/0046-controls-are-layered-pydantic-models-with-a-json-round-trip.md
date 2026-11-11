# 0046. The controls are layered pydantic models with a JSON round trip

- **Status:** Accepted. Its `tight`-only style is amended by [ADR 0070](0070-the-engine-reads-the-styles-from-data-styles.md)
- **Date:** 2026-11-09

- `human_o_matic/controls.py` holds frozen, strict pydantic models that take no unknown field, so a string or a boolean is never read as a number:
  - `ControlVector`: the plan's nine controls, each in its range or unset. `energy`, `groove`, `dynamic_range`, `tightness`, `fill_intensity` and `ghost_level` are 0 to 1, `feel` is -1 to +1, `arc` is `steady`, `build` or `drop`, and `skip` is a boolean. NaN and infinities are refused.
  - `Controls`: every control set, as a style's defaults are and as a section is rendered.
  - `SectionPlan`: `start`, the first bar from 0; `bars`; `group`, its repeat group; `controls`; `take`, from 0, which picks another draw; and `note`, the user's words.
  - `SessionPlan`: `style` (`tight` until calibration adds `medium` and `loose`, [ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)), `seed`, `controls` for the whole song, and `sections`, which start at bar 0 and each where the one before ends.
- A section is rendered with its own controls over the song's, and the song's over the style's defaults: an unset control is decided by the layer below.
- The seed is an integer from 0 to 2^53 - 1, so every seed is exact in JSON.
- The JSON form is `model_dump(mode="json", exclude_none=True)`, which leaves unset controls out, and `model_validate_json` reads it back to an equal model.
- The plan holds what a render needs besides the song and its kits. The file path, the maps and the answers to decision requests stay for `session.py`, which stores a session on disk in M4.

**Why:** Layers let one answer set a few controls and leave the rest to the song and the style, as the question policy asks and repeats inherit. Strict models make a typo or a wrong type an error at the boundary, where the agent can still fix it. One JSON form, read back exactly, is what makes "the same session and seed give the same file" checkable.
