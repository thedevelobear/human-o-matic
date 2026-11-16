# 0133. The remap tool takes paths, kits and every answer so far, keeps no session, and writes one file

- **Status:** Accepted
- **Date:** 2026-11-16

- The MCP server's tenth tool, beside the nine of [ADR 0084](0084-the-tools-take-ids-and-paths-and-reply-with-compact-json.md), is `remap(midi_path, from_map, to_map, output_path, track?, unmapped?, substitutions?, overwrite?)`, a method of `service.Tools` over `remap.remap` ([ADR 0130](0130-a-remap-keeps-every-note-s-tick-length-and-velocity-and-changes-only-its-pitch-and-channel.md)).
- It keeps no session. Each call reads the file again and takes every answer so far: `track` for a `drum_track` request, `unmapped`, from a pitch such as `"99"` to an articulation of `from_map`, and `substitutions`, from a source articulation to an articulation of `to_map`, either `"drop"`.
- A `drum_track` request replies `{"decisions": [request]}`. Any other open request replies `{"summary", "decisions"}` and writes nothing. Once every note is placed, it writes the file and replies `{"output", "summary", "decisions": []}`.
- The summary holds `file`, `output`, `kit`, `to_kit`, `ppq`, `track`, and the drum track's `notes`, `written`, `dropped` and `waiting`, `outside_range`, the notes per target articulation whose kept velocity is outside its binding's range, and `conversion`, the report a render gives ([ADR 0075](0075-render-s-summary-counts-how-the-notes-were-placed-in-the-target-kit.md)), with collisions at the notes' own ticks. It holds no note list.
- `output_path` is checked as `export` checks it: absolute, ending `.mid` or `.midi`, in a folder that exists, never the input by its path or as the same file, and refused when it exists unless `overwrite` is set. The file is written aside first and only then takes its name. No report file is written beside it.
- The site's worker leaves it out until the Remap tab ([ADR 0131](0131-the-site-s-remap-is-a-tab-of-its-own-beside-the-re-performing-flow-with-a-short-flow-and-no-feedback.md)).

**Why:** A remap is one step, and the answers are all it carries between calls, so a session would only be a file to keep. Its reply holds everything a report beside the file would.

**Consequences:** The agent passes every answer again on each call.
