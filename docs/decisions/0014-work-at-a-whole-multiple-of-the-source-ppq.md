# 0014. Songs are worked on and written at the smallest multiple of their PPQ that is at least 960

- **Status:** Accepted
- **Date:** 2026-11-08

- A file is read at its working PPQ, and every song is written at it: the smallest whole multiple of the source PPQ that is at least 960. 96 and 480 become 960, 384 becomes 1152 and 100 becomes 1000. A PPQ of 960 or more is kept.
- Every tick scales by a whole number, so no position is ever rounded, and a source PPQ that doesn't divide 960 is never forced onto 960. The result always fits the file header's limit of 32,767.
- `MidiSong.source_ppq` keeps the file's own resolution.

**Why:** At 96 PPQ and 129 BPM one tick is 4.8 ms, too coarse for performed timing, and a whole-number factor loses nothing. Working at the output resolution from the start means later steps never convert.

**Consequences:** Outputs can differ in PPQ (960, 1000, 1152) depending on the input.
