# human-o-matic: guided MIDI drum performance

> **Status:** Active. M0 is merged, and M1 is in progress.
> A living document. Each PR updates the progress table and the sections its work changes. Decisions are in [`../decisions/`](../decisions/).
> Last updated: 2026-11-08 (M1 on `feat/normalize`: MIDI I/O, tempo and the drum track choice built, ADRs 0013 to 0018 proposed).

Handoff document for an implementing agent with no prior context. The app is called **human-o-matic**: use `human-o-matic` for the repo, distribution, CLI and skill, and `human_o_matic` for the Python package.

## Progress

Milestones are done in order, and work stops at each gate ([`AGENTS.md`](../../AGENTS.md)).

| # | Milestone | Gate | Status |
|---|---|---|---|
| M0 | Setup | The checks pass on the scaffolding | Merged ([#1](https://github.com/thedevelobear/human-o-matic/pull/1)) |
| M1 | Normalize | The M1 exit tests | In progress |
| M2 | Sections | Boundary F1 of at least 0.70 on at least 10 tracks the owner has hand-labelled | Not started. Needs the owner's labelled tracks |
| M3 | Parametric engine and calibration | Each control moves its statistic the right way, and the property tests pass | Not started |
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

**Scope:** a normal, public app, built in this repo. Library MIDI is used for learning only: it is read locally, never copied into the repo, and nothing is redistributed.

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
| Performance engine | Parametric engine calibrated from library data first. A trained model is a separate experiment, adopted only if it wins a blind listening test |
| Training data | Kontakt library performances only |
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

**Guided beats black box, and the library data supports it.** Across 1,682 performed Kontakt library grooves:
- **Energy is not readable from note density.** Within a song, one drummer's snare level varies by a standard deviation of 8 to 20 velocity between grooves, yet its correlation with note density is only -0.06 to +0.30. Only density was tested, so another score feature might predict it, but asking the user is a direct way to get this information.
- **Dynamics are what change per section; timing mostly is not.** Within a song, timing spread moves by only 0.3 to 3.1 ms between grooves, while between drummers it runs from 3 to 12 ms. So set tightness or drummer style once per song, and steer dynamics per section.
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

## Library data findings

Measured with a read-only stdlib script (not saved; M3 rebuilds it). "Performed" means under 70% of notes sit exactly on a 32nd, 8th-triplet or 16th-triplet grid, which proves a file is not quantized, not that it was played unedited. Kick and snare were assumed to be pitches 36 and 38 in the packs measured, and riders were detected heuristically. Treat all of this as design input until M3 verifies the maps.

**Dataset:** 1,682 performed files, 246,130 notes, 7.8 hours (for scale, [Google's Groove dataset](https://magenta.withgoogle.com/datasets/groove) is 13.6 hours with no metal among its genres). Files are short: median 8 bars, p90 16, max 48, only 10 reach 32 bars. A model can learn local groove from this, but not song-long dynamics or slow drift, so those stay explicit. Filenames mark groove versus fill and some styles, but explicit section labels are rare (about 125 of 3,313 files, many in one largely quantized pack). Section conditioning must therefore use attributes computed from the performances, not labels.

| Measure | Range across drummers |
|---|---|
| Timing SD at quarter positions | 3 to 12 ms |
| Snare minus kick, mean | -0.3 to +2.4 ms (typically about +1) |
| Rider minus kick, mean | -0.6 to +2.7 ms |
| Kick hits at velocity 127 | 0 to 99% |
| On-beat snare hits at 127 | 0 to 92% |
| Rider mean velocity | 107 to 123 |
| Rider with snare minus without | -9 to +14, usually +4 to +14 |
| Rider loud/soft direction flips per hit (random 0.67, strict 1.0) | 0.67 to 0.83 |

**Hit types are not recoverable from position.** Share of snare hits under velocity 60: quarter 10%, 8th 34%, 16th 51%, off-grid 49%. This is why hit type must survive from the input or come from the user.

**Quantizing performances is not trivial.** Best per-bar grid: 16th 75%, 8th triplet 10.5%, 16th triplet 7.8%, 32nd 7%. In 17% of bars a note still sits over 20 ms from the chosen grid, and 1.1% of consecutive snare pairs are under 45 ms apart (flams and drags). A per-bar grid is not enough.

## Product flow

```
Agent: opens song.mid (from IOF to Sleep Token II)
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
    midi/io.py            lossless read/write (mido): notes and raw events at absolute ticks, written at 960 PPQ or more
    midi/tempo.py         tick, beat and ms conversions; tempo and time signature maps
    midi/tracks.py        track summaries and the drum track choice
    maps/                 schema (library, kit, articulation), canonical vocabulary, conversion with fallbacks
    normalize/            per-beat grid inference, flam/drag detection, hit types, ambiguity list
    analyze/sections.py   bar features, similarity matrix, novelty peaks, repeat groups
    analyze/facts.py      per-section facts and compact ASCII pattern for the agent
    controls.py           pydantic ControlVector, SectionPlan, SessionPlan
    render/compiler.py    controls + style into per-role parameters
    render/engine.py      seeded sampling
    render/guards.py      limits that apply to every backend
    render/backends/      parametric.py; neural.py in M5 only
    instruments/          base protocol, drums.py, generic.py
    session.py            session JSON on disk: sections, answers, controls, seed
    preview.py            MIDI playback to a virtual port
    mcp_server.py         thin MCP layer over the above
    cli.py                analyze and headless render, for tests and scripting
  skills/human-o-matic/SKILL.md       question policy and workflow
  skills/human-o-matic/references/vocabulary.md
  data/maps/*.toml                    built-in maps, one library per file: its kits and their articulations
  data/styles/*.toml                  generated by calibration
  tools/                              infer_map, calibrate, make_ab, train
  typings/mido/                       local type stubs for the part of mido the code uses
  tests/
```

**Pipeline:** read, map, normalize to a flat quantized score with hit types, detect sections, collect controls, compile, sample, guards, write.

**Render determinism:** derive one random stream per section with `numpy.random.SeedSequence`, so re-rendering section 5 leaves sections 1 to 4 byte-identical. Long-memory drift is generated once for the whole song and only changes with the song seed. The same session JSON and seed always produce the same file.

**Instrument seam:** `Instrument` provides normalization rules, hit typing, facts, a control schema and a compiler. `drums` is the only real implementation. A small `generic` mode (dynamics and timing without roles) proves the seam works. Piano and guitar need their own analysis, so do not design for them further yet.

### MCP tools

Tools take IDs and file paths and return compact JSON. **Never pass note arrays:** a thousand notes through tool calls would make the model read and rewrite them all, slowly and with errors.

| Tool | Purpose |
|---|---|
| `list_maps` | The built-in libraries and their kits |
| `open_session(midi_path, from_map, to_map, instrument, bpm?, tempo_map?, track?)` | Normalize and detect sections. `from_map` and `to_map` name a built-in library and kit, never a map file ([ADR 0010](../decisions/0010-built-in-maps-only.md)). Returns a session ID, summary, and anything needing a decision |
| `get_sections(session_id)` | Bars, repeat group, facts, ASCII pattern, plus suggested questions and a guess with confidence |
| `update_sections(session_id, ops)` | Split, merge, move boundaries, rename |
| `set_hit_types(session_id, decisions)` | Confirm soft notes and resolve ambiguous bars |
| `set_style(session_id, style, seed?)` | Song-wide drummer style and tightness |
| `set_section_controls(session_id, section_ids, controls, note)` | Validate and store. Returns plain-language expected results, such as "snare about 118 to 127, timing spread about 3 ms", and any clamping |
| `render(session_id, section_ids?, take?)` | Sample, returning measured stats per section |
| `preview(session_id, section_ids?, take?, port?)` / `stop_preview` | Non-blocking playback through a virtual MIDI port |
| `export(session_id, output_path, overwrite?)` | Write MIDI and a report. Never overwrite the input; refuse existing files unless `overwrite` is set |

**Preview:** the sample library determines how velocities sound, so preview through the user's real kit: enable the macOS IAC Driver, route it to the DAW track, and play with `mido` and `python-rtmidi`. This route was not verified during research, so test it in M3. If it fails, fall back to exporting and dragging into the DAW.

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
2. **One song-wide question round,** at most three: overall drummer or tightness, plus anything else that applies everywhere.
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
- The scaffolding is the toolchain ([ADR 0001](../decisions/0001-python-312-with-uv-ruff-pyright-and-pytest.md)), the docs, the orchestrator, developer and qa agents ([ADR 0005](../decisions/0005-orchestrated-agents.md)) and CI. Library data stays out of the repo ([ADR 0007](../decisions/0007-library-data-stays-out-of-the-repo.md)).

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
  - Unclear input is a `DecisionRequest`, raised as `DecisionRequired` ([ADR 0015](../decisions/0015-unclear-input-is-a-decision-request.md)). Tempo and time signatures follow [ADR 0016](../decisions/0016-tempo-and-time-signatures.md): a given `bpm` replaces the file's tempo, and a missing time signature is 4/4, flagged as assumed. The drums are one whole track ([ADR 0017](../decisions/0017-the-drums-are-one-whole-track.md)). mido is typed by a local stub ([ADR 0018](../decisions/0018-mido-is-typed-by-a-local-stub.md)).
  - All 3,313 library files read, and round-trip with every message unchanged apart from note-ons at velocity 0, written as note-offs. 901 (Drum Lab) have no tempo event, 96 PPQ and the same time signature twice at tick 0. 1,657 are format 0, 160 change time signature, and every file has exactly one track with notes. No file has more than 47 tempo events, so dense tempo maps are tested on files built in code.
  - Still open: the `tempo_map` argument and its format.
- **Quantizer:** choose a grid per beat among 16th, 8th triplet, 16th triplet and 32nd, with a penalty for complex grids. Treat hits on one drum under about 45 ms apart as grace plus main, and keep them linked. Merge near-simultaneous limbs onto one grid point. Report ambiguous bars instead of guessing silently.
- **Hit types:** cluster velocities per drum family. Clear clusters become soft, normal or accent. Flat input gets inferred types marked low confidence, so the agent asks.
- **Maps:** library-neutral, for most modern drum libraries, and no library is special in the code ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)).
  - A map file is one library and its kits. Each kit lists its articulations, each with its MIDI notes, velocity behavior, CC behavior, channel, and a source and confidence.
  - Canonical articulation names act as the pivot, because General MIDI has no articulations and the same number differs by library: note 39 is a variant snare hit in IOF Drummer but a flam in Sleep Token II. Use `family.articulation` names such as `snare.center`, `hat.closed.tip`, `crash.1.choke`. Conversion tries the exact name, then drops the variant, then the family default, and reports every inexact step.
  - M1 reads and writes notes, channels and velocity ranges, and output stays inside an articulation's velocity range. CC behavior is stored, validated and preserved, and CC-driven articulations are resolved in M3 ([ADR 0009](../decisions/0009-m1-resolves-notes-channels-and-velocity-ranges.md)).
  - Maps are built in, with no user-supplied map files ([ADR 0010](../decisions/0010-built-in-maps-only.md)). M1 ships General MIDI plus maps built from the sources in the appendix ([ADR 0011](../decisions/0011-m1-maps-from-general-midi-and-the-available-map-files.md)). **Build maps from those sources, never from memory, and cover every slot.**
- **Exit:**
  - Add known jitter to quantized library files and recover at least 99% of grid positions.
  - Round trips keep all notes and non-note events.
  - Converting between any two shipped maps never moves a hit to a different drum family. Where the target lacks an articulation, the fallback is the exact name, then the name without its variant, then the family default, and every inexact step is reported. A hit whose family the target lacks is a decision request. Tests build any other map they need in code, in `tmp_path`, and never read the vendor files.

### M2 Sections
- Bar features: per-family onset patterns on the grid, density, cymbal type, fill flag.
- Build a self-similarity matrix, take [novelty peaks](https://arxiv.org/pdf/2309.02243) at 2 to 8 bar scales, prefer 4, 8 and 16 bar lengths, and cluster repeats into groups. SMF markers win when present.
- Have the owner supply and hand-label at least 10 drum tracks.
- **Exit:** boundary F1 within ±1 bar of at least 0.70. For scale, a [2025 CNN reached 0.77](https://arxiv.org/abs/2509.16566) on 6,134 multi-track MIDI files, with code released, if heuristics fall short. It is unclear whether it uses drums.

### M3 Parametric engine and calibration
- Implement the control vector, compiler, sampler, guards, `generic` mode and preview, using the appendix defaults.
- `tools/infer_map.py` prints per-pack pitch statistics so roles can be assigned. **Maps differ between packs and need verifying:** some GGD folders look General-MIDI-like (42/46 hats, 49/57 crashes, 51 ride) while IOF's GGD map file says hats are 49 to 55; Modern & Massive has pitch 74 at 20% of notes and velocity 76; Sleep Token's Groove Pack uses pitches 1, 2, 14, 3, 41 that do not match the library's default map. Exclude and report any pack that cannot be resolved.
- `tools/calibrate.py` computes attributes per groove (energy as velocity level, dynamic range, tightness, feel), then fits per-role distributions conditioned on those attributes, by metric level and tempo band. Writes `data/styles/*.toml`: `tight` (default), `medium`, `loose` and named drummers. Commit aggregate statistics only.
- **Exit:** raising each control moves its measured statistic in the right direction, and all property tests below pass.

### M4 MCP, skill and the main gate
- Build the MCP server and skill. Register with `claude mcp add human-o-matic -- uv run --directory ~/Projects/human-o-matic human-o-matic-mcp`, then test a full session in Claude Code.
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
- **Data:** performed files normalized through M3's maps. Split by song and hold out one whole drummer. Many files share a song, so a file-level split would leak.
- **Task:** flat quantized score plus hit types and control vector, to per-note timing offset and velocity. Controls come from the target performance's own attributes, so training is self-supervised, as in MuseCoco.
- **Output must be sampled** (for example a mixture density head). Predicting the mean flattens dynamics and recreates the robotic sound.
- **Model:** small sequence model, up to about 500k parameters. PyTorch on MPS. It plugs in as `backends/neural.py`. Song-level drift stays explicit, and guards still apply.
- **Gate:** must follow the controls (M3's exit test) and beat the parametric engine in a blind test with at least six trial pairs. Otherwise keep the engine and archive the experiment, which is a valid result.

### M6 Added notes (opt-in)
Ghosts, flams, rimshots and chokes, asked about as ordinary questions ("add ghost notes here?"). Ask the owner to confirm priority first.

## Verification

**Property tests** (`hypothesis`)
- Same session and seed produce byte-identical output. Re-rendering one section with new controls leaves every other section's notes byte-identical.
- Note count is unchanged apart from notes the user chose to drop.
- Outside `skip` sections, input velocities and timing cannot influence output beyond hit type: two inputs with the same notes and types but different numbers render identically.
- Same-pitch notes never reorder, and each keeps at least 60% of its grid gap.
- Offsets stay within the cap at every tempo, including dense tempo maps.
- Velocities stay in 1 to 127. Consecutive velocities on one pitch never repeat.
- Soft-typed notes always land below normal-typed notes on the same drum in the same section.
- Rider flip rate stays in 0.70 to 0.85 over a large sample. Default-style unison spread stays at or below about 10 ms.
- Grace-to-main spacing is preserved. `skip` sections come out unchanged.

**End to end:** in Claude Code, run a real song through the full conversation, preview at least one section through the real kit, export, drag into the DAW, and have the owner listen.

## Do not

- Build a DAW bridge, web UI or built-in LLM in this version. The session format keeps them possible later.
- Pass note arrays through MCP.
- Train before M4 exists: without a baseline, "better" means nothing.
- Commit or redistribute library MIDI.
- Load user-supplied map files in this version: maps are built in ([ADR 0010](../decisions/0010-built-in-maps-only.md)).
- Special-case a library in the code: libraries differ only in their map data ([ADR 0008](../decisions/0008-library-neutral-drum-maps.md)).
- Let timing exceed performed magnitudes by default.
- Build piano or guitar logic now.

## Appendix A: Engine defaults

Placeholders until M3 replaces them. Velocity anchors are at energy 1.0, 0.5 and 0.2; interpolate between them.

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
- **Drift:** sum of slow processes at time constants of 16, 64 and 256 beats, total SD about 2.5, for long memory. Library loops are too short to fit this, so it stays modelled.
- **Shared offset per onset:** SD about 2.2, scaled by tightness.
- **Limb offsets:** snare about +1, riders about +0.7, others 0, jitter SD 1.8 to 3 clipped to ±4, then replaced by M3's values.
- **Overall spread:** about 3 to 4 ms at the default `tight` style. Cap ±12 ms.
- **Feel:** up to about +6 ms laid back (with a loudness increase on snare) and about -3 ms pushed.
- **Guards:** each same-pitch note keeps at least 60% of its grid gap. Trim durations so same-pitch notes never overlap. Clamp at tick 0 and report it. Grace notes take their main note's offset.

## Appendix B: Data sources

**Map sources** (the data the maps are built from, never their model: [ADR 0011](../decisions/0011-m1-maps-from-general-midi-and-the-available-map-files.md))
- General MIDI Level 1 percussion key map (MMA RP-003), notes 35 to 81 on channel 10, a published standard, for the General MIDI map.
- IOF Drummer 6: `~/Library/Application Support/IOF Sounds/IOF Drummer 6/User Presets/MAP/*.map`, 13 files including GM, EZdrummer 3, Superior Drummer 3, Addictive Drums 2, SSD5, GGD Modern & Massive and Abbey Road. JSON where slot `RemapCBnData`, for slots 1 to 63, is one IOF articulation and the value is note + 2 (value 1 means unset). Every file uses the same slots, so each one maps the slots for one library. `DEFAULT.map` is IOF's own map. Slot names are not in the files, so each slot's canonical articulation is proposed with low confidence, and raised to high once the owner confirms it in the plugin.
- MixWave Sleep Token II default map: `~/Music/Templates/Sleep Token Songwriting Template/Cubase/_Cubase Drum Map/MixWave Sleep Token - II.drm`, a Cubase drum map that names its pitches.
- Format reference: [Drum-Mapper](https://github.com/insomnimus/drum-mapper) (MIT).

**Library MIDI** (read in place, never copy)
- `/Users/Shared/GetGood Drums - P V Matt Halpern Signature Pack/MIDIFiles` (1,935 files; despite the name also Anup, Krimh, Kolstad, Sandnes, Richardson, Rudi and Free Vols 1/2)
- `/Users/Shared/Bogren Digital - Krimh Drums/MIDIfiles` (103, all performed)
- `/Users/Shared/GetGood Drums - Modern and Massive Pack/Modern & Massive/MIDIFiles` (31)
- `/Users/jakubszewczyk/Documents/SleepTokenII/MIDI Files` (172)
- `/Users/Shared/SoundBlind Drums - Counterkit/MIDI` (159, mostly quantized, useful for quantizer tests; has the clearest section labels)
- `/Users/Shared/Drum Lab Library/MIDI Files` (901, mostly quantized, useful for quantizer tests)
- `/Users/Shared/Krimh Drums Free/MIDIfiles` (12)

**Libraries:** `mido` and `python-rtmidi` (lossless I/O, preview), [`symusic`](https://symusic.readthedocs.io/en/latest/introduction.html) (fast batch scanning of the dataset; its speed claims are the maintainers' own), `numpy`, `scipy`, `pydantic`, `typer`, the official `mcp` Python SDK (check current docs, as the spec is moving), `pytest`, `hypothesis`, and PyTorch in M5 only. Each runtime dependency is added in the milestone that first needs it: `mido`, `numpy`, `pydantic` and `typer` in M1, `scipy` in M2, `python-rtmidi` and `symusic` in M3, and `mcp` in M4 ([ADR 0012](../decisions/0012-runtime-dependencies-arrive-with-their-milestone.md)).
