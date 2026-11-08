# 0019. Canonical articulation names follow one grammar, kept in a vocabulary file

- **Status:** Proposed
- **Date:** 2026-11-08

- The vocabulary is data, in `data/vocabulary.toml`, validated with pydantic when it loads: every family has a default articulation, every variant's parent is listed, and nothing is listed twice. A new family or articulation is added there, with a test, and needs no code.
- A name is `family[.piece].articulation[.variant...]`, in lower case with `_` inside a word. The family is the kind of drum or cymbal. The articulation is what is played. A variant refines it and can be dropped: a stroke (`tip`), an openness, a foot (`left`, `right`) or an unnamed alternate (`alt`, `alt2`).
- Pieces count from 1, the highest-pitched tom or the first cymbal of a kind. `tom`, `ride`, `crash`, `china`, `splash`, `stack` and paired percussion always write the number (`tom.1.hit`, `crash.1.choke`). `kick`, `snare`, `hat` and `cowbell` write it only for a second drum (`snare.center`, `snare.2.center`). Single instruments never do (`clap.hit`).
- A bare name is the library's ordinary stroke, and a variant is written only to tell two strokes apart in one kit, so there is no `edge` variant.
- Hat openness is in words: `hat.open.quarter`, `hat.open.half` and `hat.open.three_quarter`, and a bare `hat.open` is fully open. `hat.variable` is a hat whose openness a controller sets.
- A kit that has a variant has its parent, and each piece it has includes that piece's default, so a kit with `crash.2.choke` has `crash.2.hit`. Fallback then only ever moves up a name.

**Why:** One grammar lets a conversion move between libraries by meaning rather than by note number. Leaving the number off a first snare keeps the plan's `snare.center`, and openness in words converts by meaning, where one library's "Open 1" and another's first degree need not match.

**Consequences:** A map can name only what the vocabulary has, so a map that needs a new articulation adds it to the vocabulary first.
