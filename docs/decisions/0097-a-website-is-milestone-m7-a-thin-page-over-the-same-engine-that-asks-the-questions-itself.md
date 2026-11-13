# 0097. A website is milestone M7, a thin page over the same engine that asks the questions itself

- **Status:** Proposed
- **Date:** 2026-11-13

- A public website is milestone M7, planned in [`docs/plans/2026-11-13-website.md`](../plans/2026-11-13-website.md). It is built after M4's gate, whose result sets how many questions the page asks.
- It is a thin layer over the code the MCP server uses, `Tools` and the functions under it. It adds no engine, no LLM and no accounts. The same session and seed give the same bytes on the site as `human-o-matic render` and the MCP server's `export`.
- The page asks the questions itself: the skill's question policy as steps, and the vocabulary's rows as preset answers, with the controls as sliders and checkboxes. `references/vocabulary.md` stays the one source of the presets' numbers.
- Between the page and the engine pass IDs, answers and controls, never a note list ([ADR 0084](0084-the-tools-take-ids-and-paths-and-reply-with-compact-json.md)). Maps stay built in ([ADR 0010](0010-built-in-maps-only.md)), no library is special-cased ([ADR 0008](0008-library-neutral-drum-maps.md)), and the user hears the downloaded file in their DAW ([ADR 0074](0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)).
- The agents in `.claude/agents/` are build-time tools and never run on the site.
- The plan's "Do not" line and `AGENTS.md`'s rule, "No DAW bridge, web UI or built-in LLM in this version", keep the DAW bridge and the built-in LLM out and allow M7's site, and the plan's "Who asks the questions" row names the site's page beside the agent.

**Why:** Musicians without Claude Code can then try the app and say what they hear. A page that asks its own questions keeps the app free of an API bill and key, and one engine means the site plays what the CLI and the MCP server play.

**Consequences:** The question flow waits for M4's gate. The vocabulary's numbers, drafted unheard ([ADR 0089](0089-the-vocabulary-s-rows-set-only-their-controls-and-beyond-the-plan-s-four-are-drafted-unheard.md)), reach users who didn't choose them in a conversation, so the owner's refinements by ear matter more.
