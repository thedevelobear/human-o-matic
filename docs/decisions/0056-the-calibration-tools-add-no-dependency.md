# 0056. The calibration tools add no dependency, and `symusic` is not used

- **Status:** Accepted. Its line on `python-rtmidi` is amended by [ADR 0074](0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)
- **Date:** 2026-11-10

- `tools/infer_map.py` reads performed MIDI with the project's own reader (`read_midi`, over `mido`), and `tools/calibrate.py` will read it the same way and through `normalize()`, and fit with numpy. M3's calibration adds no dependency.
- `symusic`, which [ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md) planned for scanning performed MIDI in M3, is not added. A scan of every folder of performed MIDI in `private/midi/` with the project's reader takes about 7 seconds, timing and readings included.
- `python-rtmidi` still arrives with the preview ([ADR 0043](0043-m3-is-three-prs-and-its-gate-follows-the-third.md)).

**Why:** The project's reader is fast enough for the whole collection, and calibrating on the reading the app itself uses keeps the statistics true to what a render sees. A second MIDI library would bring its own pairing of notes and ticks, and a type stub ([ADR 0018](0018-mido-is-typed-by-a-local-stub.md)), for no gain.

**Consequences:** The line on `symusic` in [ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md) is amended by this ADR, and the plan's Appendix B drops it.
