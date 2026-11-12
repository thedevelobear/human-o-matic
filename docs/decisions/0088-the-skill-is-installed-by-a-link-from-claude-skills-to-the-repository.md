# 0088. The skill is installed by a link from `~/.claude/skills/` to `skills/human-o-matic/` in the repository

- **Status:** Proposed
- **Date:** 2026-11-12

- The skill lives in the repository, in `skills/human-o-matic/`. Claude Code finds it through a symbolic link to that folder, `~/.claude/skills/human-o-matic`, made once from the checkout's path:
  ```sh
  ln -s ~/Projects/human-o-matic/skills/human-o-matic ~/.claude/skills/human-o-matic
  ```
- It is never copied. `AGENTS.md` gives the command beside the server's `claude mcp add`.

**Why:** A link keeps one copy, so the skill a session reads is always the one checked out, and a change to it needs no second step. A user-level skill serves a session that opens a song from any folder.

**Consequences:** Switching branches switches the skill every session reads, and moving the checkout breaks the link until it is made again. `claude mcp add` registers the server for the folder it is run in unless given another `--scope`, so a session elsewhere can have the skill without the tools, and the skill says how to register them.
