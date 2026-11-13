# human-o-matic: guided MIDI drum performance

> **Status:** Active. M0 to M3 are merged, M3 after the owner listened to rendered files on their own kit and passed its gate. M4 is under way, in three PRs: the first, `feat/mcp`, the sessions, the facts and the MCP server, and the second, `feat/skill`, the skill, are merged, and the third, `feat/blind-test`, follows. The owner confirmed M6's priority, and it was built ahead of M4's third PR, as `feat/creative-mode`, which is merged: a section's `creative` control, off by default, lets it add notes. M7, a website, is planned in [its own plan](2026-11-13-website.md), to be built after M4's gate.
> A living document. Each PR updates the progress table and the sections its work changes. Decisions are in [`../decisions/`](../decisions/).
> Last updated: 2026-11-13 (`feat/creative-mode` merged, and ADRs 0091 to 0096 accepted; M7, the website, planned, proposing ADR 0097, the site as a thin page over the same engine, ADR 0098, open with limits and keeping no user's MIDI, ADR 0099, feedback without MIDI, and ADR 0100, the engine in the browser).

Handoff document for an implementing agent with no prior context. The app is called **human-o-matic**: use `human-o-matic` for the repo, distribution, CLI and skill, and `human_o_matic` for the Python package.

## Progress

Milestones are done in order, and work stops at each gate ([`AGENTS.md`](../../AGENTS.md)).

| # | Milestone | Gate | Status |
|---|---|---|---|
| M0 | Setup | The checks pass on the scaffolding | Merged ([#1](https://github.com/thedevelobear/human-o-matic/pull/1)) |
| M1 | Normalize | The M1 exit tests | Merged ([#2](https://github.com/thedevelobear/human-o-matic/pull/2)) |
| M2 | Sections | Boundary F1 of at least 0.70 on at least 10 tracks the owner has hand-labelled | Merged ([#3](https://github.com/thedevelobear/human-o-matic/pull/3)) |
| M3 | Parametric engine and calibration | Each control moves its statistic the right way, and the property tests pass | Merged: the engine ([#4](https://github.com/thedevelobear/human-o-matic/pull/4)) and calibration ([#5](https://github.com/thedevelobear/human-o-matic/pull/5)), with the three styles in `data/styles/`, which the engine reads, the research cross-check, and the guards' gap counted in milliseconds and held for notes sharing a grid point; no preview PR ([#6](https://github.com/thedevelobear/human-o-matic/pull/6), [ADR 0074](../decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)); riders draw a velocity noise of their own, and hold their strong hits under 127 by a spread of it ([#7](https://github.com/thedevelobear/human-o-matic/pull/7), [ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md), [ADR 0077](../decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md)); the exit's tests pass on the three styles, and the owner passed the gate after listening |
| M4 | MCP, skill and the main gate | The blind listening test, judged by the owner | In progress: PR 1 of 3, `feat/mcp`, merged ([#8](https://github.com/thedevelobear/human-o-matic/pull/8)): the sessions, the facts and the nine MCP tools over stdio, `mcp` 2.3.0 added ([ADR 0078](../decisions/0078-m4-is-three-prs-and-its-gate-follows-the-third.md) to [ADR 0085](../decisions/0085-the-server-is-the-mcp-sdk-s-mcpserver-over-stdio-run-as-human-o-matic-mcp.md)), and a fix to M1's quantizer, a note belonging to the beat its tick is in, with the styles fitted again on it ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)); PR 2 of 3, `feat/skill`, merged ([#9](https://github.com/thedevelobear/human-o-matic/pull/9)): `SKILL.md`, the vocabulary of 30 answers and 3 refinements with ranges, its test, and `tools/check_answers.py` for the agent pass ([ADR 0087](../decisions/0087-the-skill-s-answers-are-checked-by-a-table-with-ranges-a-test-of-it-and-an-agent-given-only-the-skill.md) to [ADR 0090](../decisions/0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md)), with the agent pass to run; `feat/blind-test` to follow |
| M5 | Trained model experiment | Follows the controls and wins a blind test, judged by the owner | Not started. Not before M4 |
| M6 | Added notes | The owner confirms the priority first, then listens to creative sections on their kit | Merged ([#10](https://github.com/thedevelobear/human-o-matic/pull/10)): `feat/creative-mode`, a section's `creative` control, off by default, which adds ghost notes, cymbals where a section has few, a fill into the next section where it has none, flams, rimshots and chokes, on drums and pitches the section plays, changing no other section, counted in the reports, and set by the skill only when the user asks ([ADR 0091](../decisions/0091-creative-mode-is-a-section-s-control-off-by-default-that-lets-it-add-notes.md) to [ADR 0096](../decisions/0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md)) |
| M7 | Website | The owner checks the site end to end on their own machine, then with friends | Planned, after M4's gate, in [the website plan](2026-11-13-website.md) ([ADR 0097](../decisions/0097-a-website-is-milestone-m7-a-thin-page-over-the-same-engine-that-asks-the-questions-itself.md)). M7 may be built before M5, which is an experiment that may be archived; the owner confirms whether it is |

**Follow-up fixes.** Fixes to a merged milestone land on `fix/topic` branches, with no number, and are listed here.

| Branch | Contents | Status |
|---|---|---|
| `fix/rider-noise` | Riders draw their velocities with a noise of their own, Appendix A's 2.5, where the other roles keep their fitted noise, 5.12 then and 5.03 since the styles were fitted again ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)), so a ride's strong and weak hits alternate more clearly ([ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)), and a rider's strong hits held under 127 by a spread of their noise with the weak ones the gap below, so the alternation holds at full energy ([ADR 0077](../decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md)) | Merged ([#7](https://github.com/thedevelobear/human-o-matic/pull/7)) |

## Context

Programmed drum MIDI sounds robotic, and existing tools mostly fix that with blind randomization. Randomization cannot know that one section is a full-power breakdown and another a low-energy bridge that needs groove.

**Product:** an MCP server that re-performs a drum MIDI file section by section. An agent such as Claude Code loads the file, the server divides it into sections, the agent asks the user about each one ("what's the energy here?"), and the user's answers steer the render. Answers like "it's a breakdown, full power" or "it's a bridge, low energy and high groove" become numeric controls. The result is a new MIDI file. Drums first; the design must allow piano, guitar and others later.

**Scope:** a normal, public app, built in this repo. Local-only files stay in a gitignored `private/` folder, and nothing in it is committed or redistributed ([ADR 0007](../decisions/0007-local-only-files-live-in-private.md)).

## Decisions already made

| Question | Decision |
|---|---|
| Language | Python 3.12+ (see below) |
| Interaction | Guided by questions, per section. Running with all defaults must still work, but it is not the main path |
| Who asks the questions | The connected agent, through MCP, or, on M7's website, the page itself, from the question policy and the vocabulary ([ADR 0097](../decisions/0097-a-website-is-milestone-m7-a-thin-page-over-the-same-engine-that-asks-the-questions-itself.md)). No built-in LLM, so the app has no API bill or API key |
| Existing humanization | Rebuild from scratch: all timing is re-quantized and all velocity numbers are discarded |
| What survives from the input | The notes and each note's **hit type only**: soft, normal or accent, confirmed with the user. If the input has one flat velocity, infer hit types and ask |
| Adding notes | Version 1 never adds notes, unless a section turns creative mode on, which the user asks for: then it may add ghosts, cymbals, a fill, flams, rimshots and chokes ([ADR 0091](../decisions/0091-creative-mode-is-a-section-s-control-off-by-default-that-lets-it-add-notes.md)) |
| Loudness | At high energy: kick and backbeats about 118 to 127. At every energy level: never the same velocity twice in a row on one drum |
| Performance engine | Parametric engine calibrated from performed drum MIDI first. A trained model is a separate experiment, adopted only if it wins a blind listening test |
| Model data | Performed drum MIDI only, kept in `private/` |
| Drum libraries | Most modern drum libraries, through library-neutral maps: library, kit and articulation, with canonical articulation names as the pivot. No library is special in the code ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)) |
| Map files | Built in only in this version, with no user-supplied maps ([ADR 0010](../decisions/0010-built-in-maps-only.md)) |

### Why Python

| Language | Fit |
|---|---|
| **Python: chosen** | Everything this needs is native: an official MCP SDK, PyTorch for the model experiment, numpy/scipy for section analysis, mature MIDI libraries. Training and inference share one language, and musical rules are fast to iterate. The only distribution cost, needing a Python environment, is handled by `uv` |
| Rust | Its main advantages are a single binary and plugin builds, and neither is needed. The cost would be splitting the project in two, since training stays in Python anyway. Reconsider only if this becomes a VST/CLAP plugin |
| TypeScript | Good for an interface, but this version has none, and it is weak for ML training |

Tooling: `uv`, `ruff`, `pyright`, `pytest`, `hypothesis`.

## Does this make sense? Yes

**Guided beats black box, and measurements of performed drum MIDI support it.**
- **Energy is not readable from note density.** Within a song, one drummer's snare level varies by a standard deviation of 8 to 20 velocity between grooves, yet its correlation with note density is only -0.06 to +0.30. Only density was tested, so another score feature might predict it, but asking the user is a direct way to get this information.
- **Dynamics are what change per section; timing mostly is not.** Within a song, timing spread moves by only 0.3 to 3.1 ms between grooves, while between drummers it runs from 3 to 12 ms. So set the style and tightness once per song, and steer dynamics per section.
- **The engine can work some things out itself.** Denser kick playing is often softer (r down to -0.76), so that needs no question.

**Perception research says to be careful with timing.** Listeners [rate original-performance microtiming and fully quantized timing about equally](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5050221/), and exaggerated microtiming scores lower. On a rock pattern, [the accurate version rated best, early shifts were worse than late ones, and snare deviations were worse than kick deviations](https://journals.sagepub.com/doi/abs/10.1177/1029864913486793). So timing stays within performed magnitudes, leans late rather than early, and has to prove its value in the listening test. In contrast, [listeners prefer long-range correlated deviations over uncorrelated noise](https://news.harvard.edu/gazette/story/2012/07/when-the-beat-goes-off), so timing should drift, not jitter. [Drummers asked to play laid-back generally also played louder](https://www.researchgate.net/publication/282186017_Effects_of_instructed_timing_and_tempo_on_snare_drum_sound_in_drum_kit_performance), so timing feel and intensity should be linked.

**Precedents support the architecture, but not for this exact job.**
- [MuseCoco](https://arxiv.org/pdf/2306.00110) splits text-to-music into text-to-attributes and attributes-to-music. Attributes can be computed from music, so the second stage can train self-supervised. This project uses the same bridge, with the agent doing the first stage.
- [FIGARO](https://arxiv.org/pdf/2201.10936) uses human-editable bar-level descriptions, [Composer's Assistant 2](https://arxiv.org/html/2407.14700v1) offers fine-grained controls locally inside a DAW, and [ScorePerformer](https://github.com/ilya16/ScorePerformer) and [DExter](https://arxiv.org/pdf/2406.14850) render performances with fine-grained or perceptual control, on piano.
- [Logic's Session Players](https://support.apple.com/guide/logicpro-ipad/lpip6efdfca1/ipados) set intensity and complexity per region, with separate fill controls, and can copy settings between regions.
- [Cococo](https://youralien.github.io/files/cococo_chi2020_copy.pdf) found that semantic controls and working in smaller chunks improved users' sense of control and reduced overload.
- I did not find a drum humanizer that interviews the user per section. That is a gap, but also means there is no proven recipe.

**Effort** (estimates, in focused agent sessions): M0 under 1, M1 1 to 2, M2 1 to 2, M3 about 2, M4 1 to 2 plus listening time, M5 2 to 4 plus training time, M6 1 to 2.

### Main risks
1. **Questions may not improve the sound enough to justify the friction.** M4 tests this directly before any further investment.
2. **Subjective language:** "full power" has no objective number. Mitigate with a vocabulary reference, a plain-language echo of each interpretation, and audition before moving on.
3. **Question fatigue:** research on when agents should ask finds [targeted questions as ambiguity arises do better than broad ones, with fewer questions overall](https://www.alphaxiv.org/abs/2603.26233), and [models tend to assume rather than ask](https://aitopics.org/doc/arxivorg:B54044BF). Most of this work is preprints, and no firm limit on tolerable questions was found, so use an explicit policy and measure it.
4. **Section detection errors:** the agent reviews sections with the user first, so errors are cheap to fix.

## Product flow

```
Agent: opens song.mid (from iof-drummer to sleep-token-ii)
Agent: I found 6 sections. A: bars 1-8, sparse crashes. B: bars 9-24, crash riding, half-time.
       C: bars 25-40, china and busy kick. B repeats at 41-56, then D: bars 57-64, toms and hats.
       I also found 34 soft snare notes and 2 bars that could be triplets or loose 16ths. Do these look right?
User:  Yes, the soft notes are ghosts. Bar 33 is triplets.
Agent: What kind of drummer overall, tight and modern or looser?
User:  Tight, modern metal.
Agent: Section C, china and busy kick: what's the energy?
User:  It's a breakdown, full power.
Agent: Taking that as maximum energy, tight, little light and shade. Sound right? It's in song-2.mid: drag it into the DAW and play from bar 25.
User:  Good. Hats in D should feel relaxed.
Agent: D is low energy, high groove, slightly laid back, with soft notes more present. Same for bar 57 onward?
```

Questions come from the agent, not the server. The server provides facts, suggestions and validation, so any MCP agent can run it. Elicitation is deliberately not required: it is [restricted to flat forms and its draft is still changing](https://modelcontextprotocol.io/specification/draft/client/elicitation), and agents already have their own ways to ask.

## Architecture

```
~/Projects/human-o-matic/             the app's git repo; only the owner pushes
  pyproject.toml
  src/human_o_matic/
    decisions.py          DecisionRequest: what the pipeline asks instead of guessing
    resources.py          data_dir(): where the built-in data is
    midi/io.py            lossless read/write (mido): notes and raw events at absolute ticks, written at 960 PPQ or more
    midi/tempo.py         tick, beat and ms conversions; tempo and time signature maps
    midi/tracks.py        track summaries and the drum track choice
    maps/vocabulary.py    canonical names: their grammar, parsed against data/vocabulary.toml
    maps/schema.py        map file models: library, kit, articulation, bindings
    maps/kit.py           a kit checked against the vocabulary, read and written
    maps/loader.py        the built-in vocabulary and maps, validated as they load
    maps/convert.py       conversion between kits with fallbacks, its report and decision requests
    normalize/read.py     the drum track through a kit into canonical hits, and the unmapped notes
    normalize/grid.py     each beat's grid and its points, and the ambiguous bars
    normalize/quantize.py graces, limbs on one grid point, and each hit's tick and offset
    normalize/hit_types.py soft, normal and accent from each family's velocities
    normalize/score.py    the score: canonical hits on a grid, with hit types and source notes
    normalize/pipeline.py normalize(): the steps in turn, and their decision requests
    analyze/sections.py   bar patterns, similarity matrix, novelty peaks, silences, markers, repeat groups
    analyze/scoring.py    boundaries matched one to one within a bar, and their F1
    analyze/labels.py     hand-label files, and the detector measured on them
    analyze/facts.py      each section's facts, its most typical bar in ASCII, a modest guess and questions
    controls.py           pydantic ControlVector, Controls, SectionPlan, SessionPlan
    render/parts.py       each note's role and limb, and the play order
    render/style.py       styles: tight, medium and loose from data/styles/, and the placeholder the fit keeps values from
    render/compiler.py    controls + style into per-role parameters
    render/engine.py      seeded streams, the song's drifts, render()
    render/creative.py    creative mode: what a section adds, admitted where it changes no other section, and its report
    render/guards.py      limits that apply to every backend
    render/target.py      each note's pitch, channel and velocity range in the target kit
    render/controllers.py the windows that keep a controller-bound note's value
    render/output.py      the rendered notes back into the drum track
    render/measure.py     each section's statistics
    render/describe.py    how a section came out, by role, in numbers and plain words
    render/backends/      parametric.py; neural.py in M5 only
    instruments/          base protocol, drums.py, additions.py (what a creative drum section adds), generic.py
    session.py            session JSON on disk: sections, answers, controls, seed, takes, exports
    files.py              files written whole: aside first, then named, linked or created exclusively
    mcp_server.py         thin MCP layer over the above: the tools, served over stdio
    cli.py                analyze: a song's summary, sections and decision requests as JSON; render: a new MIDI file by a plan
  skills/human-o-matic/SKILL.md       question policy and workflow, linked from ~/.claude/skills/ (ADR 0088)
  skills/human-o-matic/references/vocabulary.md   answers to controls, each with its range
  data/vocabulary.toml                the canonical articulation vocabulary
  data/maps/*.toml                    built-in maps, one library per file: its kits and their articulations
  data/styles/*.toml                  tight, medium and loose, generated by calibration
  tools/                              infer_map and midi_folders, calibrate and fit_styles, check_answers, make_ab, train: scripts, checked like src (ADR 0058)
  private/                            gitignored: local-only files, the tools that build maps from them, and which kit reads each folder of performed MIDI (ADR 0057), never committed (ADR 0007)
  typings/mido/                       local type stubs for the part of mido the code uses
  tests/
```

**Pipeline:** read, map, normalize to a flat quantized score with hit types, detect sections, collect controls, compile, sample, guards, write.

**Render determinism:** derive one random stream per section with `numpy.random.SeedSequence`, so re-rendering section 5 leaves sections 1 to 4 byte-identical. Long-memory drift is generated once for the whole song and only changes with the song seed. The same session JSON and seed always produce the same file ([ADR 0049](../decisions/0049-each-section-draws-from-its-own-seeded-stream.md)).

**Instrument seam:** `Instrument` provides normalization rules, hit typing, facts, a control schema and a compiler. `drums` is the only real implementation. A small `generic` mode (dynamics and timing without roles) proves the seam works. Piano and guitar need their own analysis, so do not design for them further yet. As built, the seam has only what the engine calls, each note's part and the compiler, and the rest joins it when something calls it ([ADR 0045](../decisions/0045-the-engine-is-render-modules-behind-a-small-instrument-seam.md)).

### MCP tools

Tools take IDs and file paths and return compact JSON. **Never pass note arrays:** a thousand notes through tool calls would make the model read and rewrite them all, slowly and with errors.

| Tool | Purpose |
|---|---|
| `list_maps` | The built-in libraries and their kits |
| `open_session(midi_path, from_map, to_map?, instrument?, bpm?, track?)` | Normalize and detect sections. `from_map` and `to_map` name a built-in library and kit, never a map file ([ADR 0010](../decisions/0010-built-in-maps-only.md)). Returns a session ID, summary, and anything needing a decision |
| `get_sections(session_id)` | Bars, repeat group, facts, ASCII pattern, plus suggested questions and a guess with confidence |
| `update_sections(session_id, ops)` | Split, merge, move boundaries, rename |
| `set_hit_types(session_id, hit_types?, grids?, unmapped?, substitutions?)` | Confirm soft notes and resolve ambiguous bars, and place unmapped notes and notes `to_map` lacks, each under the name its request's `answer_with` gives |
| `set_style(session_id, style?, seed?, tightness?)` | Song-wide style, `tight`, `medium` or `loose` ([ADR 0044](../decisions/0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)), and tightness |
| `set_section_controls(session_id, controls, section_ids?, note?)` | Validate and store, for the sections given or the whole song. Returns plain-language expected results, such as "snare about 118 to 127, timing spread about 3 ms", and any clamping |
| `render(session_id, section_ids?, take?)` | Sample, returning measured stats per section |
| `export(session_id, output_path, overwrite?)` | Write MIDI and a report. Never overwrite the input; refuse existing files unless `overwrite` is set |

**Listening:** the sample library determines how velocities sound, so the user listens on their own kit: a render is written to a new MIDI file through the kit `to_map` names, and the user drags it into the DAW, onto a track with that drum instrument. There is no live preview through a MIDI port, and no `preview` tool ([ADR 0074](../decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)).

**As built:**
- The tools are plain methods of `mcp_server.Tools` over a `SessionStore`, registered with the official SDK's `MCPServer` and served over stdio by the console script `human-o-matic-mcp`, one call at a time ([ADR 0085](../decisions/0085-the-server-is-the-mcp-sdk-s-mcpserver-over-stdio-run-as-human-o-matic-mcp.md)). Each reply is one compact JSON object, with open requests as `decisions`, and an argument a tool can't use is a tool error saying why. `bpm` and `track` are answered by opening the session again, and every other request by `set_hit_types`. A control past its range is clamped and listed in `clamped`, and `export` writes a report, `<name>.report.json`, beside the MIDI file ([ADR 0084](../decisions/0084-the-tools-take-ids-and-paths-and-reply-with-compact-json.md)).
- A session holds the file's path and hash, the kits, the answers, the style, the seed, 0 until set, the controls as merge patches, and the sections with their controls, words and takes, but no note: each tool reads the file again, and a changed file is an error. A section's ID is its first bar, from 0 ([ADR 0080](../decisions/0080-a-session-holds-what-a-render-needs-and-reads-its-file-again-by-its-hash.md)). The sections are found when the session opens, and change only by `update_sections`, all or none ([ADR 0081](../decisions/0081-sections-are-edited-by-split-merge-move-and-rename-all-or-none.md)).
- `get_sections` gives each section's facts, counted from the score and the drums' parts, its most typical bar as ASCII, and a guess, `silent`, `repeat`, `fill` or `groove`, with how sure it is, never of how hard it plays, and questions after the question policy ([ADR 0082](../decisions/0082-a-section-s-facts-are-counted-and-its-guess-says-only-what-the-score-shows.md)).
- `set_section_controls`'s expected results are the section rendered in memory with the stored controls, seed and takes, each role's velocities from the 5th to the 95th percentile, the riders' gap, the timing spread and how far snare and riders sit behind, in words, which `render` and `export` give too ([ADR 0083](../decisions/0083-expected-results-are-the-section-rendered-and-measured-by-role.md)).
- A creative section's `expected` and `says` end with what it added and skipped and why, and `render` and `export` count the notes added in the summary's `notes.added`, the creative sections' report in its `creative`, and each section's own in its row ([ADR 0095](../decisions/0095-an-addition-the-kit-can-t-play-is-skipped-and-the-reports-count-what-was-added.md)).

### Control vector

Per section, all optional, with defaults supplied by the song style:

| Control | Range | Mainly drives |
|---|---|---|
| `energy` | 0 to 1 | Velocity centers and floors, accent strength |
| `groove` | 0 to 1 | Accent contrast, soft note presence, hat and ride shape |
| `dynamic_range` | 0 to 1 | Spread within a drum, strong versus weak hits |
| `tightness` | 0 to 1 | Timing spread (usually set once per song) |
| `feel` | -1 pushed to +1 laid back | Mean offset of snare and riders, with loudness coupled when laid back. How far each side goes is the style's ([ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)) |
| `arc` | `steady`, `build`, `drop` | Energy shape across the section |
| `fill_intensity` | 0 to 1 | Fill velocity and crescendo |
| `ghost_level` | 0 to 1 | Velocity of notes typed soft |
| `skip` | boolean | Leave this section exactly as it came in, for parts the user already finished |
| `creative` | boolean | Let this section add notes, only when the user asks: ghosts, cymbals where it has few, a fill into the next section where it has none, flams, rimshots and chokes. Off by default, and `skip` wins ([ADR 0091](../decisions/0091-creative-mode-is-a-section-s-control-off-by-default-that-lets-it-add-notes.md)) |

**Examples for `vocabulary.md`** (starting points to refine by ear)

| Answer | energy | groove | dynamic_range | tightness | feel | ghost_level |
|---|---:|---:|---:|---:|---:|---:|
| "breakdown, full power" | 0.95 | 0.2 | 0.2 | 0.8 | 0 | 0.2 |
| "bridge, low energy, high groove" | 0.35 | 0.85 | 0.7 | 0.6 | +0.2 | 0.7 |
| "big last chorus" | 0.9 | 0.5 | 0.4 | 0.75 | 0 | 0.3 |
| "verse, holding back, building" | 0.5, `arc: build` | 0.6 | 0.5 | 0.75 | +0.1 | 0.5 |

### Question policy (in `SKILL.md`)
1. **Confirm before asking about feel:** kit maps, section table, soft notes and ambiguous bars, as one batch.
2. **One song-wide question round,** at most three: the overall style or tightness, plus anything else that applies everywhere.
3. **Per repeat group, in song order, at most two questions.** Always accept "your call".
4. **Repeats inherit.** Ask only if a repeat probably differs, such as a bigger last chorus.
5. **Ask only when plausible answers would change the controls audibly.** Otherwise assume, and state the assumption.
6. **Echo each interpretation in plain words,** export the render for the user to hear in the DAW, and treat refinements as small changes to existing controls.
7. **Budget:** about 12 questions for a typical song, measured in M4.

As built, the skill counts the kits question when it has to ask it, the confirmation batch as one and every other question as one, but not the echo's "sound right?", and tells the user the count at the end ([ADR 0090](../decisions/0090-the-skill-counts-its-questions-the-confirmation-batch-as-one.md)).

Creative mode is never asked about: the skill sets it only when the user asks for notes the song lacks, and that costs no question ([ADR 0096](../decisions/0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md)).

## Milestones

Stop at each gate. Listening decisions belong to the owner, because no agent can hear the output.

### M0 Setup
- Machine has Python 3.10.3 with no numpy or torch; M1 Pro, 32 GB. `uv` 0.13.7 is installed in `~/.local/bin`, and provides Python 3.12.
- `~/Projects/human-o-matic` is the app's repo, with a GitHub remote, `origin`. Only the owner pushes ([ADR 0006](../decisions/0006-settings-block-pushes-and-publishing.md)).
- The scaffolding is the toolchain ([ADR 0001](../decisions/0001-python-312-with-uv-ruff-pyright-and-pytest.md)), the docs, the orchestrator, developer and qa agents ([ADR 0005](../decisions/0005-orchestrated-agents.md)) and CI. Local-only files stay in the gitignored `private/` ([ADR 0007](../decisions/0007-local-only-files-live-in-private.md)).

### M1 Normalize
- Build MIDI I/O, tempo handling, maps and normalization, plus `human-o-matic analyze`.
- **MIDI requirements:**
  - Exports may have **no tempo events and 96 PPQ**. With no tempo in the file and none given, return a clear decision request, never a silent 120 BPM.
  - At 96 PPQ and 129 BPM one tick is 4.8 ms, so always write at least 960 PPQ.
  - Do not detect drums by channel 10. Choose the only track, or a track named like `drum`, or channel 9; otherwise list tracks and ask.
  - Handle dense tempo maps (thousands of events), time signature changes, duplicate time signature events, format 0 and 1.
  - Preserve CCs, RPNs, pitch bend, meta events and other tracks.
  - SMF has no mute flag. Unmapped notes are a decision request listing pitch, count and position, so an incomplete map can never silently lose real hits.
- **MIDI, as built:**
  - A file becomes paired notes and raw events at absolute ticks, and a round trip keeps every message in order ([ADR 0013](../decisions/0013-midi-is-read-into-notes-and-raw-events.md)). Songs are worked on and written at the smallest multiple of the source PPQ that is at least 960 ([ADR 0014](../decisions/0014-work-at-a-whole-multiple-of-the-source-ppq.md)).
  - Unclear input is a `DecisionRequest`, raised as `DecisionRequired` ([ADR 0015](../decisions/0015-unclear-input-is-a-decision-request.md)). Tempo and time signatures follow [ADR 0016](../decisions/0016-tempo-and-time-signatures.md): a given `bpm` replaces the file's tempo, and a missing time signature is 4/4, flagged as assumed. `bpm` is the only tempo a user gives, from 3.577 to 60,000,000 BPM, a range of tempos a MIDI tempo event can hold, and there is no `tempo_map` argument ([ADR 0032](../decisions/0032-bpm-is-the-only-tempo-a-user-gives.md)). The drums are one whole track ([ADR 0017](../decisions/0017-the-drums-are-one-whole-track.md)). mido is typed by a local stub ([ADR 0018](../decisions/0018-mido-is-typed-by-a-local-stub.md)).
  - Performed MIDI in `private/midi/` round-trips with every message unchanged apart from note-ons at velocity 0, written as note-offs, which a `private` test checks on a sample. Dense tempo maps are tested on files built in code.
- **Quantizer:** choose a grid per beat among 16th, 8th triplet, 16th triplet and 32nd, with a penalty for complex grids. Treat hits on one drum under about 45 ms apart as grace plus main, and keep them linked. Merge near-simultaneous limbs onto one grid point. Report ambiguous bars instead of guessing silently.
- **Hit types:** cluster velocities per drum family. Clear clusters become soft, normal or accent. Flat input gets inferred types marked low confidence, so the agent asks.
- **Normalize, as built:**
  - `normalize()` reads the drum track through a built-in kit into a frozen score of canonical hits, each with its source note, quantized tick, offset in milliseconds, beat and grid, grace link and hit type ([ADR 0031](../decisions/0031-the-score-is-frozen-canonical-hits-with-their-source-notes.md)). Unmapped notes wait outside the score for an `unmapped_notes` request, and notes read through low-confidence names are counted.
  - Each beat takes the 16th, 8th triplet, 16th triplet or 32nd with the least timing error in milliseconds plus a penalty of 0, 6, 10 and 10 ms ([ADR 0026](../decisions/0026-a-grid-per-beat-by-timing-error-and-complexity.md)). Two hits on one drum from 5 ms to under 45 ms apart are a grace and its main unless the gap is a grid step, and the grace keeps its gap before the main ([ADR 0027](../decisions/0027-hits-on-one-drum-under-45-ms-apart-are-a-grace-and-its-main.md)). Hits on different drums within 20 ms, or half a 32nd, share a grid point ([ADR 0028](../decisions/0028-limbs-within-20-ms-share-a-grid-point.md)). An onset belongs to the beat its point is in, so one played just before a beat, or put on it at a tempo whose milliseconds don't round-trip, belongs to that beat, whose grid is chosen with it, and no point moves ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)).
  - A beat whose grid is a close call, or with an onset over 20 ms from its point, keeps its best guess and goes into one `ambiguous_bars` request ([ADR 0029](../decisions/0029-unclear-beats-are-one-ambiguous-bars-request.md)). Hit types come from clear velocity groups per family, and anything else is normal at low confidence, in one `hit_types` request ([ADR 0030](../decisions/0030-hit-types-cluster-each-familys-velocities.md)). Each request is answered by calling again with `unmapped`, `grids` or `hit_types`.
  - Exit, as tested: grooves built in code that mix all four grids, from 60 to 240 BPM and across tempo changes, with jitter from a normal spread of 4 ms capped at 12 ms, come back to at least 99.5% of their grid positions. With a spread of 6 ms, 99% holds up to 160 BPM but not at 240 BPM. A `private` test does the same with the performed MIDI in `private/midi/` that is already on a grid.
- **Maps:** library-neutral, for most modern drum libraries, and no library is special in the code ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)).
  - A map file is one library and its kits. Each kit lists its articulations, each with its MIDI notes, velocity behavior, CC behavior, channel, and a source and confidence.
  - Canonical articulation names act as the pivot, because General MIDI has no articulations and the same number differs by library: note 39 is a snare variant in one library and a flam in another. Use `family.articulation` names such as `snare.center`, `hat.closed.tip`, `crash.1.choke`. Conversion tries the exact name, then piece substitution, then drops the variant, then the family default, and reports every inexact step ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)).
  - M1 reads and writes notes, channels and velocity ranges, and output stays inside an articulation's velocity range. CC behavior is stored, validated and preserved ([ADR 0009](../decisions/0009-m1-resolves-notes-channels-and-velocity-ranges.md)). A render keeps a controller-bound note's controller value, and following and writing controllers wait for a map whose sources give them ([ADR 0053](../decisions/0053-a-controller-bound-note-keeps-its-controller-value.md)).
  - Maps are built in, with no user-supplied map files ([ADR 0010](../decisions/0010-built-in-maps-only.md)). M1 ships General MIDI plus maps for ten libraries ([ADR 0011](../decisions/0011-m1-maps-for-general-midi-and-drum-libraries.md)), and M3 adds four ([ADR 0055](../decisions/0055-m3-adds-maps-for-four-drum-libraries.md)). **Build each map from its sources, never from memory.** Every note a source mapping defines is either named at its confidence or reported as unresolved.
- **Maps, as built:**
  - The vocabulary is `data/vocabulary.toml`, and names follow `family[.piece].articulation[.variant...]` ([ADR 0019](../decisions/0019-canonical-names-follow-one-grammar.md)), with damped strokes, a snare with its wires off and a crash's tip stroke added in M3 ([ADR 0062](../decisions/0062-the-vocabulary-adds-damped-strokes-wires-off-and-crash-tips.md)). A map file is one library in TOML, and a map with an unknown name, a missing parent or default, a gap in its pieces, or two overlapping bindings fails to load ([ADR 0020](../decisions/0020-map-files-are-toml-checked-when-they-load.md)).
  - Conversion never changes a hit's family on its own. A target that lacks the family, a missing choke, a controller-driven articulation and notes the source doesn't map are decision requests (`conversion` and `unmapped_notes`), with positions as bar and beat. A request may suggest a substitute from another family, from a fixed list in the vocabulary, used only when the user picks it ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)).
  - Shipped: `gm`, from the General MIDI Level 1 key map ([ADR 0022](../decisions/0022-the-general-midi-map-follows-the-standard.md)), and `sleep-token-ii`, 58 articulations on 68 pitches, written by hand from the library's own mapping and checked against it by a test in `private/`. Nine more are built in `private/` from local sources, every name inferred at low confidence until it is checked ([ADR 0025](../decisions/0025-proposed-names-ship-at-low-confidence.md)): `iof-drummer` (kits `default` and `old`), `ezdrummer-3`, `superior-drummer-3`, `addictive-drums-2`, `ssd5`, `ggd-modern-and-massive`, `ni-abbey-road`, `logic-pro-drums` and `garageband-drums`. A test in `private/` checks that building them again gives the committed files. Each articulation's `source` says what kind of evidence names it, and only names from a standard are kept as labels. Library ids follow [ADR 0023](../decisions/0023-built-in-library-ids.md), and the data is found by one function ([ADR 0024](../decisions/0024-built-in-data-is-found-beside-the-source.md)). M3 adds four ([ADR 0055](../decisions/0055-m3-adds-maps-for-four-drum-libraries.md)): `counterkit` and `ni-drum-lab`, named from each library's own mapping and checked against it by a test in `private/`, `krimh-drums`, from a mapping drawn without note numbers, so every entry is low until one note is checked, and `ggd-matt-halpern`, inferred at low confidence, and `sleep-token-ii` gains a second kit, `groove-pack`, inferred at low confidence for the layout its own groove files play ([ADR 0066](../decisions/0066-sleep-token-ii-gets-an-inferred-groove-pack-kit.md)). A note a mapping defines whose name can't be read with confidence is left out of the map and asked about.
  - Notes whose sound the instrument chooses are the numbered `sample` family, which converting always asks about on a kit without it ([ADR 0019](../decisions/0019-canonical-names-follow-one-grammar.md)). Notes a conversion puts on one pitch and channel at one tick keep their pitches and are reported as collisions ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)).
  - Exit, as tested: a note for every binding of each of the seventeen shipped kits, twelve from M1 and five from M3, converts onto each of them, every ordered pair, without changing family. Each inexact step is reported, in the fallback order and only when the name before it won't do, except that piece substitution re-spreads toms by register whenever the kits have different numbers of them, even when the target has the exact name ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)). Every note of a family the target lacks waits for a `conversion` request.
- **Analyze, as built:**
  - `human-o-matic analyze MIDI_FILE --from-map LIBRARY[/KIT]` normalizes a song and prints one line of compact JSON: a summary of counts and the decision requests, as the MCP layer will return them. `--track` and `--bpm` are flags, and `--answers` is a JSON file of `unmapped`, `grids`, keyed `"bar,beat"` from 0, and `hit_types`. It only reads, and lists no notes. It exits 0 when no request is open, 3 when one is, 2 for a usage error, such as a `--bpm` outside its range or an answer that names something the song lacks, and 1 for a crash ([ADR 0033](../decisions/0033-analyze-takes-flags-and-an-answers-file-and-prints-json.md)).
- **Exit:**
  - Add known jitter to quantized MIDI files and recover at least 99% of grid positions.
  - Round trips keep all notes and non-note events.
  - Converting between any two shipped maps never moves a hit to a different drum family. Where the target lacks an articulation, the fallback is the exact name, then piece substitution, then the name without its variant, then the family default, and every inexact step is reported. A hit whose family the target lacks is a decision request. Tests build any other map they need in code, in `tmp_path`.

### M2 Sections
- Bar features: per-family onset patterns on the grid, which carry each family's density and the cymbal type, with no fill flag ([ADR 0036](../decisions/0036-a-bar-is-its-onset-pattern-in-each-family.md)).
- Build a self-similarity matrix, take [novelty peaks](https://arxiv.org/pdf/2309.02243) at 2 to 8 bar scales, prefer 4, 8 and 16 bar lengths, and cluster repeats into groups. SMF markers win when present.
- `analyze/sections.py` holds these, and `human-o-matic analyze` also prints the sections, each with its bars and repeat group. Each section's facts and ASCII pattern come in M4, with the MCP tools that return them ([ADR 0035](../decisions/0035-m2-finds-the-sections-and-their-facts-wait-for-m4.md)).
- **Labels:** the owner hand-labels at least 10 whole-song drum tracks, one TOML file each in the gitignored `private/labels/`: `midi`, the song's path, relative to `private/` unless absolute; `from_map`; `bpm` and `track` when needed, as in `analyze`; `starts`, the bars where sections begin, counted from 0 as a DAW's bar 1 is bar 0, and starting with 0; and `tuned = true` on a track the detector was tuned on ([ADR 0034](../decisions/0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md)).
- **Sections, as built:**
  - A bar is its onset pattern in each family of the score, 24 slots to a quarter note, with graces left out, and two bars are as alike as the cosine of their patterns, each family scaled to count the same. Density and cymbal type are in the patterns, and there is no fill flag ([ADR 0036](../decisions/0036-a-bar-is-its-onset-pattern-in-each-family.md)).
  - Boundaries are peaks of the novelty at 2, 4 and 8 bars, never on an empty bar, chosen by an exact dynamic program: each is worth its novelty less 0.2, and a section that isn't 4, 8 or 16 bars long costs 0.2. A stretch of 4 or more empty bars is a section of its own, started by a stop and ended by a lead-in, while a shorter silence ends the section before it ([ADR 0037](../decisions/0037-boundaries-are-novelty-peaks-that-favour-4-8-and-16-bar-sections.md)).
  - A section joins the repeat group it plays most like, comparing bars in order, from 0.8, and groups are named A, B, C in song order ([ADR 0038](../decisions/0038-a-section-joins-the-repeat-group-it-plays-most-like.md)). SMF markers, meta events of type 6, snap to the nearest bar line and win when one starts a section, and `find_sections(..., markers=False)` leaves them out ([ADR 0039](../decisions/0039-smf-markers-start-sections-at-the-nearest-bar-line.md)).
  - `human-o-matic analyze` prints the sections as `{"start", "bars", "group"}` beside the summary, which counts them and says whether the markers or the drums set them, and its exit codes stay ([ADR 0040](../decisions/0040-analyze-prints-the-sections-and-its-exit-codes-stay.md)). M2 adds no runtime dependency, and `scipy` waits for code that imports it ([ADR 0041](../decisions/0041-m2-adds-no-runtime-dependency.md)).
  - The label reader, the matcher and the F1 are tested in CI on cases built in code, and a `private` test measures the detector on `private/labels/`, whose report `uv run pytest -m private -raP tests/test_private_sections.py` shows. Measured on 2026-11-09 over 10 labelled tracks, 3 of them tuned and 7 not, the mean F1 is 0.849 and the pooled F1 0.845, so the exit, a mean of at least 0.70 over at least 10 tracks with markers off, is met. Beside it, the untuned mean F1 is 0.815 over the 7, the check that the tuning holds. The 3 tuned tracks average about 0.93, since the costs were chosen on them, which flatters the detector. The weakest track scores about 0.56, as the detector cuts it into more sections than were labelled, the known weakness for a later round of tuning. The labels can still be corrected, so these are the figures of that date.
- **Exit:** boundary F1 within ±1 bar of at least 0.70, as the mean of each track's F1 over at least 10 labelled tracks, measured with SMF markers off. The mean over the tracks not marked `tuned` is reported beside it, as the check on the tuning ([ADR 0034](../decisions/0034-the-m2-exit-is-scored-on-hand-labelled-section-starts.md)). For scale, a [2025 CNN reached 0.77](https://arxiv.org/abs/2509.16566) on 6,134 multi-track MIDI files, with code released, if heuristics fall short. It is unclear whether it uses drums.

### M3 Parametric engine and calibration
- M3 is two PRs, in this order, and its gate follows the second ([ADR 0043](../decisions/0043-m3-is-three-prs-and-its-gate-follows-the-third.md), [ADR 0074](../decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)):
  1. `feat/engine`: the control vector, compiler, sampler, guards and `generic` mode, using the appendix defaults, with the property tests below.
  2. `feat/calibration`: `tools/infer_map.py`, `tools/calibrate.py` and `data/styles/`, which replace the appendix defaults.
- There is no preview PR: the owner hears a render by dragging the file `human-o-matic render` writes into the DAW ([ADR 0074](../decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)).
- `tools/infer_map.py` prints pitch statistics for each folder of performed MIDI in `private/midi/`, so roles can be assigned. **A folder's notes can disagree with its library's map, so each needs verifying.** Exclude and report any folder that cannot be resolved.
- **Calibration, as built:**
  - `tools/infer_map.py` prints, for each folder of `private/midi/`, each pitch's notes and share, files, velocities, where it falls in the bar, and what a built-in kit reads it as, with the share of the folder's notes the kit reads and the pitches it leaves unmapped. `--map` reads a folder through any kit, and `--split` gives a report per subfolder. The tools are scripts in `tools/`, checked like `src/` and tested from `tests/` ([ADR 0058](../decisions/0058-tools-are-scripts-checked-like-src.md)).
  - Which kit reads each folder, and which folders are left out and why, is in the gitignored `private/data/midi-folders.toml`, and no tracked file names a folder ([ADR 0057](../decisions/0057-each-folder-s-kit-is-in-a-gitignored-file-under-private-data.md)). A folder's entry can leave out pitches its kit would read by a name the folder doesn't play, which are then counted and left out of every statistic. Every folder was checked against its library's map, and a folder that no built-in kit reads, or that copies another, is left out.
  - The tools read with the project's own reader and fit with numpy, so calibration adds no dependency. A scan of every folder takes about 7 seconds ([ADR 0056](../decisions/0056-the-calibration-tools-add-no-dependency.md)).
  - `tools/calibrate.py measure` reads each assigned folder's files through their kit with `normalize()` and cuts them into grooves of at most 16 bars. It measures around what a file leaves open: unmapped notes are left out and counted, ambiguous beats keep their best guess, and a file without a tempo has no timing ([ADR 0059](../decisions/0059-calibration-measures-files-in-windows-of-at-most-16-bars.md)). A groove is held to the grid, and its timing left out, when its notes pile up at one offset, more than a fifth of them there and more than twice as many as one step either side, or spread by under 1.5 steps ([ADR 0060](../decisions/0060-a-groove-held-to-the-grid-is-left-out-of-timing.md)). A pack, a folder's first-level subfolder, is a source, and the report counts each band's packs ([ADR 0063](../decisions/0063-a-pack-is-a-source.md)). Grooves the grid doesn't fit are left out of the timing fits: by default, those with more than a tenth of their notes over 20 ms from their grid point, and `measure --misfit SHARE` measures with another share ([ADR 0064](../decisions/0064-grooves-the-grid-does-not-fit-are-left-out-of-the-timing-fits.md)). Velocities are fitted once, on every groove whose velocities aren't flat, and the three styles share them, differing in timing only ([ADR 0065](../decisions/0065-velocities-are-fitted-once-and-shared-by-the-three-styles.md)). Each groove gets the engine's statistics, with feel against the kick ([ADR 0061](../decisions/0061-calibration-measures-the-engine-s-statistics-with-feel-against-the-kick.md)). It prints the distribution of timing spread and the bands a few sets of cuts would make, and, apart, the timing of the folders left out, read with every pitch a drum of its own.
  - The styles are `tight`, the default, `medium` and `loose` only, with no named or numbered drummer ([ADR 0044](../decisions/0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)). Each style's timing pools its band's grooves from every assigned folder, and the velocities they share pool every folder's, so no committed file identifies a source, and what the repo keeps from the performed MIDI is aggregate statistics only ([ADR 0007](../decisions/0007-local-only-files-live-in-private.md)). The bands are cut at 3 and 6 ms of timing spread, over the grooves those rules leave ([ADR 0067](../decisions/0067-the-bands-are-cut-at-3-and-6-ms.md)).
  - `tools/calibrate.py fit` fits the three styles with `tools/fit_styles.py`: velocities shared by the three, by energy rank and metric level, and each band's timing by tempo band, under and from 150 BPM, with what a performance can't give kept from the placeholder ([ADR 0068](../decisions/0068-what-calibration-fits-and-what-stays-modelled.md)), and the rider gap, accent and fill crescendo too ([ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)), and the riders' noise ([ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)). It writes each style as one complete TOML file in `data/styles/`, and `fit --check` compares ([ADR 0069](../decisions/0069-a-style-is-one-complete-toml-file-written-by-the-fit.md)). It prints every value beside the placeholder's, and what runs against Appendix A or the plan's limits. The style model gains velocity by metric level and timing by tempo band, and a section is compiled at its tempo.
  - Measured on 2026-11-10, pooled over the assigned folders: of 3,472 grooves, 1,132 have performed timing, 1,314 are held to the grid, 505 have no tempo and 521 too few notes. With the misfit rule, 131 more are left out of timing, and the 1,001 left spread 1.45 ms at the 5th percentile, 2.39 at the 25th, 4.73 at the median, 6.73 at the 75th and 9.69 at the 95th. The shared velocity fit draws on 3,321 grooves from 22 packs, and the bands' timing on 349, 315 and 337 grooves from 10, 9 and 9 packs. Measured again on 2026-11-12 with each note in the beat its tick is in ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)), every one of these counts and spreads is the same.
  - The styles in `data/styles/` render each band's spread at their defaults, 1.97, 4.14 and 6.48 ms over a 16-bar groove, and kick and backbeats at about 124 at energy 1.0. The engine reads them, and the placeholder stays in the code as the source of the values the fit keeps, never rendered ([ADR 0070](../decisions/0070-the-engine-reads-the-styles-from-data-styles.md)).
  - Six values were compared with published measurements of drummers, in [the styles against published measurements](../research/2026-11-10-styles-against-published-measurements.md). The fit is the default, research fills what a performance can't give, and a value they disagree on, or whose fit runs against Appendix A, is decided with both numbers seen ([ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)). All six are decided. The styles keep Appendix A's fill crescendo, 11, where the grooves' fills fit none, its rider gap, 4 to 14, where the fit's is under half a step, and its accent, 2 plus 6 times the energy, where the fit's, 33.21 less 11.95 times the energy, pushes accents past 127. With both numbers seen, the fit stands where it runs against three of Appendix A's premises: `medium` pushes 2.41 ms and lays back 2.21, `loose` lays back 4.03 ms, 1.19 times its pushed 3.38, and `loose`'s riders from 150 BPM play 1.13 ms early. `fit` prints these, and its check passes. These are the values of the styles fitted again on 2026-11-12 ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)), and [ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md) and the research page give those of the first fit, 2.35, 4.10, 1.23, 3.32 and 1.31.
  - Riders draw their velocities with a noise of their own, Appendix A's 2.5, where the grooves give them 6.21 over 2,859 grooves, their spread about the means of their strong, weak and metric classes, and 4.89 over 2,523 on the alternating quarter-note hits alone, which `fit` prints beside it, and the other roles keep the fitted 5.03. At the fitted noise a quarter-note ride changes direction on 0.77 of its moves, and on 0.84 at 2.5, with the rider gap and flip rate as they were. These are the values of the styles fitted again ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)), and [ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md) and its research page give those of the first fit, 6.19 over 2,867, 4.86 over 2,532, and 5.12 ([ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md), [the rider noise against published measurements](../research/2026-11-11-rider-noise-against-published-measurements.md)).
- **The gate, checked on 2026-11-11 on the three calibrated styles, and again on 2026-11-12 on the styles fitted again with each note in the beat its tick is in ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)), with the riders' own noise ([ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)) and their strong hits held under 127 by a spread of it ([ADR 0077](../decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md)):**
  - Every control moves its statistic strictly the right way over five values and six seeds, in each style ([ADR 0052](../decisions/0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)). The styles share their velocities, so these read the same in each, from a control's lowest value to its highest: `energy` takes normal notes' mean from 88.2 to 120.2, `groove` the accent contrast from 3.8 to 7.1 and the rider gap from 5.9 to 13.0, `dynamic_range` the rider gap from 4.0 to 14.6 and the spread of normal velocities on a drum from 3.3 to 6.3, `fill_intensity` the fills' mean from 108.7 to 119.3, and `ghost_level` the soft notes' from 37.1 to 60.1, and `arc`'s trend is -10.0, 0.6 and 11.3 for `drop`, `steady` and `build`. `tightness` narrows the spread from 2.60 to 2.05 ms in `tight`, 5.67 to 3.85 in `medium` and 8.37 to 5.78 in `loose`, and `feel` moves the snare and riders from 0.14 to 1.93 ms, -1.27 to 3.27 and -2.14 to 4.11, with the snare louder laid back. On the first fit they were 88.5 to 120.2, 3.9 to 7.1, -9.9, 0.6 and 11.2, 5.65 to 3.84, 8.36 to 5.78, and 0.12 to 1.92, -1.25 to 3.22 and -2.19 to 4.08, and the rest as now.
  - The property tests pass at the default 50 examples and at CI's 500, and so does every other test, the private ones included.
  - How the styles and their velocities sound on a real kit, the riders' clearer alternation among them, is the owner's to judge, since no agent can hear it. The owner listened to rendered files on their own kit and passed the gate, so M3 is merged and M4 starts.
- **To try it:** render a song through the kit of the drum instrument that will play it, and drag the file into the DAW onto that instrument's track ([ADR 0074](../decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)):
  ```sh
  uv run human-o-matic render song.mid --from-map gm --to-map sleep-token-ii/default --seed 1 --answers answers.json -o song-tight.mid
  ```
  The first run writes nothing and prints a `hit_types` request, which an answers file with an entry for each family it names settles, such as `{"hit_types": {"kick": {}, "snare": {"soft_below": 50}}}`, where an empty object reads a family's notes as normal. The controls' defaults play at energy 0.5: `--plan` with `{"controls": {"energy": 0.9}}` plays the song harder, and its `sections` set a section's controls by its first bar. `--style medium` and `--style loose` are the other styles, and another `--seed` is another take. The summary's `conversion` says what to listen for in another kit: the notes written as another articulation, such as a tom moved down the kit, the drums that land on one pitch, each a doubled hit, and the names read or written at low confidence ([ADR 0075](../decisions/0075-render-s-summary-counts-how-the-notes-were-placed-in-the-target-kit.md)).
- **Engine, as built:**
  - The controls are layered pydantic models: a section's over the song's, over the style's defaults, with a JSON round trip ([ADR 0046](../decisions/0046-controls-are-layered-pydantic-models-with-a-json-round-trip.md)). The modules and the instrument seam, with `drums` and `generic`, are in [ADR 0045](../decisions/0045-the-engine-is-render-modules-behind-a-small-instrument-seam.md).
  - The styles are `tight`, the default, `medium` and `loose`, read from `data/styles/` ([ADR 0070](../decisions/0070-the-engine-reads-the-styles-from-data-styles.md)). The placeholder, Appendix A with what it leaves out filled in ([ADR 0051](../decisions/0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)), stays in the code as the fit's source and is never rendered. Each note's role comes from canonical families and the score, never a pitch, with three readings of Appendix A: a lone crash-family hit or one starting a run on a beat is an accent, only quarter-note rider hits alternate, and fills are capped at 2 bars ([ADR 0047](../decisions/0047-roles-come-from-canonical-families-and-the-score.md)). A rider hit not typed soft draws its velocity with the style's rider noise, smaller than the other roles', so its strong and weak hits stay apart, and a soft-typed one keeps the soft notes' spread. A test holds a quarter-note ride over four 256-bar takes to changing direction on at least 0.81 of its moves, where the other roles' noise would give about 0.77 ([ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)). Where half the gap would take a rider's strong hits within a spread of its noise of 127, from energy 0.75 at the defaults, they are held that spread under 127 and the weak hits the whole gap below, so a quarter-note ride keeps a gap of about 8.3 of its 9, where the tests' check over four 256-bar takes reads about 8.2, 8.21 on the refitted styles, and changes direction on about 0.84 of its moves from energy 0.8 to 1.0, where reflection had left 7.5, 4.6 and 0.3 at 0.8, 0.9 and 1.0. The rule binds from energy 0.61 to 0.89 as `dynamic_range` falls from 1 to 0, and keeps 13.2 of a gap of 14 and 3.2 of 4 at full energy. A test holds the ride from energy 0.8 up to a gap of at least 7.8, at least 0.815 of its moves turning, and nothing past 127 ([ADR 0077](../decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md)). Measured again on the styles fitted again on 2026-11-12, the ride's turns, its gaps and the energies the rule binds from are the same, and the fitted rider center at energy 1.0 is 126.81, where ADR 0077 gives the first fit's 126.78 ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)).
  - Each section draws from its own stream, keyed by its first bar and take, and the song's drifts from their own, so a section rendered again leaves the others as they were. A note renders with the section of its beat, which holds its tick, so a downbeat played just early renders with its own section, and a backbeat played early is a backbeat ([ADR 0086](../decisions/0086-a-note-belongs-to-the-beat-its-tick-is-in.md)). Turning `skip` on or off for a section can move the notes at and just after its boundaries by a step or a few ticks, as they then avoid its fixed notes, even in a section further on when the sections between lack those pitches and drums. Every other control change leaves the other sections byte-identical ([ADR 0049](../decisions/0049-each-section-draws-from-its-own-seeded-stream.md)). The guards hold every backend: the ±12 ms cap, 60% of the grid gap, reflection below 127, velocity ranges, soft below normal, and no repeat on a pitch or on a drum, with rules at section boundaries that never depend on another section's draws ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)). The gap is counted in milliseconds through the tempo map, as the cap is, and a main note and its graces move by one shift in milliseconds, so between two notes of a section the gap never takes a note past the cap. The gap is held in each pitch's play order, each note's side of a boundary is carried back through its section, of two notes on one grid point either side of a boundary the later keeps a tick after it, and a grace the score puts on its main's tick takes its main only as far as the cap ([ADR 0073](../decisions/0073-the-gap-is-counted-in-milliseconds-through-the-tempo-map.md)).
  - Notes are written through the target kit by conversion's own fallback order, and only the drum track's notes change ([ADR 0048](../decisions/0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)). A controller-bound note keeps its controller value, and following and writing controllers wait for a map that gives them ([ADR 0053](../decisions/0053-a-controller-bound-note-keeps-its-controller-value.md)).
  - `human-o-matic render` writes a new MIDI file by a plan file and prints each section's statistics, with `analyze`'s answers and exit codes ([ADR 0054](../decisions/0054-human-o-matic-render-writes-a-new-midi-file-by-a-plan-and-prints-json.md)). Its summary counts, from conversion's own report, how the notes were placed in the target kit: each source articulation written as another, with its steps, the target pitches where notes from different source pitches meet on a grid point, which the guards keep a tick or more apart, and the notes read or written through low-confidence names ([ADR 0075](../decisions/0075-render-s-summary-counts-how-the-notes-were-placed-in-the-target-kit.md)).
  - Exit, as tested on the three styles: in each of `tight`, `medium` and `loose`, each control moves the statistic it mainly drives strictly the right way over five values and six seeds, with `feel`'s laid-back side held to its pushed side in the style's own ratio, and the property tests below pass with `hypothesis`, drawing the style ([ADR 0052](../decisions/0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md), [ADR 0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md)). Each style's timing spread at its defaults falls in its band, and kick and backbeats at energy 1.0 play 118 to 127.
- **Exit:** raising each control moves its measured statistic in the right direction, and all property tests below pass. It is checked at the gate, after calibration, on the calibrated styles.

### M4 MCP, skill and the main gate
- M4 is three PRs, in this order, and its gate follows the third ([ADR 0078](../decisions/0078-m4-is-three-prs-and-its-gate-follows-the-third.md)):
  1. `feat/mcp`: `session.py`, `analyze/facts.py`, `mcp_server.py` and the MCP tools, with the `mcp` dependency.
  2. `feat/skill`: `SKILL.md`, `references/vocabulary.md` and the check of about 30 answers.
  3. `feat/blind-test`: `tools/make_ab.py` and the five variants.
- Sessions are JSON files, one per session ID, in `sessions/` under the user's state directory, `$XDG_STATE_HOME/human-o-matic/` or `~/.local/state/human-o-matic/`, which `HUMAN_O_MATIC_STATE_DIR` replaces, by default outside the repository and `private/` ([ADR 0079](../decisions/0079-sessions-are-json-files-in-the-user-s-state-directory.md)).
- Build the MCP server and skill. Register with `claude mcp add human-o-matic -- uv run --directory ~/Projects/human-o-matic human-o-matic-mcp`, install the skill with `ln -s ~/Projects/human-o-matic/skills/human-o-matic ~/.claude/skills/human-o-matic` ([ADR 0088](../decisions/0088-the-skill-is-installed-by-a-link-from-claude-skills-to-the-repository.md)), then test a full session in Claude Code.
- Build `analyze/facts.py`, each section's facts and its compact ASCII pattern, with the MCP tools that return them, such as `get_sections` ([ADR 0035](../decisions/0035-m2-finds-the-sections-and-their-facts-wait-for-m4.md)).
- **The MCP server, as built in `feat/mcp`:** `session.py`, `analyze/facts.py`, `render/describe.py` and `mcp_server.py` with the nine tools, as the architecture's MCP tools section sets out ([ADRs 0080 to 0085](../decisions/0080-a-session-holds-what-a-render-needs-and-reads-its-file-again-by-its-hash.md)). The tests call each tool as a method, and talk to the server through the SDK's in-memory client and over stdio through the console script. They check that a session round-trips through its file, that the same session JSON and seed export the same bytes, that another take of a section leaves the others' notes as they were, that `export` never writes the input and refuses an existing file unless `overwrite` is set, each section edit, the facts of songs built in code, and that no reply holds a note list. A full session in Claude Code, with the server registered, waits for the skill.
- `references/vocabulary.md` plus a check of about 30 answers against expected control ranges, run through a real agent session.
- **The skill, as built in `feat/skill`:**
  - `skills/human-o-matic/SKILL.md` is a Claude Code skill: the question policy above, and the workflow over the nine tools in their order, opening the song, confirming in one batch, the song-wide round, each repeat group in song order, the echo of each interpretation with `set_section_controls`' `expected`, an export after each round to a new numbered file beside the input, as the product flow's `song-2.mid`, for the user to drag onto the drum instrument in the DAW, and refinements as small patches. It never passes notes, and says nothing is added and there is no live preview. Since M6, nothing is added unless the user asks for added notes, which turns a section's creative mode on ([ADR 0096](../decisions/0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md)).
  - `references/vocabulary.md` maps 30 answers, the plan's four examples first at its values, and 3 refinements to controls, each a starting point with the range that keeps its meaning, as `0.95 [0.85, 1]`, in two tables a test parses ([ADR 0087](../decisions/0087-the-skill-s-answers-are-checked-by-a-table-with-ranges-a-test-of-it-and-an-agent-given-only-the-skill.md)). A row sets only its controls, rows are written for a song at the defaults, and every value beyond the plan's four is drafted unheard, for the owner to refine by ear ([ADR 0089](../decisions/0089-the-vocabulary-s-rows-set-only-their-controls-and-beyond-the-plan-s-four-are-drafted-unheard.md)).
  - The check: tests hold the skill's frontmatter and its naming of every tool, and every row of the vocabulary to the control model and its range. `uv run python tools/check_answers.py phrases` prints a phrase for each answer in other words, with no range, and `brief` what an agent given only the skill is asked. `compare RESULTS` checks the agent's controls for each phrase, clamped as the server clamps them, against the answer's ranges, and the defaults for the controls the answer leaves out. The live session in Claude Code is the end-to-end step ([ADR 0087](../decisions/0087-the-skill-s-answers-are-checked-by-a-table-with-ranges-a-test-of-it-and-an-agent-given-only-the-skill.md)). The check maps answers to controls and reads no section's facts, so [ADR 0082](../decisions/0082-a-section-s-facts-are-counted-and-its-guess-says-only-what-the-score-shows.md)'s thresholds stay as they are, and meet a real song first in that session.
  - The skill is installed by a link, made once, `ln -s ~/Projects/human-o-matic/skills/human-o-matic ~/.claude/skills/human-o-matic`, never a copy ([ADR 0088](../decisions/0088-the-skill-is-installed-by-a-link-from-claude-skills-to-the-repository.md)).
- **Blind test:** `tools/make_ab.py` writes shuffled, anonymized sections and a hidden key. The owner renders them through one kit and rates them, ideally with one or two other producers. Variants:
  1. Quantized, one flat velocity
  2. Naive randomization (SD 8 ms, velocity ±12)
  3. Engine defaults, no questions
  4. Guided by answers
  5. Guided, velocities only with quantized timing
- **Gate:**
  - Variant 4 must beat variant 2. If it does not, stop and discuss.
  - If 4 does not beat 3, questions are not paying for themselves: shrink to a few song-wide questions.
  - If 5 matches 4, default timing to almost nothing, as the perception research predicts it might.
  - Record how many questions a real song took and whether they felt worth it.

### M5 Trained model experiment (gate)
- **Data:** the performed MIDI in `private/midi/`, normalized through M3's maps. Split by song and hold out one whole drummer. Many files share a song, so a file-level split would leak.
- **Task:** flat quantized score plus hit types and control vector, to per-note timing offset and velocity. Controls come from the target performance's own attributes, so training is self-supervised, as in MuseCoco.
- **Output must be sampled** (for example a mixture density head). Predicting the mean flattens dynamics and recreates the robotic sound.
- **Model:** small sequence model, up to about 500k parameters. PyTorch on MPS. It plugs in as `backends/neural.py`. Song-level drift stays explicit, and guards still apply.
- **Gate:** must follow the controls (M3's exit test) and beat the parametric engine in a blind test with at least six trial pairs. Otherwise keep the engine and archive the experiment, which is a valid result.

### M6 Added notes (opt-in)
Ghosts, flams, rimshots and chokes, opt-in. The priority is confirmed. Creative mode is never asked about: the skill sets it only when the user asks for notes the song lacks, so it adds no question ([ADR 0096](../decisions/0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md)).
- It is built now, ahead of M4's blind test: a creative mode, per section, that adds ghost notes, cymbals where a section is sparse, fills between sections where there are none, and flams, rimshots and chokes. It is off by default, so a render without it, and the blind test's variants, are as before, and the skill sets it only when the user asks, so it adds no question.
- **As built, in `feat/creative-mode`:**
  - `creative` is a boolean control, false in every style's defaults, set per section or for the song with `set_section_controls`, under each section's own, and unset in older sessions. `skip` wins. The added notes are made at render time, never kept in the score or the session, and the instrument seam gains `additions`, which `generic` answers with nothing ([ADR 0091](../decisions/0091-creative-mode-is-a-section-s-control-off-by-default-that-lets-it-add-notes.md)).
  - `instruments/additions.py` proposes, from the section's own score, parts, grids and hit types: a fill of 16ths over the last two quarter notes of a section whose last bar has notes and no fill note, followed by a section with notes, on its snare and the toms it plays; where its cymbal hits number fewer than its beats, a crash every 4 bars where no crash or ride hits and its rider on each beat between its first and last hits; soft ghost notes on its snare, on the 16ths between 8ths its stream picks once with the chance 0.3; a 25 ms soft grace before the last backbeat of every fourth bar; the first backbeat of every 4 bars as the kit's rimshot; and the kit's choke an 8th after its last crash-family accent ([ADR 0092](../decisions/0092-a-creative-section-adds-by-rules-read-from-its-own-score.md)).
  - They draw from a stream of their own, `(2, start, take)`, through the section's own parameters, an onset's shared offset kept, and the drifts read between the score's ticks ([ADR 0093](../decisions/0093-added-notes-draw-from-a-stream-of-their-own-through-their-section-s-parameters.md)).
  - `render/creative.py` admits a note only on a pitch and drum its section plays, and where the latest and earliest the notes of other sections around it can be leave it its gap within the cap, and the guards count every rule at a boundary on the score's own notes, an added note at a boundary taking its section's own class there. So turning creative mode on, or rendering a creative section again, leaves every other section's notes byte-identical. A section without toms gets a snare fill, and rimshots and chokes are added only where the section already plays them ([ADR 0094](../decisions/0094-an-added-note-changes-no-other-section.md)).
  - A rimshot or choke the target kit lacks is skipped as `missing`, never asked about or substituted. The reports count the notes added by kind and those skipped as `missing`, `unplayed`, `played` or `crowded`, in the summary and each section, and `expected` and `says` say them ([ADR 0095](../decisions/0095-an-addition-the-kit-can-t-play-is-skipped-and-the-reports-count-what-was-added.md)).
  - `SKILL.md` and the vocabulary, now 34 answers and 3 refinements, set `creative` only on the user's request, and echo what it may add ([ADR 0096](../decisions/0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md)).
  - Tests: `hypothesis` holds, with creative sections drawn among the others in every style, that turning one section creative leaves every other section's notes as they were, that rendering one again leaves the others and what they added as they were, the same bytes for the same plan and seed, every score note once and the added notes those the report counts, on no grid point their drum or pitch already has, velocities 1 to 127 and never repeating on a pitch or drum, soft notes below the others of their drum, the cap, the 60% gap and no overlap on a pitch across tempo changes of 10 to 1, a skipped section unchanged, and the input's velocities and timing reaching nothing added. Examples hold each addition's rule and each skip.
- **Gate:** the owner listens to creative sections on their kit.

### M7 Website
A public website where musicians choose a drum MIDI file, answer the page's questions with presets, sliders and checkboxes, download the re-performed file for their DAW, and leave feedback. It is a thin page over the same engine, with no LLM and no accounts, built after M4's gate, whose result sets how many questions it asks ([ADR 0097](../decisions/0097-a-website-is-milestone-m7-a-thin-page-over-the-same-engine-that-asks-the-questions-itself.md)). Everything else, where the engine runs, the limits, privacy, the theme, hosting, its PRs and its gate, is in [the website plan](2026-11-13-website.md).

## Verification

**Property tests** (`hypothesis`)
- Same session and seed produce byte-identical output. Re-rendering one section with new controls leaves every other section's notes byte-identical. The one exception is turning `skip` on or off for a section: the notes at and just after its boundaries, on the pitches and drums that cross them, can move by a step or a few ticks, because they then avoid its fixed notes, and so can a section further on when the sections between have none of those notes. Every other control change leaves the other sections byte-identical ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)). Turning creative mode on or off for a section, or rendering a creative section again, leaves every other section's notes, and what they add, byte-identical ([ADR 0094](../decisions/0094-an-added-note-changes-no-other-section.md)).
- Note count is unchanged apart from notes the user chose to drop, and in a creative section the notes it adds, which the report counts ([ADR 0091](../decisions/0091-creative-mode-is-a-section-s-control-off-by-default-that-lets-it-add-notes.md)).
- Outside `skip` sections, input velocities and timing cannot influence output beyond hit type: two inputs with the same notes and types but different numbers render identically, with what creative sections add.
- Same-pitch notes never reorder, and each keeps at least 60% of its grid gap.
- Offsets stay within the cap at every tempo, including dense tempo maps.
- Velocities stay in 1 to 127. Consecutive velocities on one pitch, or on one drum, never repeat ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)).
- Soft-typed notes always land below normal-typed notes on the same drum in the same section.
- Rider flip rate stays in 0.70 to 0.85 over a large sample. Default-style unison spread stays at or below about 10 ms.
- Grace-to-main spacing is preserved. On the song's first tick, where a grace can't go before its main in the score, its main goes later to keep the gap, up to the cap, and a gap over 12 ms is shortened to it ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)). `skip` sections come out unchanged. To another target kit, they keep their velocity and timing, and take the target's pitch and channel as conversion does, with the velocity moved into the target's range ([ADR 0048](../decisions/0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).

**End to end:** in Claude Code, run a real song through the full conversation, export it through the owner's kit, drag the file into the DAW onto that drum instrument, and have the owner listen.

## Do not

- Build a DAW bridge or a built-in LLM in this version, or a web UI other than M7's site, a thin page over the same engine ([ADR 0097](../decisions/0097-a-website-is-milestone-m7-a-thin-page-over-the-same-engine-that-asks-the-questions-itself.md)). The session format keeps them possible later.
- Pass note arrays through MCP.
- Train before M4 exists: without a baseline, "better" means nothing.
- Commit, copy out of or redistribute anything in `private/` ([ADR 0007](../decisions/0007-local-only-files-live-in-private.md)).
- Load user-supplied map files in this version: maps are built in ([ADR 0010](../decisions/0010-built-in-maps-only.md)).
- Special-case a library in the code: libraries differ only in their map data ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)).
- Let timing exceed performed magnitudes by default.
- Add notes outside a creative section, or on a drum or pitch the section doesn't play, or have the skill suggest creative mode unprompted ([ADR 0094](../decisions/0094-an-added-note-changes-no-other-section.md), [ADR 0096](../decisions/0096-the-skill-turns-creative-mode-on-only-when-the-user-asks-for-added-notes.md)).
- Build piano or guitar logic now.

## Appendix A: Engine defaults

The placeholder, with the values it leaves out in [ADR 0051](../decisions/0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md). It is never rendered: the styles in `data/styles/` are, and they keep its values where a performance can't give one, and its fill crescendo, rider gap, accent and rider noise ([ADRs 0068](../decisions/0068-what-calibration-fits-and-what-stays-modelled.md), [0070](../decisions/0070-the-engine-reads-the-styles-from-data-styles.md), [0071](../decisions/0071-the-fit-is-the-default-and-research-fills-what-a-performance-can-t-give.md) and [0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)). Velocity anchors are at energy 1.0, 0.5 and 0.2; interpolate between them.

**Velocity**

| Role | E = 1.0 | E = 0.5 | E = 0.2 |
|---|---:|---:|---:|
| Kick | 122 (band 116 to 127) | 104 | 85 |
| Double kick (4+ notes at gaps up to 0.25 beats) | 118, feet ±3 | 100 | 82 |
| Snare backbeat | 123 (band 117 to 127) | 100 | 80 |
| Other normal snare | 106 | 88 | 68 |
| Rider | 114 | 95 | 72 |
| Accent cymbal (single hit or first of a run on a downbeat) | 122, floor 114 | 105 | 85 |
| Soft-typed notes | 25 to 55, scaled by `ghost_level` and energy | | |

- **Rider alternation:** strong hits land with the snare, found by a vote across the run. Gap 4 to 14 from `dynamic_range`, noise SD about 2.5, the riders' own, where the styles fit the other roles' noise at 5.03 ([ADR 0076](../decisions/0076-riders-draw-their-velocities-with-a-noise-of-their-own.md)). Where half the gap would take the strong hits within a spread of their noise of 127, they are held that spread under it and the weak ones the gap below ([ADR 0077](../decisions/0077-a-rider-s-strong-hits-are-held-under-127-by-a-spread-of-their-noise.md)). **Must be probabilistic: flip rate 0.75 to 0.80.** Strict alternation sounds mechanical. For 8th and 16th patterns, alternate the quarter accents only.
- **Fills:** snare and tom runs with gaps up to 0.5 beats, 3+ notes, containing a tom or a gap up to 0.26 beats. Add metric accent (6, 5, 2, 0) and hand alternation ±2, then crescendo up to 11 over the last 4 beats at most, scaled by `fill_intensity`.
- **Energy drift:** slow process, SD about 2, across the song.
- **Near the ceiling, reflect samples rather than clip,** or everything piles up at 127. Then forbid identical consecutive values per pitch (nudge ±1, or -1 at 127).

**Timing** (ms, converted with the local tempo)
- **Drift:** sum of slow processes at time constants of 16, 64 and 256 beats, total SD about 2.5, for long memory. Performed loops are too short to fit this, so it stays modelled.
- **Shared offset per onset:** SD about 2.2, scaled by tightness.
- **Limb offsets:** snare about +1, riders about +0.7, others 0, jitter SD 1.8 to 3 clipped to ±4, then replaced by M3's values.
- **Overall spread:** about 3 to 4 ms at the default `tight` style. Cap ±12 ms.
- **Feel:** up to about +6 ms laid back (with a loudness increase on snare) and about -3 ms pushed.
- **Guards:** each same-pitch note keeps at least 60% of its grid gap. Trim durations so same-pitch notes never overlap. Clamp at tick 0 and report it. Grace notes take their main note's offset.

## Appendix B: Python libraries

`mido` (lossless I/O), `numpy`, `scipy`, `pydantic`, `typer`, the official `mcp` Python SDK (check current docs, as the spec is moving), `pytest`, `hypothesis`, and PyTorch in M5 only. Each runtime dependency is added in the milestone that first needs it: `mido`, `numpy`, `pydantic` and `typer` in M1, none in M2 or M3, and `mcp` in M4 ([ADR 0012](../decisions/0012-runtime-dependencies-arrive-with-their-milestone.md)), at 2.3.0, whose `MCPServer` serves the tools over stdio ([ADR 0085](../decisions/0085-the-server-is-the-mcp-sdk-s-mcpserver-over-stdio-run-as-human-o-matic-mcp.md)). `python-rtmidi`, once planned for a live preview, is not used: a render is heard from its file in the DAW ([ADR 0074](../decisions/0074-a-render-is-heard-from-its-midi-file-in-the-daw-and-there-is-no-live-preview.md)). `scipy` comes with the first code that imports it ([ADR 0041](../decisions/0041-m2-adds-no-runtime-dependency.md)). `symusic`, once planned for scanning the performed MIDI, is not used: the project's own reader scans it in seconds ([ADR 0056](../decisions/0056-the-calibration-tools-add-no-dependency.md)).
