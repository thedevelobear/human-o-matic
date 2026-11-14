# 0089. The vocabulary's rows set only their controls, are written for a song at the defaults, and beyond the plan's four are drafted unheard and refined by ear

- **Status:** Accepted. Its count of answers is amended by [ADR 0096](0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md) and [ADR 0108](0108-the-skill-s-budget-is-about-20-questions-with-a-third-per-group-only-for-a-ramp.md)
- **Date:** 2026-11-12

- A row sets the controls it fills in, and the agent leaves the rest unset, so they come from the song's controls and then the style's defaults. Every style's defaults are 0.5 for `energy`, `groove`, `dynamic_range`, `fill_intensity` and `ghost_level`, 0.75 for `tightness`, 0 for `feel`, `steady` for `arc` and false for `skip`.
- Rows are written for a song whose own controls are unset. Where the user has set a control for the whole song, such as its tightness, a section moves from the song's value by its row's difference from the default, and leaves the control unset where its row gives the default.
- The `Answers` table has the plan's four examples first, at the plan's values, and 26 more: section kinds, answers to the questions `get_sections` suggests, fills, feel, `arc`, the drummer's style and tightness, "your call", which sets nothing new, and "leave this alone", `skip`. "The drop" is a section, not `arc: drop`. The `Refinements` table has three changes, a refinement moving a control by about 0.1 for "a bit" and 0.2 for "a lot". Full power starts at `energy` 0.85, from which every style's kick and backbeat centers are 118 or more, as a test holds.
- Every value but the plan's four, and every range, is drafted without listening, and the file says so. The owner refines them by ear, in the end-to-end session and the blind test, and a refined value changes the table, whose form the test holds.

**Why:** No agent can hear the output, so only the owner can say whether "full power" is 0.95. Setting only a row's controls keeps a song-wide answer, such as its tightness, from being undone section by section, and rows written for a song at the defaults read the same in any song.

**Consequences:** Until the owner has listened, an answer that sounds wrong is a value to refine, not a fault in the skill.
