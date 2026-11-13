# 0101. The blind test renders the owner's saved session of one song through one built-in kit, each section with notes a trial

- **Status:** Proposed
- **Date:** 2026-11-13

- `tools/make_ab.py make SESSION --kit LIBRARY[/KIT] --seed N --out FOLDER` reads a session the MCP server saved ([ADR 0079](0079-sessions-are-json-files-in-the-user-s-state-directory.md)): the one the owner made by running the skill on the test song in Claude Code and answering its questions, named by its ID, kept in the state directory, or by the path of its JSON file. It reads the song's file again, checked by its hash ([ADR 0080](0080-a-session-holds-what-a-render-needs-and-reads-its-file-again-by-its-hash.md)), and never writes the session or the song. The guided variants render the session's style, seed, controls and takes as it holds them. No answer is scripted for the test.
- The material is that one song, all of it: each section of the session's table is a trial. A section with no notes, whose five files would be the same silence, makes no trial, and the key lists it.
- Every variant is written through one kit, `--kit`, a built-in kit named as the other commands name one, `library` or `library/kit`, and checked against the built-in maps: a name that isn't one is refused. No library is named in the code ([ADR 0008](0008-library-neutral-drum-maps.md)). The song is placed in that kit with the session's answers, so a kit that leaves a request open, as a `conversion` can, writes nothing until the session answers it.
- Creative mode is off in every variant, a section the session made creative included, so each variant of a section plays the same notes ([ADR 0091](0091-creative-mode-is-a-section-s-control-off-by-default-that-lets-it-add-notes.md)). The key lists the sections it was turned off in.
- A session with a request open writes nothing, prints the requests and exits 3. A missing or invalid session, a changed file, a kit that isn't built in, or an output it won't write exits 2.

**Why:** The gate asks whether a producer's real answers beat the alternatives, so the guided variants are the owner's own session, and what it cost in questions is that session's. A whole song puts each of its kinds of section in the test, and one kit keeps the sample library the same for every variant.

**Consequences:** A song has as many trials as it has sections with notes, so a short song gives few. The session must be complete, every request answered, as `export` requires.
