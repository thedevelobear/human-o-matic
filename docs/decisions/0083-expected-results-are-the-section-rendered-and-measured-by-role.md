# 0083. A section's expected results are the section rendered with its controls and measured by role

- **Status:** Accepted
- **Date:** 2026-11-12

- After storing controls, `set_section_controls` renders the session in memory, with its stored controls, seed and takes, and gives each section it set an `expected` in plain words, from `render/describe.py`. They name, in order, each group of roles that plays, kick with double kick, backbeats, other snare, the riders by their families, the accent cymbals by theirs, fills and other drums, and the notes typed soft as a group of their own, each from its 5th to its 95th percentile velocity, or from its lowest to its highest under 5 notes. Then the riders' strong hits above their weak ones, the timing spread, and how far the snare and the riders sit behind the other notes.
- `render` and `export` give the same words, `says`, beside each section's statistics.
- While a note waits for an `unmapped` or `substitutions` answer nothing renders, so there is no `expected`. With only hit types or grids unconfirmed, it is given from the guesses.

**Why:** Words read off the engine's own render can't drift from what the engine does, as a model of it would. A song renders in a fraction of a second, and the exported file plays exactly that take.

**Consequences:** The words are one take's, so they move a little with the seed and the take. A range that reaches 127 shows a role at the ceiling.
