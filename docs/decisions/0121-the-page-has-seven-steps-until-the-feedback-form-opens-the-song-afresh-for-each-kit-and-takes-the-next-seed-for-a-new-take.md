# 0121. The page has seven steps until the feedback form, opens the song afresh for each kit, and takes the next seed for a new take

- **Status:** Accepted
- **Date:** 2026-11-15

- **Steps:** the top bar lists 1 File to 7 Download, and the eighth, Feedback, joins with its form in `feat/web-feedback`. A step reached can be opened again from the top bar. Opening the song again makes Check the furthest step reached.
- **Kits:** "Open the song" calls `reset`, then `open_session` with the file's bytes, so the worker holds one session. "Which drum instrument will play it?" follows "Where did this MIDI come from?" until it is changed. A kit says "mapping not yet checked" when more than half its articulations are of low confidence.
- **Check** lists the section table, whose edits are in Sections. Its forms start at what the engine found: "soft below" one above the soft notes' highest velocity, "accent from" at the accents' lowest, empty where a family has no such group, each unclear beat at its guess, offering its alternatives, a conversion at its first option, and an unmapped pitch at no choice, which must be made. Confirm sends them in one call, `open_session` again with a tempo or a track, or else one `set_hit_types`, and shows any request still open.
- **Takes:** "a new take of the song" sets the seed one higher with `set_style`, and "another take" of a section renders it with its take one higher.
- **A download** is a Blob URL, revoked 10 seconds after the download starts, or at once by "Delete my file now".
- **"Delete my file now"** is also how to start over: shown once a file is chosen, it ends the worker, drops the file's bytes from the page and starts a new worker, whose engine loads again.
- **A dropped file** whose name doesn't end `.mid` or `.midi` is refused before it is read.

**Why:** A step the page can't take yet stays out of its bar. One session in the worker keeps nothing of an earlier opening. Forms that start at what the engine found let Confirm accept it as found. The next seed is a new take that the same session gives again. A Blob URL holds the file in the page's memory until it is revoked, and 10 seconds covers a download's start.

**Consequences:** The page can't go back to an earlier take of the song, since the seed only climbs, and an earlier download keeps it.
