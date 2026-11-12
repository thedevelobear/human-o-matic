# 0079. Sessions are JSON files in the user's state directory, one per session ID

- **Status:** Proposed
- **Date:** 2026-11-12

- Each session is one JSON file, `<session ID>.json`, in `sessions/` under the app's state directory: `$XDG_STATE_HOME/human-o-matic/`, or `~/.local/state/human-o-matic/` when `XDG_STATE_HOME` is unset, empty or not an absolute path, on every platform.
- `HUMAN_O_MATIC_STATE_DIR`, when set and not empty, is the app's state directory instead. The code that reads and writes sessions also takes the sessions directory as an argument, so tests keep their sessions in `tmp_path` and never touch the real one.
- The directory is made on first use. It is never inside the repository or `private/`.

**Why:** A session outlives the server process, which the agent can restart at any time, so it is kept on disk. It holds the user's file paths and answers, which belong with the user's own state, not in the public repository, and `private/` holds the local files the project is calibrated on, not a user's work. One file per session can be read, copied or deleted on its own.

**Consequences:** Nothing deletes old sessions in this version.
