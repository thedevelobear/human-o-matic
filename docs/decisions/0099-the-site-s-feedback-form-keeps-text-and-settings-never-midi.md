# 0099. The site's feedback form keeps text and settings, never MIDI

- **Status:** Proposed
- **Date:** 2026-11-13

- After a download the page offers a short form: a rating, a comment and an optional contact.
- The page sends what the user wrote with the settings the render used, and nothing else: the kits read and written, the style, the seed, the song's bars, the number of sections and each section's controls.
- No code of the site's sends or stores the file, its name, its hash, a note, a section's words or a session ID, and none stores the client's address. A server of the site's own reads the form into a pydantic model that refuses unknown fields. Where the store is a host's form service that records the sender's address itself, the privacy notice says so.
- Feedback is kept until the owner deletes it, in the store the site plan names.

**Why:** Feedback is why the site opens, and the settings make a comment something to act on. The MIDI is the user's work, and the settings say enough without it.

**Consequences:** A comment can't be checked against the song it was about. A comment or contact can identify a person, so the privacy notice says what is kept, by whom, and how to have it deleted. A host's form service is a third party that holds the feedback.
