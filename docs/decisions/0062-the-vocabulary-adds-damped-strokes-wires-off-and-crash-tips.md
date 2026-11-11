# 0062. The vocabulary adds damped strokes, a snare with its wires off, and a crash's tip stroke

- **Status:** Proposed
- **Date:** 2026-11-10

- `data/vocabulary.toml` adds four names, each a variant that drops to the stroke it refines:
  - `kick.hit.dampened` and `snare.center.dampened`: the stroke with the head damped, as by a pillow or a hand;
  - `snare.center.wires_off`: the snare's center stroke with its wires off;
  - `crash.N.hit.tip`: a crash struck with the tip of the stick, as `stack.N.hit.tip` is.
- A variant can now also be a damped stroke (`dampened`) or the snare with its wires off (`wires_off`), beside a stroke, an openness, a foot and an unnamed alternate ([ADR 0019](0019-canonical-names-follow-one-grammar.md)).
- A note a map left out only because the vocabulary had no name for it is named with these, where its mapping's name is clear. A note whose mapping's name can't be read with confidence stays out, and asked about, until it is understood.

**Why:** Each of these is a sound a library's own mapping names clearly, and a kit that has it should write it back as itself rather than as the plain stroke. As variants they fall back to that stroke on a kit without them, which is the nearest sound and changes no family ([ADR 0021](0021-conversion-falls-back-within-a-family.md)).

**Consequences:** The list of variant kinds in [ADR 0019](0019-canonical-names-follow-one-grammar.md) is amended by this ADR.
