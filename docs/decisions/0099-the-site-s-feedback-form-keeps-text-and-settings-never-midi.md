# 0099. The site's feedback form keeps text and settings, never MIDI

- **Status:** Proposed
- **Date:** 2026-11-13

- After a download the page offers a short form: a rating, a comment and an optional contact.
- The server stores what the user sends with the settings the render used: the kits read and written, the style, the seed, the song's bars, the number of sections and each section's controls.
- It never stores the file, its name, its hash, a note, a section's words, a session ID or the client's address. The form's body is a pydantic model that refuses unknown fields.
- Feedback is kept until the owner deletes it, in the store the site plan names.

**Why:** Feedback is why the site opens, and the settings make a comment something to act on. The MIDI is the user's work, and the settings say enough without it.

**Consequences:** A comment can't be checked against the song it was about. A comment or contact can identify a person, so the privacy notice says what is kept and how to have it deleted.
