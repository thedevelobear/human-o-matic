# 0025. A proposed name ships at low confidence, and only a check raises it

- **Status:** Proposed
- **Date:** 2026-11-08

- An articulation whose name is a proposal, inferred from where a library puts the note rather than named by a source, ships with `source = "inferred"` and `confidence = "low"`. That includes best guesses with little behind them: they ship, and stay `low`.
- Nothing raises a confidence automatically. A built map never gives an entry more confidence than the proposals that name it, and an entry with several notes takes the lowest of its notes'.
- Confirming a name in the instrument is a one-line change, after which the map is built again with that entry as `source = "checked"` and `confidence = "high"`. A wrong name is corrected the same way.

**Why:** An unchecked name can send a real hit to the wrong drum. Keeping it `low` makes every conversion that relies on it say so in its report ([ADR 0021](0021-conversion-falls-back-within-a-family.md)), and only a person listening to the instrument can settle it.

**Consequences:** Until their names are checked, converting from or to these libraries reports low confidence on almost every note.
