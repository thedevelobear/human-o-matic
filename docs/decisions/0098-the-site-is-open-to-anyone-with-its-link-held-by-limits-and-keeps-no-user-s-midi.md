# 0098. The site is open to anyone with its link, held by limits, and keeps no user's MIDI

- **Status:** Proposed
- **Date:** 2026-11-13

- Anyone with the link can use the site: no accounts, no login and no invite code.
- Limits hold it instead: a size cap on every file the page reads and on every request the site accepts, a rate limit per client where the site's own code can apply one, a limit on the work at once of any server of the site's own, and automatic deletion. The numbers, and what a host enforces itself, are the site plan's, to confirm.
- No user's MIDI, and nothing made from it, stays on any server past the user's work. Where the engine runs in the browser, no server receives the file. Where it runs on a server of the site's own, each file made for a user has a deadline set when it is made: deleted at once on the user's request, a short grace after the last download, after an idle time and at a maximum age, by a periodic sweep and a sweep at every start, so neither an interrupted download, a closed tab nor a restart leaves one behind.
- A kill switch, or later an invite code, is a check in front of the page or a closed build of it, added without changing the engine.

**Why:** The site is for friends trying it and giving feedback, and an account would stop most of them. An open link draws abuse, which the limits bound. A user's MIDI is their work: keeping none of it is the plainest promise to make and to test.

**Consequences:** Anyone can reach the site, so the limits and the switch are the only brakes, and on a static host some of them are the host's, not the site's. With the engine on a server, deletion is code to build and test.
