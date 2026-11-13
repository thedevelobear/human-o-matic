# 0090. The skill counts its questions, the confirmation batch as one, and tells the user the count

- **Status:** Accepted
- **Date:** 2026-11-12

- The agent counts the questions it asks: one for the kits, when it has to ask which they are before opening the song, one for the confirmation batch, and one for each other question. The echo of an interpretation, with its "sound right?", doesn't count.
- When the user has a file they are happy with, the agent says how many it asked, in all and by step of the skill's workflow, against the plan's budget of about 12.

**Why:** The plan measures the budget in M4, and its gate records how many questions a real song took, so each session counts the same way. Counting the batch as one matches the budget: one batch, at most three song-wide questions and two per group make 12 for a song of four groups.

**Consequences:** The count is the agent's, so the end-to-end session and the blind test's guided variant read it from the conversation.
