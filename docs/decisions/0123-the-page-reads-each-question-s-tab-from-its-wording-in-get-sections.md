# 0123. The page reads each question's tab from its wording in `get_sections`

- **Status:** Accepted
- **Date:** 2026-11-15

- `get_sections` gives a section's questions as text, and its reply stays as it is. The page reads which tab a question is from its words: one beginning "What's the energy in" is Energy, "Should its soft notes be more present" Soft notes, "Steady and even, or more groove" Groove, "How hard should the fill" Fill and "Build up into" Ramp, and one ending "the same, or bigger, as the last time?" Last repeat.
- A question the page doesn't read as one of them is still a tab, with its text and "your call" alone, and "Set it by hand" opening no control, so the page never leaves out a question the engine gives.
- A group's round, when drawn, has a tab for each of its sections' questions but the ramp question. A Ramp tab joins a round only once the round is sent: one for each group whose sections then ask the ramp question with both groups asked about, over those sections, named by the first of them, so a later Ramp tab of the same group is counted as a question of its own.
- A test runs the page's flow under Pyodide on a song built in code whose questions are of all six kinds, so a change to the engine's wording that the page no longer reads fails it.

**Why:** Reading the words needs no change to the tools' replies, which the skill reads too, and the engine words its questions in a few fixed sentences, which the test holds.

**Consequences:** A change to a question's wording in `analyze/facts.py` or `service.py` changes `js/questions.js` with it.
