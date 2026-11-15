# 0122. A round sent again takes back what its answers set before and set no longer

- **Status:** Accepted
- **Date:** 2026-11-15

- When the page sends a round, it keeps, for each section, the controls the round's answers set: the group-wide tabs', Energy, Soft notes, Groove and Fill, on every section of the group, and the Last repeat tab's on its own section; for the song-wide round, the song's `tightness` and `feel`. When the round is sent again, a control its answers set at the last send and no longer set is sent as `null`, so the section takes the song's value, or the style's default, again. So "your call" after a row unsets that row's controls, and "chorus, big and open" after "verse, holding back, building" unsets the `arc: build` the verse set.
- A control Fine-tune moved is sent as moved and never taken back. A Ramp tab's answer is never taken back: `ramp: 0` is already the default, and it is set so the question isn't asked again.
- The song-wide round takes back the song's `tightness` with `set_section_controls` without `section_ids`, since `set_style` can set it but not unset it.
- What the answers set is kept in the page's memory for the song as opened, and starts empty when the song is opened again. A section edit keeps it only for the sections the edit leaves with the same first bar, bars and group, and forgets it for the rest, so taking back what a round set never reaches a section that a split, a merge, a moved boundary or a new group has made into another.

**Why:** Submit sends the whole round as it stands, and "your call" keeps the song's controls, or a repeat its group's. Without taking back what an earlier answer set, a changed answer would leave the old answer's controls under the new one's.

**Consequences:** [ADR 0120](0120-the-question-window-sends-only-the-controls-changed-and-enter-on-set-it-by-hand-opens-its-controls.md)'s line that the page can't unset a control once it is sent holds for Fine-tune only. Fine-tune shows a section's values without the controls the round's answers set before, under what they set now.
