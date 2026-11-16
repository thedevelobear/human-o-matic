# 0129. Kit remap is milestone M8, built before M5 in three PRs, with its gate after the agreed maps

- **Status:** Accepted
- **Date:** 2026-11-16

- A kit remap, which moves a drum MIDI file from one kit's note layout to another's and changes nothing else ([ADR 0130](0130-a-remap-keeps-every-note-s-tick-length-and-velocity-and-changes-only-its-pitch-and-channel.md)), is milestone M8 of the app's plan. It is built now, after M7 and before M5, which stays not started.
- It lands in three PRs, in this order, each a branch from `main` after the one before it has merged ([ADR 0003](0003-branches-off-main-merged-without-squashing.md)):
  1. `feat/kit-remap`: the engine path, the MCP tool and the skill's first question ([ADR 0132](0132-the-skill-asks-first-whether-to-remap-only-or-re-perform.md)).
  2. `feat/web-remap`: the site's Remap tab ([ADR 0131](0131-the-site-s-remap-is-a-tab-of-its-own-beside-the-re-performing-flow-with-a-short-flow-and-no-feedback.md)).
  3. `feat/maps`: each built-in kit's map as agreed with the owner, from its library's published documentation.
- M8's gate follows the third PR: every built-in kit's map is agreed, then the owner remaps a song between two kits they own, through Claude Code and on the site, and listens in the DAW.

**Why:** A remap is a feature of its own, with its own tool, tab and gate, not a fix to a merged milestone. The maps come last because their agreement is paced by the owner, and neither the engine path nor the tab depends on which notes a map holds, so the research goes to the owner while the first two PRs are built.

**Consequences:** `AGENTS.md`'s rule that milestones are done in order gets a second exception beside M7's ([ADR 0117](0117-m7-is-built-before-m5.md)). A map whose notes change can change what calibration reads from `private/midi/`, so the maps' PR runs `tools/calibrate.py fit --check`.
