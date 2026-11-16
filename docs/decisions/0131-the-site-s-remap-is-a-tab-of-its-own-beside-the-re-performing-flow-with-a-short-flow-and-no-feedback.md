# 0131. The site's remap is a tab of its own beside the re-performing flow, with a short flow and no feedback

- **Status:** Proposed
- **Date:** 2026-11-16

- The page has two top-level tabs: the re-performing flow, as it is, and Remap.
- Remap's flow is: choose a file; choose the kit it was made for and the kit that will play it; answer the `drum_track`, `unmapped_notes` and `conversion` requests that came up, and nothing else; download. It has no sections, style, questions about feel, takes or Feedback step, and the Feedback form stays with the re-performing flow.
- It runs the same engine in the same worker, through a call beside `open_session` that takes the file's bytes ([ADR 0114](0114-the-worker-api-takes-the-file-s-bytes-and-display-name-and-answers-an-error-as-error.md)), and keeps the site's rules: the file stays in the browser, nothing is stored, and "Delete my file now" clears it ([ADR 0098](0098-the-site-is-open-to-anyone-with-its-link-held-by-limits-and-keeps-no-user-s-midi.md), [ADR 0121](0121-the-page-has-seven-steps-until-the-feedback-form-opens-the-song-afresh-for-each-kit-and-takes-the-next-seed-for-a-new-take.md)).
- Its download is the same bytes as the MCP tool's output for the same file, kits and answers.

**Why:** A user who wants only another kit shouldn't walk through sections and feel. The feedback's settings describe a render ([ADR 0128](0128-the-feedback-s-settings-include-each-section-s-take.md)), which a remap doesn't have.

**Consequences:** The top bar of steps belongs to the re-performing tab, whose steps [ADR 0121](0121-the-page-has-seven-steps-until-the-feedback-form-opens-the-song-afresh-for-each-kit-and-takes-the-next-seed-for-a-new-take.md) sets, unchanged.
