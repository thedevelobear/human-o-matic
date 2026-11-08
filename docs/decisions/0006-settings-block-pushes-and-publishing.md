# 0006. Claude Code's settings block pushes and publishing

- **Status:** Accepted
- **Date:** 2026-11-08

- `.claude/settings.json` denies `git push`, `git -C <path> push` and `uv publish`, each with and without arguments. Deny rules apply to the orchestrator and to every subagent.
- The owner pushes branches, and publishes the package if it is ever published, outside Claude Code.

**Why:** The repo is public, so whatever is pushed is public, including anything that doesn't belong there, such as library data ([ADR 0007](0007-library-data-stays-out-of-the-repo.md)). A push or a published version can't be taken back, and an instruction in an agent's file can be missed, while Claude Code enforces the settings whatever the agent intends.

**Consequences:** The rules match the written forms of the commands. A git alias, a script that pushes, or `gh` called to push the branch still runs, so a `PreToolUse` hook that reads whole commands should be added if that becomes a worry. No one can push from Claude Code in this repo.
