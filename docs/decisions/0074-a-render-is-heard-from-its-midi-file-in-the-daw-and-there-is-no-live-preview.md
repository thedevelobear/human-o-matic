# 0074. A render is heard from its MIDI file in the DAW, and there is no live preview

- **Status:** Proposed
- **Date:** 2026-11-11

- This version plays nothing through a MIDI port: there is no `preview.py`, no IAC Driver route, and `python-rtmidi` is not added.
- A render is heard by writing it to a new MIDI file through the kit the user plays, with `human-o-matic render --to-map` and, in M4, `export` from a session opened with `to_map`, then opening that file in the DAW on a track with that drum instrument.
- M3 has no preview PR. What remains of it after calibration is its gate: the exit is checked on the calibrated styles, and the owner listens to rendered files on their own kit. M3 is merged when the owner passes the gate.
- `preview` and `stop_preview` leave M4's tools, and the question policy's audition is a rendered file.

**Why:** How velocities sound depends on the sample library, so the review has to be on the user's own kit, and the DAW already plays a file through it. A file needs no port to enable or route, adds no dependency, and can be kept, compared and played again.

**Consequences:** Hearing a change in M4 takes an export and a drag into the DAW. The third PR of [ADR 0043](0043-m3-is-three-prs-and-its-gate-follows-the-third.md), and with it when M3 is merged, the line of [ADR 0045](0045-the-engine-is-render-modules-behind-a-small-instrument-seam.md) on `preview.py`, the gate after the preview PR in [ADR 0052](0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md), and the lines on `python-rtmidi` in [ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md) and [ADR 0056](0056-the-calibration-tools-add-no-dependency.md) are amended by this ADR. A live preview would need a new decision.
