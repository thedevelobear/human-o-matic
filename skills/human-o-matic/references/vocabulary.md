# Vocabulary: answers to controls

What a producer's answers mean as human-o-matic's controls. Each row is an answer and the controls it sets, each as a starting point and, in brackets, the range that still reads the answer the same way: `0.95 [0.85, 1]` is 0.95, and anything from 0.85 to 1 keeps the answer's meaning.

**These values are starting points, not yet heard.** Apart from the first four rows, which the plan gives, they were drafted without listening, and the owner refines them by ear. When the user says a result sounds wrong, believe the user over the table.

## How to read a row

- A row sets the controls it fills in, and only those. Leave the others unset, so they come from the song's controls and then the style's defaults: `energy`, `groove`, `dynamic_range`, `fill_intensity` and `ghost_level` 0.5, `tightness` 0.75, `feel` 0, `arc` `steady`, `skip` false. Every style has these defaults.
- Rows are written for a song whose own controls are unset. Where the user has set a control for the whole song, such as its tightness, move a section from the song's value by the row's difference from the default, and leave it unset where the row gives the default. A bridge at tightness 0.6 is 0.15 looser than the song, so in a song at 0.9 it is 0.75.
- `style` and the song's `tightness` go to `set_style`. Every other control goes to `set_section_controls`, with `section_ids` for the sections the answer is about, or without them for the whole song.
- Blend rows when an answer mixes them: "chorus, but laid back" is the chorus row with the laid-back row's `feel`. Move within a range for the user's emphasis: "really full power" is the top of it.
- A section's name is not a control: "the drop" is a big section, not `arc: drop`, which only makes the energy fall across a section.
- Nothing adds notes. "More ghost notes" plays the soft notes the song has louder, which is `ghost_level`.
- "Your call" sets nothing new: use the row for what the section is, when the user named it or confirmed it in the section table, and otherwise keep the song's controls, or for a repeat, its group's. Say which.

## In words

What each control does, and the words to echo it with.

| Control | Low | High |
|---|---|---|
| `energy`, 0 to 1 | quiet, held back | full power: from 0.85, kick and backbeats about 118 to 127 |
| `groove`, 0 to 1 | steady and even, little light and shade | groovy: accents and soft notes stand out, the ride's strong and weak hits apart |
| `dynamic_range`, 0 to 1 | every hit alike | wide: strong and weak hits far apart |
| `tightness`, 0 to 1 | looser timing, within the style | tighter timing, within the style |
| `feel`, -1 to +1 | pushed, on top of the beat | laid back, behind the beat, with the snare a little louder |
| `arc` | `drop`: the energy falls across the section | `build`: it rises; `steady` keeps it level |
| `fill_intensity`, 0 to 1 | fills stay down | fills build hard |
| `ghost_level`, 0 to 1 | soft notes tucked away | soft notes present |
| `skip` | | `true`: the section stays exactly as it came in |

The styles are `tight`, the default, `medium` and `loose`. They differ in how far the timing spreads and how far `feel` moves the snare and riders, and play the same velocities.

## Answers

| Answer | energy | groove | dynamic_range | tightness | feel | ghost_level | Also |
|---|---|---|---|---|---|---|---|
| "breakdown, full power" | 0.95 [0.85, 1] | 0.2 [0.1, 0.35] | 0.2 [0.1, 0.35] | 0.8 [0.75, 0.9] | 0 [-0.1, 0.1] | 0.2 [0.1, 0.35] | |
| "bridge, low energy, high groove" | 0.35 [0.25, 0.45] | 0.85 [0.75, 0.95] | 0.7 [0.6, 0.85] | 0.6 [0.5, 0.7] | +0.2 [0.1, 0.35] | 0.7 [0.6, 0.85] | |
| "big last chorus" | 0.9 [0.85, 1] | 0.5 [0.4, 0.6] | 0.4 [0.3, 0.5] | 0.75 [0.7, 0.85] | 0 [-0.1, 0.1] | 0.3 [0.2, 0.4] | |
| "verse, holding back, building" | 0.5 [0.4, 0.6] | 0.6 [0.5, 0.7] | 0.5 [0.4, 0.6] | 0.75 [0.7, 0.8] | +0.1 [0, 0.2] | 0.5 [0.4, 0.6] | arc: build |
| "quiet intro" | 0.3 [0.2, 0.4] | 0.5 [0.4, 0.6] | 0.6 [0.5, 0.7] | 0.75 [0.7, 0.8] | 0 [-0.1, 0.1] | 0.4 [0.3, 0.5] | |
| "verse, steady and solid" | 0.55 [0.45, 0.65] | 0.4 [0.3, 0.5] | 0.45 [0.35, 0.55] | 0.75 [0.7, 0.85] | 0 [-0.1, 0.1] | 0.45 [0.35, 0.55] | |
| "pre-chorus, lifting into the chorus" | 0.65 [0.55, 0.75] | 0.5 [0.4, 0.6] | 0.45 [0.35, 0.55] | 0.75 [0.7, 0.85] | 0 [-0.1, 0.1] | 0.4 [0.3, 0.5] | arc: build |
| "chorus, big and open" | 0.8 [0.7, 0.9] | 0.5 [0.4, 0.6] | 0.45 [0.35, 0.55] | 0.75 [0.7, 0.85] | 0 [-0.1, 0.1] | 0.35 [0.25, 0.45] | |
| "halftime, heavy" | 0.8 [0.7, 0.9] | 0.4 [0.3, 0.5] | 0.35 [0.25, 0.45] | 0.75 [0.7, 0.85] | +0.2 [0.1, 0.35] | 0.3 [0.2, 0.4] | |
| "the drop, everything hits" | 0.95 [0.85, 1] | 0.3 [0.2, 0.4] | 0.3 [0.2, 0.4] | 0.8 [0.75, 0.9] | 0 [-0.1, 0.1] | 0.25 [0.15, 0.35] | |
| "outro, winding down" | 0.45 [0.35, 0.55] | 0.6 [0.5, 0.7] | 0.6 [0.5, 0.7] | 0.7 [0.6, 0.8] | +0.1 [0, 0.2] | 0.5 [0.4, 0.6] | arc: drop |
| "full power" | 0.95 [0.85, 1] | | | | | | |
| "fairly hard, not all out" | 0.7 [0.6, 0.8] | | | | | | |
| "soft notes more present" | | | | | | 0.75 [0.65, 0.9] | |
| "soft notes tucked away" | | | | | | 0.25 [0.1, 0.35] | |
| "steady and even" | | 0.3 [0.2, 0.4] | 0.3 [0.2, 0.4] | | | | |
| "more groove, more light and shade" | | 0.75 [0.65, 0.85] | 0.7 [0.6, 0.8] | | | | |
| "fill, big into the chorus" | | | | | | | fill_intensity: 0.85 [0.7, 1] |
| "small fill, just a turnaround" | | | | | | | fill_intensity: 0.3 [0.15, 0.4] |
| "laid back" | | | | | +0.4 [0.25, 0.6] | | |
| "way behind the beat, lazy" | | | | | +0.8 [0.65, 1] | | |
| "pushing, on top of the beat" | | | | | -0.4 [-0.6, -0.25] | | |
| "building" | | | | | | | arc: build |
| "dropping down towards the end" | | | | | | | arc: drop |
| "tight, modern metal" | | | | 0.85 [0.75, 0.95] | | | style: tight |
| "loose, like a live drummer" | | | | 0.7 [0.55, 0.8] | | | style: loose |
| "somewhere in between" | | | | 0.75 [0.7, 0.8] | | | style: medium |
| "machine tight, nearly quantized" | | | | 1 [0.9, 1] | | | style: tight |
| "your call" | | | | | | | |
| "leave this alone, it's finished" | | | | | | | skip: true |

The four answers about the drummer, from "tight, modern metal" on, are song-wide: `set_style` takes their `style` and `tightness`.

## Refinements

A refinement changes controls already set, by a small step from their current values: about 0.1 for "a bit" and 0.2 for "a lot". Here each cell is the change, with its range.

| Answer | energy | groove | dynamic_range | tightness | feel | ghost_level | Also |
|---|---|---|---|---|---|---|---|
| "a bit harder" | +0.1 [+0.05, +0.15] | | | | | | |
| "a little softer" | -0.1 [-0.15, -0.05] | | | | | | |
| "a touch tighter" | | | | +0.1 [+0.05, +0.15] | | | |
