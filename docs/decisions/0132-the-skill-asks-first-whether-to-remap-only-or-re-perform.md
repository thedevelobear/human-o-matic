# 0132. The skill asks first whether to remap only or re-perform

- **Status:** Proposed
- **Date:** 2026-11-16

- The skill's first question, before the kits question and before any tool call on the song, asks whether the user wants the file only moved to another kit, every note's timing and velocity kept, or re-performed. It isn't asked when the user's request already says which.
- A remap then goes: the kits, as the skill's first step asks them; the remap tool; the requests it returns, `drum_track`, `unmapped_notes` and `conversion`, put to the user with their options and each answered under the argument its `answer_with` names; then the file, with what its report says to listen for. No sections, style or questions about feel follow.
- A re-performance goes on as the skill's workflow sets it.
- The question counts as one when it is asked ([ADR 0090](0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md)).
- The skill's description names remapping, so an agent uses the skill for a request to move drums to another kit.

**Why:** Remapping and re-performing take different flows from the first tool call, so the choice comes before any. A request that already names one has answered it.
