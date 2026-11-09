# 0043. M3 is three PRs, the engine, calibration and preview, and its gate follows the third

- **Status:** Proposed
- **Date:** 2026-11-09

- M3 lands in three PRs, in this order, each a branch from `main` ([ADR 0003](0003-branches-off-main-merged-without-squashing.md)):
  1. `feat/engine`: the control vector, the compiler, the sampler, the guards and `generic` mode, on the plan's Appendix A placeholder defaults, with the plan's property tests.
  2. `feat/calibration`: `tools/infer_map.py`, `tools/calibrate.py` and the styles in `data/styles/`, which replace the placeholders ([ADR 0044](0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)).
  3. `feat/preview`: playback through a virtual MIDI port, the macOS IAC Driver.
- M3's gate follows the third PR. Its exit, that raising each control moves its measured statistic the right way and that the property tests pass, is checked there, and the engine PR already carries the tests for its own part of it, on the placeholders.
- Each of the three is branched from `main` after the one before it has merged.
- The plan's progress table says which of the three is under way, and M3 is merged when the third is.

**Why:** The engine can be built and tested without the local files, calibration needs them ([ADR 0007](0007-local-only-files-live-in-private.md)), and the preview can only be checked once the owner has enabled the IAC Driver and tried it, so it comes last. Each of the three is smaller to review than all of M3.

**Consequences:** Until calibration merges, the engine renders with the placeholders. Each PR adds the runtime dependencies its own code first imports ([ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md)), so `python-rtmidi` waits for the preview.
