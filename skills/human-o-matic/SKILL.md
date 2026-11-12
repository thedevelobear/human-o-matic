---
name: human-o-matic
description: Re-performs a drum MIDI file section by section with the human-o-matic MCP server, asking the user a few targeted questions about each section and turning the answers into controls. Use when the user wants to humanize, re-perform or add feel to programmed drum MIDI, or mentions human-o-matic.
---

# human-o-matic

human-o-matic re-performs a drum MIDI file section by section. The server reads the file, finds its sections and renders them. You ask the user about the music, turn the answers into controls, and hand the user a new MIDI file to hear. The server asks nothing itself: its replies carry facts, suggested questions and decision requests for you to put to the user.

The tools are the `human-o-matic` MCP server's, which Claude Code names `mcp__human-o-matic__<tool>`. If they are missing, the server isn't registered: tell the user it is registered once, from a shell, with the path of their human-o-matic checkout,

```sh
claude mcp add human-o-matic -- uv run --directory ~/Projects/human-o-matic human-o-matic-mcp
```

and that a new Claude Code session then has the tools. Don't run it unless the user asks you to.

## Always
- **Never pass notes.** The tools take a session ID, section IDs and file paths, and reply with counts, facts, controls and statistics. Never build, paste or ask for a list of notes.
- **Paths are absolute.** `~` is expanded.
- **Bars count from 0** in every argument and reply field, and from 1 in labels and messages, as a DAW shows them. A section's ID is its first bar from 0, its `start`. Talk to the user in labels: "bars 9 to 24".
- **Read `decisions` in every reply.** Each is an open request, its `message` the question in plain words and its `answer_with` the argument that settles it. `render` and `export` wait until every request is answered. `set_section_controls` gives its `expected` from the guesses while only hit types or grids are unconfirmed, and none while unmapped notes or conversions wait.
- **A tool error says what was wrong.** Fix the argument and call again.
- **Nothing is added.** This version never adds notes and keeps each note's hit type: soft, normal or accent. "More ghost notes" means the soft notes the song has, louder. If the user wants notes the song lacks, say this version can't add them.
- **No live preview.** The user hears a render by dragging its exported MIDI file into the DAW, onto the track whose drum instrument is the kit the session writes for.

## Question policy
1. **Confirm before asking about feel:** kit maps, section table, soft notes and ambiguous bars, as one batch.
2. **One song-wide question round,** at most three: the overall style or tightness, plus anything else that applies everywhere.
3. **Per repeat group, in song order, at most two questions.** Always accept "your call".
4. **Repeats inherit.** Ask only if a repeat probably differs, such as a bigger last chorus.
5. **Ask only when plausible answers would change the controls audibly.** Otherwise assume, and state the assumption.
6. **Echo each interpretation in plain words,** export the render for the user to hear in the DAW, and treat refinements as small changes to existing controls.
7. **Budget:** about 12 questions for a typical song. The budget is still being measured, so count the questions you ask (step 7).

## Workflow

### 1. Open the song
- You need the file's absolute path, the kit it was made for, `from_map`, and the kit that will play it, `to_map`: the drum instrument on the user's DAW track. `list_maps` gives the built-in libraries and kits: pass a kit's `map`, such as `sleep-token-ii/default`, or a library with one kit by its id. Only built-in kits exist, and no map file can be loaded. If the user hasn't said which kits, ask, naming the closest from `list_maps`.
- `open_session(midi_path, from_map, to_map)`. `to_map` left out is `from_map`.
  - A `tempo` or `drum_track` request comes back alone, and no session is kept: ask, then call `open_session` again with `bpm` or `track`, a track counted from 0.
  - Otherwise the reply holds `session_id`, a `summary` of counts, `to_kit`, the section table and the requests.

### 2. Confirm, in one batch (rule 1)
Call `get_sections` and put everything to confirm to the user in one message:
- the kits: read as `from_map`, written for `to_kit`;
- the section table: each section's label, repeat group and `plays`, such as "B: bars 9 to 24, crash riding, half-time", with repeats named as repeats;
- the soft notes and accents the `hit_types` request read, family by family, and any family whose types are a guess;
- the beats whose grid is unclear, from `ambiguous_bars`;
- notes `from_map` doesn't map (`unmapped_notes`) and notes `to_map` can't play (`conversion`), with the request's options.

Then settle what the user said:
- Fix the sections with `update_sections(session_id, ops)`: `{"op": "split", "at": bar}`, `{"op": "merge", "start": bar}`, `{"op": "move", "start": bar, "to": bar}` and `{"op": "rename", "start": bar, "name": "chorus", "group": "B"}`, applied in turn, all or none. A section keeps its controls through an edit, and a moved boundary changes the ID of the section after it, which is then drawn anew.
- Answer the requests with `set_hit_types`, each under the argument its `answer_with` names:
  - `hit_types`: every family the request lists. `{"snare": {"soft_below": 59}}` makes velocities below 59 soft, `accent_from` starts the accents, and `{}` makes every note of a family normal. To confirm what was read, put each bound between the groups the request gives, such as one above the highest soft velocity.
  - `grids`: `{"12,2": "8th_triplet"}`, bar and beat from 0, to `16th`, `8th_triplet`, `16th_triplet` or `32nd`.
  - `unmapped`: `{"99": "tom.3.hit"}`, a pitch to an articulation of `from_map`, or `"drop"`. Opening a new session with another `from_map` also settles it.
  - `substitutions`: from a source articulation to an articulation of `to_map`, or `"drop"`, from the request's options.

  Each answer replaces the one held for its key, `null` takes one back, and the reply lists the requests still open.

### 3. The song-wide round (rule 2)
At most three questions, for what holds everywhere: always what kind of drummer, tight and modern or looser, and anything else the user wants for the whole song, such as laid back throughout.
- `set_style(session_id, style, tightness)`: `style` is `tight`, the default, `medium` or `loose`, and sets how far the timing spreads. `tightness` tunes it within the style, 1 the tightest. The reply gives the style's defaults, which every control left unset takes.
- Any other control for the whole song: `set_section_controls(session_id, controls)` without `section_ids`. Each section's own controls sit over the song's.

### 4. Each repeat group, in song order (rules 3 to 5)
- Ask at most two questions per group. `get_sections` suggests them in each section's `questions`: put them in the user's terms, with what the section `plays` so they know which part it is.
- `guess` says what the score shows, `silent`, `repeat`, `fill` or `groove`, and how sure it is. It never says how hard a section plays, because that isn't readable from the notes: energy always comes from the user.
- Repeats inherit: set a group's controls on all its sections at once, with every one of their IDs in `section_ids`. Ask about a repeat only when it probably differs. The last repeat of a group asks "the same, or bigger, as the last time?", and "bigger" is a refinement of that section alone, or the vocabulary's "big last chorus" for a last chorus.
- Ask only when plausible answers would change the controls audibly. A silent section needs nothing, and a short fill one question at most. Otherwise assume, and say what you assumed.
- Turn the answer into controls with [the vocabulary](references/vocabulary.md), and call `set_section_controls(session_id, controls, section_ids, note)`, with the user's words as `note`.

### 5. Echo, export and listen (rule 6)
- After each `set_section_controls`, echo what you set in plain words, then each section's `expected`: its roles' velocities, the riders' strong hits above their weak ones, the timing spread, and how far the snare and riders sit behind. Name any control in `clamped` and the value used. For example: "Taking that as maximum energy, tight, little light and shade: kick about 121 to 127, backbeats 124 to 127, timing spread about 2.0 ms. Sound right?"
- `export(session_id, output_path)` writes the render to a new MIDI file through `to_map`, and a report, `<name>.report.json`, beside it. It never writes the input, and refuses a file that exists unless `overwrite` is true, which you set only when the user asks. Number the exports beside the input, such as `song-1.mid`, `song-2.mid`, so earlier ones stay to compare.
- Give the user the file's path: they drag it into the DAW onto the track with the `to_kit` drum instrument, and play from the bars you name. Mention what the summary's `conversion` reports, the articulations written as others, drums landing on one pitch and names read at low confidence, since that is what to listen for.
- Export after the song-wide round and after each group's answer, unless the user would rather listen once at the end. `render` gives the same statistics and words without writing a file.

### 6. Refine (rule 6)
- A refinement is a small change to the controls already set: patch only the controls the user speaks to, by about 0.1 for "a bit" and 0.2 for "a lot", from their current values. `get_sections` gives each section's own controls, and `set_section_controls` replies with `resolved`, every control as it renders.
- A control given replaces the one held, `null` unsets it, back to the song's or the style's, and one left out stays.
- Another take of some sections: `render(session_id, section_ids, take)`, kept for later exports. Another take of the whole song: `set_style(session_id, seed=n)`. The same session and seed always give the same file.
- Export again under a new number after each refinement.

### 7. Count the questions (rule 7)
Keep count as you go: one for the kits question when you need it, one for the confirmation batch, and one for each other question you ask. The echo's "sound right?" doesn't count. When the user has the file they're happy with, tell them how many questions you asked, in all and in each step, against the budget of about 12.

## Turning answers into controls
- Read [the vocabulary](references/vocabulary.md): its rows map answers to controls, each with a starting point and the range that keeps the answer's meaning. Start from the closest row, blend rows when an answer mixes them, and stay within their ranges.
- Set only the controls a row gives. The rest stay unset, so they come from the song's controls and then the style's defaults.
- Rows are written for a song whose own controls are unset. Where the song has its own value, such as its tightness, move a section from it by the row's difference from the default, and leave a control unset where the row gives the default.
- "Your call" sets nothing new: use the row for what the section is, when the user named it or confirmed it in the table, and otherwise keep the song's controls, or for a repeat, its group's. Say which.
- "Leave this alone" or "it's already done" is `skip: true`: the section stays exactly as it came in.
- For an answer no row covers, choose from the vocabulary's "In words" table and say it's your reading.
- The values are starting points that haven't been heard yet. The user's ears decide: when they say something sounds off, refine.

## Tools
| Tool | Takes | Gives |
|---|---|---|
| `list_maps` | nothing | each library and its kits, by the `map` the other tools take |
| `open_session` | `midi_path`, `from_map`, `to_map`, `instrument` (`drums`, or `generic` for dynamics and timing without drum roles), `bpm`, `track` | `session_id`, `summary`, `to_kit`, `sections`, `decisions` |
| `get_sections` | `session_id` | the song's style, seed and controls, and each section's facts, `pattern` (its most typical bar in ASCII, `X` accent, `x` normal, `o` soft), `guess`, `questions`, controls, `note` and `take` |
| `update_sections` | `session_id`, `ops` | the new section table |
| `set_hit_types` | `session_id`, `hit_types`, `grids`, `unmapped`, `substitutions` | the hit types' counts, the answers held, the requests still open |
| `set_style` | `session_id`, `style`, `seed`, `tightness` | the style, seed, defaults, the song's controls, `clamped` |
| `set_section_controls` | `session_id`, `controls`, `section_ids`, `note` | per section its controls, `resolved` and `expected`, then `clamped` and `decisions` |
| `render` | `session_id`, `section_ids`, `take` | the summary and each section's statistics and `says`, without writing |
| `export` | `session_id`, `output_path`, `overwrite` | the files written, the summary and each section's statistics and `says` |
