# human-o-matic
Re-performs programmed drum MIDI section by section, steered by your answers.

Programmed drum MIDI sounds robotic, and existing tools mostly fix that with blind randomization. Randomization can't know that one section is a full-power breakdown and another a low-energy bridge that needs groove. human-o-matic is an MCP server that re-performs a drum MIDI file section by section, steered by your answers to questions the connected agent asks. The result is a new MIDI file.

## How it works
1. The agent opens your file through the kit it was made for. The server finds its sections, its repeats, its soft notes and any bars whose grid is unclear.
2. The agent confirms the kits, the section table, the soft notes and the unclear bars with you in one message.
3. It asks once about the whole song: what kind of drummer, tight and modern or looser. Then, for each repeat group in song order, it asks at most two questions, about energy and feel. Repeats take their group's answers, and the agent asks about one only when it probably differs, such as a bigger last chorus. "Your call" is always an answer. The skill aims for about 12 questions for a typical song.
4. Each answer becomes controls. The agent echoes them in plain words with what they give, and exports a new MIDI file for you to drag into the DAW. A refinement such as "a bit more laid back" is a small change to what is already set.

For example (the words and numbers depend on the song):

```text
You:    Humanize ~/songs/song.mid. It's General MIDI, and I play it with Superior Drummer 3.
Agent:  Reading it as gm and writing for superior-drummer-3, I found 4 sections. A: bars 1 to 8,
        hats, 2 crash hits. B: bars 9 to 24, crash riding, half-time. C: bars 25 to 40, china
        riding, double kick. B repeats at bars 41 to 56. The snare has 34 soft notes, and bar 33
        could be triplets or loose 16ths. Do these look right?
You:    Yes, the soft notes are ghosts. Bar 33 is triplets.
Agent:  What kind of drummer overall: tight and modern, or looser?
You:    Tight, modern metal.
Agent:  What's the energy in bars 25 to 40 (china riding, double kick)?
You:    It's a breakdown, full power.
Agent:  Taking that as maximum energy, tight, little light and shade: kick about 121 to 127,
        backbeats 124 to 127, timing spread about 2.0 ms. It's in song-2.mid: drag it into
        the DAW and play from bar 25. Sound right?
```

## Features
- **Built-in kits.** 15 libraries with 17 kits: General MIDI and 14 drum libraries. A file made for one kit can be written for another. A note the target kit can't play falls back within its family, or the agent asks about it. Maps are built in, and no map file of your own can be loaded.
- **Styles.** `tight`, the default, `medium` and `loose`, fitted from performed drum MIDI, with the song's tightness tuned within the style.
- **Per section.** Energy, groove, dynamic range, feel from pushed to laid back, an arc that holds steady, builds or drops, fill intensity and ghost level. `skip` leaves a section exactly as it came in.
- **A performance, not noise.** Outside a skipped section, only the notes and their hit types, soft, normal or accent, are kept from the input. Velocities and timing are performed anew, never the same velocity twice in a row on one drum. Timing stays within what drummers play, and drifts rather than jitters.
- **Repeatable.** The same session and seed always give the same file. Another seed plays another take of the song, and another take of a section leaves the other sections as they were.
- **Creative mode, off by default.** It lets a section add ghost notes, cymbals where it has few, a fill into the next section where it has none, flams, rimshots and chokes, only on drums the section plays. The agent turns it on only when you ask for notes the song lacks. Otherwise no note is added.

Not in this version: a DAW bridge, a web UI or a built-in LLM. The connected agent asks the questions, so the server needs no API key. There is no live preview: you listen by dragging the exported MIDI file into the DAW. No piano or guitar yet.

## Install
Needs [uv](https://docs.astral.sh/uv/), which provides Python 3.12, and Claude Code. The commands assume the checkout is at `~/Projects/human-o-matic`.

```sh
git clone https://github.com/thedevelobear/human-o-matic.git ~/Projects/human-o-matic
cd ~/Projects/human-o-matic
uv sync
claude mcp add human-o-matic -- uv run --directory ~/Projects/human-o-matic human-o-matic-mcp
mkdir -p ~/.claude/skills
ln -s ~/Projects/human-o-matic/skills/human-o-matic ~/.claude/skills/human-o-matic
```

`claude mcp add` registers the server for the folder it is run in, unless you give it another `--scope`. The skill is a link to the checkout, never a copy, so it is always the version checked out.

## Quick start
1. Start a new Claude Code session in the folder where the server is registered.
2. Ask it to humanize a drum MIDI file, and name the kit the file was made for and the kit that will play it.
3. Answer its questions. Drag each export, `song-1.mid`, `song-2.mid` and so on beside the input, into the DAW onto the track with the kit that plays it.

Each export has a report beside it, `<name>.report.json`, with the session and each section's statistics. Sessions are JSON files in `sessions/` under the state directory: `$HUMAN_O_MATIC_STATE_DIR` when it is set, else `$XDG_STATE_HOME/human-o-matic/`, else `~/.local/state/human-o-matic/`.

## Tools
The MCP server's tools take IDs and file paths, never notes, and reply with compact JSON.

| Tool | What it does |
|---|---|
| `list_maps` | Lists the built-in libraries and their kits. |
| `open_session` | Reads a drum MIDI file through `from_map`, the kit it was made for, finds its sections, and opens a session that writes for `to_map`, the kit that will play it. |
| `get_sections` | Gives each section's bars, repeat group, facts, a typical bar in ASCII, a guess of what it is, and questions to ask. |
| `update_sections` | Splits, merges, moves or renames sections. |
| `set_hit_types` | Settles the soft notes and accents, unclear grids, unmapped notes, and notes the target kit lacks. |
| `set_style` | Sets the song's style, tightness and seed. |
| `set_section_controls` | Sets controls for some sections or the whole song, and says what they give. |
| `render` | Gives each section's statistics, without writing a file. |
| `export` | Writes a new MIDI file and its report. It never writes over the input, or over a file that exists unless asked. |

Without an agent, the `human-o-matic` CLI works from flags and JSON files. `uv run human-o-matic analyze` prints a song's summary, sections and decision requests as JSON, and `uv run human-o-matic render` writes a new MIDI file from a JSON file of controls. `--help` lists the kits.

To compare versions blind, `tools/make_ab.py` writes each section of a saved session through one kit in five variants: quantized at one velocity, naive randomization, the engine's defaults, your answers, and your answers with quantized timing. It shuffles them under neutral names into a new folder with a ratings sheet, puts the hidden key beside the folder, and counts the filled sheets:

```sh
uv run python tools/make_ab.py make SESSION --kit LIBRARY[/KIT] --seed N --out FOLDER
uv run python tools/make_ab.py score FOLDER.key.json SHEET...
```

`SESSION` is a session's ID, which each export's report holds under `session.id`, or its file.

## Development
```sh
uv run ruff check                # lint
uv run ruff format               # format
uv run pyright                   # types
uv run pytest                    # all tests
uv run pytest -m "not private"   # the tests CI runs
```

Tests marked `private` read local-only files in the gitignored `private/` folder, and skip when they are missing. The contributor guide is [`AGENTS.md`](AGENTS.md), and the design decisions are in [`docs/`](docs/README.md).
