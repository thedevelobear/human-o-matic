# human-o-matic: guided MIDI drum performance

> **Status:** Active. M0 to M2 are merged, M3's engine, the first of its three PRs, is merged, and calibration, the second, is under way.
> A living document. Each PR updates the progress table and the sections its work changes. Decisions are in [`../decisions/`](../decisions/).
> Last updated: 2026-11-10 (M3's engine merged and ADRs 0043 to 0054 accepted; calibration started on `feat/calibration`, with `tools/infer_map.py` and maps for four more libraries, ADRs 0055 to 0058 proposed, and ADRs 0001, 0011, 0012 and 0023 amended by them; then `tools/calibrate.py measure`, which measures each groove and proposes no style yet, ADRs 0059 to 0061 proposed).

Handoff document for an implementing agent with no prior context. The app is called **human-o-matic**: use `human-o-matic` for the repo, distribution, CLI and skill, and `human_o_matic` for the Python package.

## Progress

Milestones are done in order, and work stops at each gate ([`AGENTS.md`](../../AGENTS.md)).

| # | Milestone | Gate | Status |
|---|---|---|---|
| M0 | Setup | The checks pass on the scaffolding | Merged ([#1](https://github.com/thedevelobear/human-o-matic/pull/1)) |
| M1 | Normalize | The M1 exit tests | Merged ([#2](https://github.com/thedevelobear/human-o-matic/pull/2)) |
| M2 | Sections | Boundary F1 of at least 0.70 on at least 10 tracks the owner has hand-labelled | Merged ([#3](https://github.com/thedevelobear/human-o-matic/pull/3)) |
| M3 | Parametric engine and calibration | Each control moves its statistic the right way, and the property tests pass | In progress: the engine merged ([#4](https://github.com/thedevelobear/human-o-matic/pull/4)), and calibration, the second of three PRs, under way |
| M4 | MCP, skill and the main gate | The blind listening test, judged by the owner | Not started |
| M5 | Trained model experiment | Follows the controls and wins a blind test, judged by the owner | Not started. Not before M4 |
| M6 | Added notes | The owner confirms the priority first | Not started |

**Follow-up fixes.** Fixes to a merged milestone land on `fix/topic` branches, with no number, and are listed here.

| Branch | Contents | Status |
|---|---|---|
| | | |

## Context

Programmed drum MIDI sounds robotic, and existing tools mostly fix that with blind randomization. Randomization cannot know that one section is a full-power breakdown and another a low-energy bridge that needs groove.

**Product:** an MCP server that re-performs a drum MIDI file section by section. An agent such as Claude Code loads the file, the server divides it into sections, the agent asks the user about each one ("what's the energy here?"), and the user's answers steer the render. Answers like "it's a breakdown, full power" or "it's a bridge, low energy and high groove" become numeric controls. The result is a new MIDI file. Drums first; the design must allow piano, guitar and others later.

**Scope:** a normal, public app, built in this repo. Local-only files stay in a gitignored `private/` folder, and nothing in it is committed or redistributed ([ADR 0007](../decisions/0007-local-only-files-live-in-private.md)).

## Decisions already made

| Question | Decision |
|---|---|
| Language | Python 3.12+ (see below) |
| Interaction | Guided by questions, per section. Running with all defaults must still work, but it is not the main path |
| Who asks the questions | The connected agent, through MCP. No built-in LLM and no UI of its own, so the app has no API bill or API key |
| Existing humanization | Rebuild from scratch: all timing is re-quantized and all velocity numbers are discarded |
| What survives from the input | The notes and each note's **hit type only**: soft, normal or accent, confirmed with the user. If the input has one flat velocity, infer hit types and ask |
| Adding notes | Version 1 never adds notes. Ghosts, flams, rimshots and chokes come later, opt-in |
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
Agent: Taking that as maximum energy, tight, little light and shade. Sound right? Previewing C now.
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
    analyze/facts.py      per-section facts and compact ASCII pattern for the agent, in M4
    controls.py           pydantic ControlVector, Controls, SectionPlan, SessionPlan
    render/parts.py       each note's role and limb, and the play order
    render/style.py       styles: the placeholder `tight` until calibration
    render/compiler.py    controls + style into per-role parameters
    render/engine.py      seeded streams, the song's drifts, render()
    render/guards.py      limits that apply to every backend
    render/target.py      each note's pitch, channel and velocity range in the target kit
    render/controllers.py the windows that keep a controller-bound note's value
    render/output.py      the rendered notes back into the drum track
    render/measure.py     each section's statistics
    render/backends/      parametric.py; neural.py in M5 only
    instruments/          base protocol, drums.py, generic.py
    session.py            session JSON on disk: sections, answers, controls, seed
    preview.py            MIDI playback to a virtual port
    mcp_server.py         thin MCP layer over the above
    cli.py                analyze: a song's summary, sections and decision requests as JSON; render: a new MIDI file by a plan
  skills/human-o-matic/SKILL.md       question policy and workflow
  skills/human-o-matic/references/vocabulary.md
  data/vocabulary.toml                the canonical articulation vocabulary
  data/maps/*.toml                    built-in maps, one library per file: its kits and their articulations
  data/styles/*.toml                  tight, medium and loose, generated by calibration
  tools/                              infer_map and midi_folders, calibrate, make_ab, train: scripts, checked like src (ADR 0058)
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
| `open_session(midi_path, from_map, to_map, instrument, bpm?, track?)` | Normalize and detect sections. `from_map` and `to_map` name a built-in library and kit, never a map file ([ADR 0010](../decisions/0010-built-in-maps-only.md)). Returns a session ID, summary, and anything needing a decision |
| `get_sections(session_id)` | Bars, repeat group, facts, ASCII pattern, plus suggested questions and a guess with confidence |
| `update_sections(session_id, ops)` | Split, merge, move boundaries, rename |
| `set_hit_types(session_id, decisions)` | Confirm soft notes and resolve ambiguous bars |
| `set_style(session_id, style, seed?)` | Song-wide style, `tight`, `medium` or `loose` ([ADR 0044](../decisions/0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)), and tightness |
| `set_section_controls(session_id, section_ids, controls, note)` | Validate and store. Returns plain-language expected results, such as "snare about 118 to 127, timing spread about 3 ms", and any clamping |
| `render(session_id, section_ids?, take?)` | Sample, returning measured stats per section |
| `preview(session_id, section_ids?, take?, port?)` / `stop_preview` | Non-blocking playback through a virtual MIDI port |
| `export(session_id, output_path, overwrite?)` | Write MIDI and a report. Never overwrite the input; refuse existing files unless `overwrite` is set |

**Preview:** the sample library determines how velocities sound, so preview through the user's real kit: enable the macOS IAC Driver, route it to the DAW track, and play with `mido` and `python-rtmidi`. This route was not verified during research, so test it in M3's last PR ([ADR 0043](../decisions/0043-m3-is-three-prs-and-its-gate-follows-the-third.md)). If it fails, fall back to exporting and dragging into the DAW.

### Control vector

Per section, all optional, with defaults supplied by the song style:

| Control | Range | Mainly drives |
|---|---|---|
| `energy` | 0 to 1 | Velocity centers and floors, accent strength |
| `groove` | 0 to 1 | Accent contrast, soft note presence, hat and ride shape |
| `dynamic_range` | 0 to 1 | Spread within a drum, strong versus weak hits |
| `tightness` | 0 to 1 | Timing spread (usually set once per song) |
| `feel` | -1 pushed to +1 laid back | Mean offset of snare and riders, with loudness coupled when laid back. Keep the pushed side smaller |
| `arc` | `steady`, `build`, `drop` | Energy shape across the section |
| `fill_intensity` | 0 to 1 | Fill velocity and crescendo |
| `ghost_level` | 0 to 1 | Velocity of notes typed soft |
| `skip` | boolean | Leave this section exactly as it came in, for parts the user already finished |

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
6. **Echo each interpretation in plain words,** preview, and treat refinements as small changes to existing controls.
7. **Budget:** about 12 questions for a typical song, measured in M4.

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
  - Each beat takes the 16th, 8th triplet, 16th triplet or 32nd with the least timing error in milliseconds plus a penalty of 0, 6, 10 and 10 ms ([ADR 0026](../decisions/0026-a-grid-per-beat-by-timing-error-and-complexity.md)). Two hits on one drum from 5 ms to under 45 ms apart are a grace and its main unless the gap is a grid step, and the grace keeps its gap before the main ([ADR 0027](../decisions/0027-hits-on-one-drum-under-45-ms-apart-are-a-grace-and-its-main.md)). Hits on different drums within 20 ms, or half a 32nd, share a grid point ([ADR 0028](../decisions/0028-limbs-within-20-ms-share-a-grid-point.md)).
  - A beat whose grid is a close call, or with an onset over 20 ms from its point, keeps its best guess and goes into one `ambiguous_bars` request ([ADR 0029](../decisions/0029-unclear-beats-are-one-ambiguous-bars-request.md)). Hit types come from clear velocity groups per family, and anything else is normal at low confidence, in one `hit_types` request ([ADR 0030](../decisions/0030-hit-types-cluster-each-familys-velocities.md)). Each request is answered by calling again with `unmapped`, `grids` or `hit_types`.
  - Exit, as tested: grooves built in code that mix all four grids, from 60 to 240 BPM and across tempo changes, with jitter from a normal spread of 4 ms capped at 12 ms, come back to at least 99.5% of their grid positions. With a spread of 6 ms, 99% holds up to 160 BPM but not at 240 BPM. A `private` test does the same with the performed MIDI in `private/midi/` that is already on a grid.
- **Maps:** library-neutral, for most modern drum libraries, and no library is special in the code ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)).
  - A map file is one library and its kits. Each kit lists its articulations, each with its MIDI notes, velocity behavior, CC behavior, channel, and a source and confidence.
  - Canonical articulation names act as the pivot, because General MIDI has no articulations and the same number differs by library: note 39 is a snare variant in one library and a flam in another. Use `family.articulation` names such as `snare.center`, `hat.closed.tip`, `crash.1.choke`. Conversion tries the exact name, then piece substitution, then drops the variant, then the family default, and reports every inexact step ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)).
  - M1 reads and writes notes, channels and velocity ranges, and output stays inside an articulation's velocity range. CC behavior is stored, validated and preserved ([ADR 0009](../decisions/0009-m1-resolves-notes-channels-and-velocity-ranges.md)). A render keeps a controller-bound note's controller value, and following and writing controllers wait for a map whose sources give them ([ADR 0053](../decisions/0053-a-controller-bound-note-keeps-its-controller-value.md)).
  - Maps are built in, with no user-supplied map files ([ADR 0010](../decisions/0010-built-in-maps-only.md)). M1 ships General MIDI plus maps for ten libraries ([ADR 0011](../decisions/0011-m1-maps-for-general-midi-and-drum-libraries.md)), and M3 adds four ([ADR 0055](../decisions/0055-m3-adds-maps-for-four-drum-libraries.md)). **Build each map from its sources, never from memory.** Every note a source mapping defines is either named at its confidence or reported as unresolved.
- **Maps, as built:**
  - The vocabulary is `data/vocabulary.toml`, and names follow `family[.piece].articulation[.variant...]` ([ADR 0019](../decisions/0019-canonical-names-follow-one-grammar.md)). A map file is one library in TOML, and a map with an unknown name, a missing parent or default, a gap in its pieces, or two overlapping bindings fails to load ([ADR 0020](../decisions/0020-map-files-are-toml-checked-when-they-load.md)).
  - Conversion never changes a hit's family on its own. A target that lacks the family, a missing choke, a controller-driven articulation and notes the source doesn't map are decision requests (`conversion` and `unmapped_notes`), with positions as bar and beat. A request may suggest a substitute from another family, from a fixed list in the vocabulary, used only when the user picks it ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)).
  - Shipped: `gm`, from the General MIDI Level 1 key map ([ADR 0022](../decisions/0022-the-general-midi-map-follows-the-standard.md)), and `sleep-token-ii`, 58 articulations on 68 pitches, written by hand from the library's own mapping and checked against it by a test in `private/`. Nine more are built in `private/` from local sources, every name inferred at low confidence until it is checked ([ADR 0025](../decisions/0025-proposed-names-ship-at-low-confidence.md)): `iof-drummer` (kits `default` and `old`), `ezdrummer-3`, `superior-drummer-3`, `addictive-drums-2`, `ssd5`, `ggd-modern-and-massive`, `ni-abbey-road`, `logic-pro-drums` and `garageband-drums`. A test in `private/` checks that building them again gives the committed files. Each articulation's `source` says what kind of evidence names it, and only names from a standard are kept as labels. Library ids follow [ADR 0023](../decisions/0023-built-in-library-ids.md), and the data is found by one function ([ADR 0024](../decisions/0024-built-in-data-is-found-beside-the-source.md)). M3 adds four ([ADR 0055](../decisions/0055-m3-adds-maps-for-four-drum-libraries.md)): `counterkit` and `ni-drum-lab`, named from each library's own mapping and checked against it by a test in `private/`, `krimh-drums`, from a mapping drawn without note numbers, so every entry is low until one note is checked, and `ggd-matt-halpern`, inferred at low confidence. A note a mapping defines that the vocabulary can't name, or whose name can't be read, is left out of the map and asked about.
  - Notes whose sound the instrument chooses are the numbered `sample` family, which converting always asks about on a kit without it ([ADR 0019](../decisions/0019-canonical-names-follow-one-grammar.md)). Notes a conversion puts on one pitch and channel at one tick keep their pitches and are reported as collisions ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)).
  - Exit, as tested: a note for every binding of each of the sixteen shipped kits, twelve from M1 and four from M3, converts onto each of them, every ordered pair, without changing family. Each inexact step is reported, in the fallback order and only when the name before it won't do, except that piece substitution re-spreads toms by register whenever the kits have different numbers of them, even when the target has the exact name ([ADR 0021](../decisions/0021-conversion-falls-back-within-a-family.md)). Every note of a family the target lacks waits for a `conversion` request.
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
- M3 is three PRs, in this order, and its gate follows the third ([ADR 0043](../decisions/0043-m3-is-three-prs-and-its-gate-follows-the-third.md)):
  1. `feat/engine`: the control vector, compiler, sampler, guards and `generic` mode, using the appendix defaults, with the property tests below.
  2. `feat/calibration`: `tools/infer_map.py`, `tools/calibrate.py` and `data/styles/`, which replace the appendix defaults.
  3. `feat/preview`: the preview through the IAC Driver, last because the owner has to enable it and try it.
- `tools/infer_map.py` prints pitch statistics for each folder of performed MIDI in `private/midi/`, so roles can be assigned. **A folder's notes can disagree with its library's map, so each needs verifying.** Exclude and report any folder that cannot be resolved.
- **Calibration, as built:**
  - `tools/infer_map.py` prints, for each folder of `private/midi/`, each pitch's notes and share, files, velocities, where it falls in the bar, and what a built-in kit reads it as, with the share of the folder's notes the kit reads and the pitches it leaves unmapped. `--map` reads a folder through any kit, and `--split` gives a report per subfolder. The tools are scripts in `tools/`, checked like `src/` and tested from `tests/` ([ADR 0058](../decisions/0058-tools-are-scripts-checked-like-src.md)).
  - Which kit reads each folder, and which folders are left out and why, is in the gitignored `private/data/midi-folders.toml`, and no tracked file names a folder ([ADR 0057](../decisions/0057-each-folder-s-kit-is-in-a-gitignored-file-under-private-data.md)). Every folder was checked against its library's map, and a folder that no built-in kit reads, or that copies another, is left out.
  - The tools read with the project's own reader and fit with numpy, so calibration adds no dependency. A scan of every folder takes about 7 seconds ([ADR 0056](../decisions/0056-the-calibration-tools-add-no-dependency.md)).
  - `tools/calibrate.py measure` reads each assigned folder's files through their kit with `normalize()` and cuts them into grooves of at most 16 bars. It measures around what a file leaves open: unmapped notes are left out and counted, ambiguous beats keep their best guess, and a file without a tempo has no timing ([ADR 0059](../decisions/0059-calibration-measures-files-in-windows-of-at-most-16-bars.md)). A groove with more than a fifth of its notes at one offset from the grid is held to it, and its timing is left out ([ADR 0060](../decisions/0060-a-groove-held-to-the-grid-is-left-out-of-timing.md)). Each groove gets the engine's statistics, with feel against the kick ([ADR 0061](../decisions/0061-calibration-measures-the-engine-s-statistics-with-feel-against-the-kick.md)). It prints the distribution of timing spread and the bands a few sets of cuts would make, and, apart, the timing of the folders left out, read with every pitch a drum of its own.
  - Measured on 2026-11-10, pooled over the assigned folders: of 3,183 grooves, 844 have performed timing, 1,386 are held to the grid, 411 have no tempo and 542 too few notes. The performed grooves' spread is 1.8 ms at the 5th percentile, 3.8 at the 25th, 6.2 at the median, 8.6 at the 75th and 14.4 at the 95th. Where `tight`, `medium` and `loose` are cut waits for the owner, as does fitting them.
- `tools/calibrate.py` computes attributes per groove of the performed MIDI in `private/midi/` (energy as velocity level, dynamic range, tightness, feel), then fits per-role distributions conditioned on those attributes, by metric level and tempo band. Writes `data/styles/*.toml`: `tight` (the default), `medium` and `loose` only, each pooled across all the performed MIDI by tightness band, so no committed file identifies a source ([ADR 0044](../decisions/0044-m3-ships-tight-medium-and-loose-styles-pooled-by-tightness.md)). Commit aggregate statistics only.
- **Engine, as built:**
  - The controls are layered pydantic models: a section's over the song's, over the style's defaults, with a JSON round trip ([ADR 0046](../decisions/0046-controls-are-layered-pydantic-models-with-a-json-round-trip.md)). The modules and the instrument seam, with `drums` and `generic`, are in [ADR 0045](../decisions/0045-the-engine-is-render-modules-behind-a-small-instrument-seam.md).
  - The only style is `tight`, Appendix A's placeholders with what it leaves out filled in, built in code with no `data/styles/` file until calibration ([ADR 0051](../decisions/0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md)). Each note's role comes from canonical families and the score, never a pitch, with three readings of Appendix A: a lone crash-family hit or one starting a run on a beat is an accent, only quarter-note rider hits alternate, and fills are capped at 2 bars ([ADR 0047](../decisions/0047-roles-come-from-canonical-families-and-the-score.md)).
  - Each section draws from its own stream, keyed by its first bar and take, and the song's drifts from their own, so a section rendered again leaves the others as they were. Turning `skip` on or off for a section can move the notes at and just after its boundaries by a step or a few ticks, as they then avoid its fixed notes, even in a section further on when the sections between lack those pitches and drums. Every other control change leaves the other sections byte-identical ([ADR 0049](../decisions/0049-each-section-draws-from-its-own-seeded-stream.md)). The guards hold every backend: the ±12 ms cap, 60% of the grid gap, reflection below 127, velocity ranges, soft below normal, and no repeat on a pitch or on a drum, with rules at section boundaries that never depend on another section's draws ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)).
  - Notes are written through the target kit by conversion's own fallback order, and only the drum track's notes change ([ADR 0048](../decisions/0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)). A controller-bound note keeps its controller value, and following and writing controllers wait for a map that gives them ([ADR 0053](../decisions/0053-a-controller-bound-note-keeps-its-controller-value.md)).
  - `human-o-matic render` writes a new MIDI file by a plan file and prints each section's statistics, with `analyze`'s answers and exit codes ([ADR 0054](../decisions/0054-human-o-matic-render-writes-a-new-midi-file-by-a-plan-and-prints-json.md)).
  - Exit, as tested on the placeholders: each control moves the statistic it mainly drives strictly the right way over five values and six seeds, and the property tests below pass with `hypothesis` ([ADR 0052](../decisions/0052-each-control-is-tested-against-the-statistic-it-mainly-drives.md)). At the defaults, timing spreads 3.1 ms over a 16-bar groove.
- **Exit:** raising each control moves its measured statistic in the right direction, and all property tests below pass. It is checked at the gate, after the third PR, on the calibrated styles.

### M4 MCP, skill and the main gate
- Build the MCP server and skill. Register with `claude mcp add human-o-matic -- uv run --directory ~/Projects/human-o-matic human-o-matic-mcp`, then test a full session in Claude Code.
- Build `analyze/facts.py`, each section's facts and its compact ASCII pattern, with the MCP tools that return them, such as `get_sections` ([ADR 0035](../decisions/0035-m2-finds-the-sections-and-their-facts-wait-for-m4.md)).
- `references/vocabulary.md` plus a check of about 30 answers against expected control ranges, run through a real agent session.
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
Ghosts, flams, rimshots and chokes, asked about as ordinary questions ("add ghost notes here?"). Ask the owner to confirm priority first.

## Verification

**Property tests** (`hypothesis`)
- Same session and seed produce byte-identical output. Re-rendering one section with new controls leaves every other section's notes byte-identical. The one exception is turning `skip` on or off for a section: the notes at and just after its boundaries, on the pitches and drums that cross them, can move by a step or a few ticks, because they then avoid its fixed notes, and so can a section further on when the sections between have none of those notes. Every other control change leaves the other sections byte-identical ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)).
- Note count is unchanged apart from notes the user chose to drop.
- Outside `skip` sections, input velocities and timing cannot influence output beyond hit type: two inputs with the same notes and types but different numbers render identically.
- Same-pitch notes never reorder, and each keeps at least 60% of its grid gap.
- Offsets stay within the cap at every tempo, including dense tempo maps.
- Velocities stay in 1 to 127. Consecutive velocities on one pitch, or on one drum, never repeat ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)).
- Soft-typed notes always land below normal-typed notes on the same drum in the same section.
- Rider flip rate stays in 0.70 to 0.85 over a large sample. Default-style unison spread stays at or below about 10 ms.
- Grace-to-main spacing is preserved. On the song's first tick, where a grace can't go before its main in the score, its main goes later to keep the gap, up to the cap, and a gap over 12 ms is shortened to it ([ADR 0050](../decisions/0050-guards-hold-every-backend-and-keep-each-section-independent.md)). `skip` sections come out unchanged. To another target kit, they keep their velocity and timing, and take the target's pitch and channel as conversion does, with the velocity moved into the target's range ([ADR 0048](../decisions/0048-a-render-writes-the-score-through-the-target-kit-into-the-drum-track.md)).

**End to end:** in Claude Code, run a real song through the full conversation, preview at least one section through the real kit, export, drag into the DAW, and have the owner listen.

## Do not

- Build a DAW bridge, web UI or built-in LLM in this version. The session format keeps them possible later.
- Pass note arrays through MCP.
- Train before M4 exists: without a baseline, "better" means nothing.
- Commit, copy out of or redistribute anything in `private/` ([ADR 0007](../decisions/0007-local-only-files-live-in-private.md)).
- Load user-supplied map files in this version: maps are built in ([ADR 0010](../decisions/0010-built-in-maps-only.md)).
- Special-case a library in the code: libraries differ only in their map data ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)).
- Let timing exceed performed magnitudes by default.
- Build piano or guitar logic now.

## Appendix A: Engine defaults

Placeholders until calibration replaces them, with the values they leave out in [ADR 0051](../decisions/0051-the-tight-style-s-placeholders-fill-in-what-appendix-a-leaves-out.md). Velocity anchors are at energy 1.0, 0.5 and 0.2; interpolate between them.

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

- **Rider alternation:** strong hits land with the snare, found by a vote across the run. Gap 4 to 14 from `dynamic_range`, noise SD about 2.5. **Must be probabilistic: flip rate 0.75 to 0.80.** Strict alternation sounds mechanical. For 8th and 16th patterns, alternate the quarter accents only.
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

`mido` and `python-rtmidi` (lossless I/O, preview), `numpy`, `scipy`, `pydantic`, `typer`, the official `mcp` Python SDK (check current docs, as the spec is moving), `pytest`, `hypothesis`, and PyTorch in M5 only. Each runtime dependency is added in the milestone that first needs it: `mido`, `numpy`, `pydantic` and `typer` in M1, none in M2, `python-rtmidi` in M3, with the preview ([ADR 0043](../decisions/0043-m3-is-three-prs-and-its-gate-follows-the-third.md)), and `mcp` in M4 ([ADR 0012](../decisions/0012-runtime-dependencies-arrive-with-their-milestone.md)). `scipy` comes with the first code that imports it ([ADR 0041](../decisions/0041-m2-adds-no-runtime-dependency.md)). `symusic`, once planned for scanning the performed MIDI, is not used: the project's own reader scans it in seconds ([ADR 0056](../decisions/0056-the-calibration-tools-add-no-dependency.md)).
