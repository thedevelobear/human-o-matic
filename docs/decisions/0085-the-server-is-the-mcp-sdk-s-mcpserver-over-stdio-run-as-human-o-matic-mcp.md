# 0085. The server is the official SDK's `MCPServer` over stdio, run as `human-o-matic-mcp`

- **Status:** Accepted
- **Date:** 2026-11-12

- `mcp` 2.3.0, the official MCP Python SDK, is a runtime dependency at that exact version ([ADR 0004](0004-exact-dependency-versions.md), [ADR 0012](0012-runtime-dependencies-arrive-with-their-milestone.md)).
- `mcp_server.py`'s `Tools` holds the tools as plain methods over a `SessionStore`. `build_server` registers each with the SDK's `MCPServer`, the version 2 name of `FastMCP`, with the server's instructions, a read-only hint on `list_maps` and `get_sections`, and its reply as one text block of compact JSON, not structured output. The SDK runs each tool on a worker thread, and a lock runs them one at a time.
- `main`, the console script `human-o-matic-mcp`, serves them over stdio. It is registered with `claude mcp add human-o-matic -- uv run --directory ~/Projects/human-o-matic human-o-matic-mcp`. The SDK logs warnings and errors only, on stderr, since stdout carries the protocol.
- The tests call the methods directly, talk to the server through the SDK's in-memory client over JSON-RPC, and start the console script over stdio, with `HUMAN_O_MATIC_STATE_DIR` in `tmp_path` ([ADR 0079](0079-sessions-are-json-files-in-the-user-s-state-directory.md)).

**Why:** The plan names the official SDK. Claude Code starts a stdio server itself, with no port to open. One text block of compact JSON is what the plan asks the tools to return, and is what the CLI prints.

**Consequences:** `mcp` brings its HTTP transports' dependencies, such as `starlette` and `uvicorn`, which the lockfile pins and stdio never imports.
