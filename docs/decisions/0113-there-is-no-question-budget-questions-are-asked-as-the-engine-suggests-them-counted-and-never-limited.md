# 0113. There is no question budget: questions are asked as the engine suggests them, counted and never limited

- **Status:** Accepted
- **Date:** 2026-11-14

- Neither the skill nor the page has a question budget: no "about 20" for a song, and no limit of two questions a repeat group with a third only for a ramp. A group gets every question `get_sections` suggests for its sections, the ramp question among them, so the engine's facts decide what is worth asking.
- The questions are still counted as [ADR 0090](0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md) counts them: the kits question when it is asked, the confirmation batch as one, each other question as one, and the echo's "sound right?" not at all. The count is still shown, to the user at the end and on the page as it goes, and limits nothing.
- The ramp question stays as [ADR 0108](0108-the-skill-s-budget-is-about-20-questions-with-a-third-per-group-only-for-a-ramp.md) sets it: `get_sections` suggests it where the next section is 0.2 or more louder, it is asked once both groups have been asked about, once per group, and "no", "none", "straight in" and "your call" are `ramp: 0`. "Your call" is always accepted.

**Why:** A cap makes the agent or the page leave out a question the engine found worth asking, and the best render needs every answer that changes it. The count still shows what a song cost.

**Consequences:** The budget of [ADR 0090](0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md), about 12 and then about 20, and [ADR 0108](0108-the-skill-s-budget-is-about-20-questions-with-a-third-per-group-only-for-a-ramp.md)'s budget of about 20 and its limit per group, are amended by this ADR. The skill's text still states a budget until a later branch, `feat/open-questions`, changes it: `SKILL.md`'s rules 3 and 7, its step for each repeat group, and its count told "against the budget of about 20". No test, tool or vocabulary line holds the budget's numbers, but that branch reads `tests/test_skill.py`, `tools/check_answers.py` and the agent pass's brief again. Until then the skill and the page differ: the skill stops near 20 questions, and the page asks every one. The blind test's `--questions` stays a count. A song with many groups asks more, and the count shows it.
