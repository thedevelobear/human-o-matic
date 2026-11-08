# 0021. Conversion falls back within a family, and asks instead of changing family

- **Status:** Proposed
- **Date:** 2026-11-08

- A note is read with the source kit, and its articulation is found in the target kit by, in turn: the exact name; piece substitution; the name without its last variant, one variant at a time (`hat.open.quarter.tip`, then `hat.open.quarter`, then `hat.open`); and the piece's default (`snare.flam` to `snare.center`, `ride.1.crash` to `ride.1.bow`, `crash.1.mute` to `crash.1.hit`).
- Piece substitution re-spreads toms by register when the kits have different numbers of them: tom i of n_s becomes tom round-half-down(1 + (i - 1)(n_t - 1) / (n_s - 1)) of n_t. So 6 toms onto 3 go 1, 1, 2, 2, 3, 3, and 3 onto 6 go 1, 3, 6. Every other family keeps its piece, or takes the target's last piece when the target has fewer (`crash.3` to `crash.2`, `snare.2` to `snare`). The vocabulary says which families are re-spread.
- A hit never leaves its family unless the user picks a substitute. These are `conversion` decision requests instead, one per source articulation, with its count and positions:
  - the target kit lacks the family;
  - the target lacks a choke (the vocabulary's `ask_if_missing`), since in some libraries a choke is a silent grab, and playing the plain hit could sound a cymbal the source never did;
  - the articulation depends on a controller value in either kit, until controllers are resolved in M3 ([ADR 0009](0009-m1-resolves-notes-channels-and-velocity-ranges.md)).
- A request about a missing family may offer substitutes from another family, from a fixed list in the vocabulary (china to crash, stack to china, sticks to sidestick). One is used only when the user picks it.
- Notes the source kit doesn't map at all are one `unmapped_notes` decision request, listing each pitch with its channels, count and first positions.
- Positions are `[bar, beat]` from the time signature map, counted from 0 in the data and from 1 in messages, with at most 8 per group beside the full count.
- The answers are `substitutions`, from a source articulation to a target articulation, and `unmapped`, from a source pitch to a target articulation. `drop` leaves those notes out instead. A note a controller value decides among several articulations is keyed by their names joined with `|`.
- The report has a row per source and target articulation, with the count, each inexact step (what was asked, what was used, and which step it was, a pick being `picked`), both confidences, and how many velocities were moved into the target's range.
- Converted notes from different source notes that start on one target pitch and channel at the same tick, as when several toms are re-spread onto fewer, keep their pitches and are listed as collisions: per pitch and channel, how many ticks and notes, the source articulations and the first positions.
- Converting a kit to itself keeps every mapped note as it is.

**Why:** A hit that silently changes family, or a choke played as a full crash, is a wrong note that the user may not notice. Re-spreading toms keeps a fill moving down the kit, where taking the nearest number would put half of General MIDI's six toms on the floor tom.

**Consequences:** Until M3, a file with controller-driven hats needs an answer before it converts to another kit. `substitutions`, `unmapped` and `from_map` reach the user through `open_session` once the MCP layer exists.
