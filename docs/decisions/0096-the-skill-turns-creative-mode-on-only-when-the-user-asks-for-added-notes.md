# 0096. The skill turns creative mode on only when the user asks for added notes

- **Status:** Accepted
- **Date:** 2026-11-13

- `SKILL.md` never suggests creative mode and never asks whether to add notes. A request for notes the song lacks, such as "make it more creative", "add ghost notes in the verses" or "fill in the transitions", sets `creative: true` on the sections it names, or for the whole song without `section_ids`, and costs no question in the count of [ADR 0090](0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md). "More ghost notes" alone is still `ghost_level`, the soft notes the song has.
- The echo says what a creative section may add, all together, before its `expected`, which says what it added and skipped, and that asking for one kind brings the others with it in this version.
- `references/vocabulary.md` gains a `creative` row in "In words" and four answers, `creative: true` for "make it more creative", "add ghost notes" and "fill in the transitions", and `creative: false` for "no added notes, keep what's there", in its `Also` column, which [ADR 0087](0087-the-skill-s-answers-are-checked-by-a-table-with-ranges-a-test-of-it-and-an-agent-given-only-the-skill.md)'s check reads as true or false, as `skip`. `tools/check_answers.py` words each in a phrase of its own, so the table has 34 answers and 3 refinements.

**Why:** Added notes change the user's part beyond its feel, so they come only from the user's own words, and with no question they leave the budget the plan measures as it was.

**Consequences:** [ADR 0087](0087-the-skill-s-answers-are-checked-by-a-table-with-ranges-a-test-of-it-and-an-agent-given-only-the-skill.md)'s `Also` column takes `creative`. The agent pass has four more phrases to read as the vocabulary means them.
