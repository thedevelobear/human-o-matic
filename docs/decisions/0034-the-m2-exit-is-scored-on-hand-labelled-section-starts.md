# 0034. The M2 exit is scored on hand-labelled section starts in `private/labels/`

- **Status:** Proposed
- **Date:** 2026-11-09

- Each labelled drum track, a whole song, is one TOML file directly in the gitignored `private/labels/`, under any name ending in `.toml` ([ADR 0007](0007-local-only-files-live-in-private.md)). The labels and the songs are local files: nothing in them is committed, and no tracked file names what they hold.
- A label file has these keys, and any other key is an error:
  - `midi`: the path to the song's MIDI file, relative to `private/` unless it is absolute.
  - `from_map`: the built-in kit the drums are read through, as `analyze` takes `--from-map` ([ADR 0023](0023-built-in-library-ids.md)).
  - `bpm`, optional: a constant tempo that replaces the file's own, as `analyze` takes `--bpm` ([ADR 0016](0016-tempo-and-time-signatures.md)). A file with no tempo needs it, and a `bpm` outside 3.577 to 60,000,000 is an error ([ADR 0032](0032-bpm-is-the-only-tempo-a-user-gives.md)).
  - `track`, optional: the drum track, counting from 0, when the rules of [ADR 0017](0017-the-drums-are-one-whole-track.md) don't settle it, as `analyze` takes `--track`.
  - `starts`: the bar where each section begins, with bars counted from 0 as `analyze` counts them ([ADR 0016](0016-tempo-and-time-signatures.md)), so a DAW's bar 1 is bar 0 here. The list is strictly increasing, begins with 0 and has at least one start after it, and every start is below the song's bar count, `bars` in `analyze`'s summary ([ADR 0033](0033-analyze-takes-flags-and-an-answers-file-and-prints-json.md)).
  - `tuned`, optional: a boolean, `true` for a track the detector's parameters were tuned on. Left out, it is `false`.
- A song whose sections begin at a DAW's bars 1, 9, 25, 41 and 57 is labelled:

  ```toml
  midi = "path/to/song.mid"
  from_map = "gm"
  bpm = 120      # replaces the file's tempo; needed when it has none
  track = 1      # only when the drum track isn't clear
  starts = [0, 8, 24, 40, 56]
  tuned = true   # only when the detector was tuned on this track
  ```

- A label file that breaks these rules, or whose song still raises a `tempo` or `drum_track` request with them, fails the measurement, naming the file. The song's other requests stay open, and its sections are found in the score as `normalize()` leaves it.
- A boundary is a section start other than bar 0, which is never counted. A detected boundary matches a labelled one when they are at most 1 bar apart, and each boundary is in at most one match: the matches are the most that such a one-to-one pairing allows.
- Per track, with `m` matches, `d` detected and `l` labelled boundaries: precision is `m / d` (0 when `d` is 0), recall is `m / l`, and F1 is `2m / (d + l)`.
- The headline is the mean of the per-track F1 over all tracks, so each track counts equally and a long song doesn't dominate. The exit holds when at least 10 labelled tracks have a mean F1 of at least 0.70.
- Beside the headline are the pooled F1, `2Σm / (Σd + Σl)` over all tracks, and the mean F1 over the tracks not marked `tuned`, with how many there are. The untuned mean is only reported, and doesn't change whether the exit holds. When no track is marked, it is the headline, and when every track is, there is none.
- The measurement turns SMF markers off. Where a file has them the detector takes its sections from them, which would make the score trivial, so this tests the heuristic itself.
- The code that reads a label file, matches the boundaries and computes the scores is in `src/`, with unit tests that build their cases in code, so CI runs them.
- Only the measurement over the label files is a test marked `private`, and it skips when `private/labels/` is missing or holds no label file. It reports each track's precision, recall and F1, the mean F1, the pooled F1, and the untuned mean with its count. With 10 or more tracks it fails when the mean F1 is below 0.70. With fewer it skips with the scores in its reason, so a pass always means the exit holds.

**Why:** Hand labels are the only ground truth for what a section is, and one small file per track is the least work to label. Matching one to one keeps two detections near one labelled boundary from both counting. A path relative to `private/` keeps a label working wherever the repository is.

**Consequences:** The exit can't be measured until at least 10 tracks are labelled. The detector's parameters are tuned on the first few, and those tracks flatter the headline, so the mean over the tracks not marked `tuned` is the check that the tuning holds.
