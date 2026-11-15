# 0128. The feedback's settings include each section's take

- **Status:** Accepted
- **Date:** 2026-11-15

- The `settings` field the feedback form sends ([ADR 0099](0099-the-site-s-feedback-form-keeps-text-and-settings-never-midi.md)) holds exactly these keys: `from_map` and `to_map`, the kits the song was opened with; `style`, `seed` and `bars`; `sections`, how many; `song_controls`, the song's own controls; `section_controls`, each section's own controls, in song order; and `takes`, each section's take, in song order.
- The controls are those the session set, by `ControlVector`'s names, with unset ones left out, and the page keeps no other name.
- They are read from `get_sections` after the download, so they are the render the user downloaded.

**Why:** A section's take draws it again from another stream, so the seed alone doesn't say which render the user heard. With each take, the settings name it.

**Consequences:** ADR 0099's list of the settings is amended by this ADR. A take is a count, so the feedback still holds nothing of the file, its name, a note or a section's words.
