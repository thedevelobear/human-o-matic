# 0017. The drums are one whole track, chosen by rules in turn

- **Status:** Accepted
- **Date:** 2026-11-08

- The drum part is every note of one track, on whatever channels they use, since a library can put articulations on several channels ([ADR 0008](0008-library-neutral-drum-maps.md)). Other tracks pass through unchanged.
- The track is, in turn: the `track` argument; the only track with notes; the only track whose name contains "drum", in any case; the only track with notes on channel 10 (9 counted from 0). A rule that matches no track or several hands over to the next.
- When no rule settles it, or `track` names a track without notes, it is a `drum_track` decision request listing each track with notes: its index, name, channels and note count.

**Why:** Channel 10 alone misses many files, such as grooves with their drums on channel 16. The rules follow the plan's order, and asking beats guessing when they don't settle it.

**Consequences:** A format 0 file that holds a whole band in one track would be taken whole. Splitting a track by channel needs a new decision.
