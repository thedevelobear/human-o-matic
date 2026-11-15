// The page's pure modules for its forms and words: each decision request's form and the answer
// its values give, the check batch's one call, Fine-tune's fields, the section edits, the kits
// as choices, the review's lines and the download's name (the website plan's PR 3). The
// requests are in the form the engine gives them, as `decisions` in a reply.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ADD_NOTES,
  GROUP_CONTROLS,
  REQUESTS,
  SONG_CONTROLS,
  batch,
  capital,
  editBars,
  fineTune,
  fixed,
  form,
  kitOptions,
  mostRamp,
  sectionEdit,
  touchedControls,
  words,
} from "../../src/human_o_matic/web/static/js/forms.js";
import {
  barsLabel,
  conversionLines,
  creativeLines,
  downloadName,
} from "../../src/human_o_matic/web/static/js/review.js";

const REQUEST = {
  tempo: { kind: "tempo", message: "What is the song's tempo in BPM?", answer_with: ["bpm"] },
  drum_track: {
    kind: "drum_track",
    message: "Which track holds the drums?",
    answer_with: ["track"],
    options: [
      { value: 1, label: 'Track 1 "Bass": 412 notes on channel 3', details: {} },
      { value: 2, label: 'Track 2 "Kit": 990 notes on channel 1', details: {} },
    ],
  },
  hit_types: {
    kind: "hit_types",
    message: "Hit types read from the velocities: ... Do these look right?",
    answer_with: ["hit_types"],
    details: {
      families: [
        {
          family: "snare",
          reason: "clusters",
          confidence: "high",
          counts: { soft: 32, normal: 138, accent: 12 },
          velocities: { soft: [20, 35], normal: [96, 110], accent: [120, 127] },
        },
        {
          family: "kick",
          reason: "one_group",
          confidence: "low",
          counts: { normal: 573 },
          velocities: { normal: [90, 120] },
        },
      ],
    },
  },
  ambiguous_bars: {
    kind: "ambiguous_bars",
    message: "2 bars have beats whose grid is unclear ...",
    answer_with: ["grids"],
    details: {
      bars: [
        {
          bar: 32,
          beats: [
            { beat: 1, grid: "16th", alternatives: ["8th_triplet"], largest_offset_ms: 21.4 },
            { beat: 3, grid: "32nd", alternatives: [], largest_offset_ms: 18.6 },
          ],
        },
        { bar: 40, beats: [{ beat: 0, grid: "16th_triplet", alternatives: ["16th"] }] },
      ],
    },
  },
  unmapped_notes: {
    kind: "unmapped_notes",
    message: "3 notes on 2 pitches have no articulation in General MIDI ...",
    answer_with: ["unmapped", "from_map"],
    details: {
      kit: "gm/default",
      notes: [
        { pitch: 20, channels: [9], count: 2, positions: [[4, 0], [12, 2]] },
        { pitch: 99, channels: [9], count: 1, positions: [[7, 1.5]] },
      ],
    },
  },
  conversion: {
    kind: "conversion",
    message: "cowbell.hit, bar 1, can't be converted ...",
    answer_with: ["substitutions"],
    options: [
      { value: "perc.1.hit", label: "Play it as perc.1.hit, note 77" },
      { value: "drop", label: "Leave it out" },
    ],
    details: { source: "cowbell.hit", reason: "family", count: 1, positions: [[0, 0]] },
  },
};

/** Every field of a form, the groups' own included. */
function* fieldsOf(fields) {
  for (const field of fields) {
    yield field;
    if (field.type === "group") {
      yield* fieldsOf(field.fields);
    }
  }
}

test("every request kind the engine gives has a form whose every input has a label", () => {
  assert.deepEqual(Object.keys(REQUEST), Object.keys(REQUESTS));
  for (const [kind, request] of Object.entries(REQUEST)) {
    const fields = [...fieldsOf(form(request, { articulations: ["kick.hit"] }))];

    assert.ok(fields.length, kind);
    for (const field of fields) {
      assert.ok(field.type === "group" ? field.legend : field.label, `${kind}: ${field.name}`);
      if (!["group", "list", "button"].includes(field.type)) {
        assert.ok(field.name, kind);
      }
    }
  }
});

test("a kind the page doesn't know shows its options and answers nothing", () => {
  const request = {
    kind: "a_new_kind",
    message: "Something new to ask?",
    options: [
      { value: 1, label: "One way" },
      { value: 2, label: "Another" },
    ],
  };

  assert.deepEqual(form(request), [
    { type: "list", label: "Its options", items: ["One way", "Another"] },
  ]);
  assert.deepEqual(form({ ...request, options: [] }), []);
  assert.deepEqual(batch([request], {}), { call: "set_hit_types", args: {} });
});

test("a tempo and a drum track are answered by opening the song again", () => {
  assert.deepEqual(batch([REQUEST.tempo], { bpm: "128.5" }), {
    call: "open_session",
    args: { bpm: 128.5 },
  });
  assert.deepEqual(batch([REQUEST.drum_track], { track: "2" }), {
    call: "open_session",
    args: { track: 2 },
  });
  assert.deepEqual(
    form(REQUEST.drum_track)[0].options.map(({ value }) => value),
    ["1", "2"],
  );
});

test("the hit types start between the groups found, and all normal takes every bound out", () => {
  const [snare, kick] = form(REQUEST.hit_types);

  assert.deepEqual(
    snare.fields.map(({ name, value }) => [name, value]),
    [
      ["hit_types.snare.soft_below", "36"],
      ["hit_types.snare.accent_from", "120"],
      ["hit_types.snare.normal", undefined],
    ],
  );
  assert.equal(snare.hint, "32 soft, velocity 20 to 35; 138 normal, velocity 96 to 110; 12 accent, velocity 120 to 127");
  assert.deepEqual(
    kick.fields.map(({ value }) => value),
    ["", "", undefined],
  );
  const values = {
    "hit_types.snare.soft_below": "40",
    "hit_types.snare.accent_from": "",
    "hit_types.snare.normal": false,
    "hit_types.kick.soft_below": "60",
    "hit_types.kick.accent_from": "115",
    "hit_types.kick.normal": true,
  };
  assert.deepEqual(batch([REQUEST.hit_types], values), {
    call: "set_hit_types",
    args: { hit_types: { snare: { soft_below: 40 }, kick: {} } },
  });
});

test("each unclear beat offers its guess and alternatives, from bar and beat 1", () => {
  const [bar33, bar41] = form(REQUEST.ambiguous_bars);

  assert.equal(bar33.legend, "Bar 33");
  assert.deepEqual(
    bar33.fields.map(({ name, label, value, options, hint }) => [
      name,
      label,
      value,
      options.map((option) => option.label),
      hint,
    ]),
    [
      ["grids.32,1", "Beat 2", "16th", ["16th", "8th triplet"], ""],
      ["grids.32,3", "Beat 4", "32nd", ["32nd"], "a note 19 ms off its grid"],
    ],
  );
  assert.equal(bar41.fields[0].label, "Beat 1");
  const values = { "grids.32,1": "8th_triplet", "grids.32,3": "32nd", "grids.40,0": "16th" };
  assert.deepEqual(batch([REQUEST.ambiguous_bars], values).args, {
    grids: { "32,1": "8th_triplet", "32,3": "32nd", "40,0": "16th" },
  });
});

test("an unmapped pitch is played as a source kit's articulation or left out, or another kit read", () => {
  const fields = form(REQUEST.unmapped_notes, { articulations: ["kick.hit", "tom.1.hit"] });

  assert.deepEqual(
    fields[0].options.map(({ value }) => value),
    ["", "kick.hit", "tom.1.hit", "drop"],
  );
  assert.equal(fields[0].required, true);
  assert.equal(fields[0].hint, "2 notes from bar 5");
  assert.equal(fields[1].hint, "1 note from bar 8");
  assert.deepEqual(fields.at(-1), {
    type: "button",
    name: "kits",
    label: "Read the file with another kit",
  });
  assert.deepEqual(
    batch([REQUEST.unmapped_notes], { "unmapped.20": "tom.1.hit", "unmapped.99": "drop" }).args,
    { unmapped: { 20: "tom.1.hit", 99: "drop" } },
  );
});

test("a conversion offers the request's options, the first chosen", () => {
  const [field] = form(REQUEST.conversion);

  assert.equal(field.type, "radio");
  assert.equal(field.value, "perc.1.hit");
  assert.equal(field.label, "1 note of cowbell.hit");
  assert.deepEqual(
    batch([REQUEST.conversion], { "substitutions.cowbell.hit": "drop" }).args,
    { substitutions: { "cowbell.hit": "drop" } },
  );
});

test("the check batch answers every request of set_hit_types in one call", () => {
  const values = {
    "hit_types.snare.normal": true,
    "hit_types.kick.normal": true,
    "grids.32,1": "16th",
    "grids.32,3": "32nd",
    "grids.40,0": "16th",
    "unmapped.20": "drop",
    "unmapped.99": "drop",
    "substitutions.cowbell.hit": "perc.1.hit",
  };
  const requests = ["hit_types", "ambiguous_bars", "unmapped_notes", "conversion"].map(
    (kind) => REQUEST[kind],
  );

  const { call, args } = batch(requests, values);

  assert.equal(call, "set_hit_types");
  assert.deepEqual(Object.keys(args), ["hit_types", "grids", "unmapped", "substitutions"]);
  assert.deepEqual(args.hit_types, { snare: {}, kick: {} });
});

test("Fine-tune starts each control at its resolved value, a ramp up to what the section allows", () => {
  const resolved = {
    style: "medium",
    energy: 0.8,
    groove: 0.5,
    dynamic_range: 0.5,
    tightness: 0.75,
    feel: -0.2,
    arc: "build",
    fill_intensity: 0.5,
    ghost_level: 0.35,
    ramp: 6,
    skip: false,
    creative: true,
  };

  const song = fineTune(SONG_CONTROLS, resolved);
  const group = fineTune(GROUP_CONTROLS, resolved, mostRamp(9));

  assert.deepEqual(
    song.map(({ type, name, value }) => [type, name, value]),
    [
      ["segments", "style", "medium"],
      ["range", "tightness", "0.75"],
      ["range", "feel", "-0.2"],
    ],
  );
  const by = Object.fromEntries(group.map((field) => [field.name, field]));
  assert.deepEqual([by.feel.min, by.feel.max, by.energy.min, by.energy.max], [-1, 1, 0, 1]);
  assert.deepEqual([by.ramp.max, by.ramp.step, by.ramp.value], [4, 1, "4"]);
  assert.deepEqual([by.arc.type, by.arc.value], ["segments", "build"]);
  assert.deepEqual(
    [by.skip.type, by.skip.checked, by.creative.checked, by.creative.label],
    ["checkbox", false, true, ADD_NOTES],
  );
  assert.equal(mostRamp(40), 8);
  assert.equal(mostRamp(3), 1);
});

test("only the controls touched are sent, numbers as numbers", () => {
  const values = { energy: "0.8", feel: "-0.25", arc: "drop", ramp: "2", skip: true, groove: "0.5" };

  assert.deepEqual(touchedControls(values, new Set(["energy", "feel", "arc", "ramp", "skip"])), {
    energy: 0.8,
    feel: -0.25,
    arc: "drop",
    ramp: 2,
    skip: true,
  });
  assert.deepEqual(touchedControls(values, new Set()), {});
});

test("the page shows a sentence or an option with a capital first letter, and changes nothing else", () => {
  assert.equal(capital("loose"), "Loose");
  assert.equal(capital("your call"), "Your call");
  assert.equal(capital("nothing new: the song's controls stay"), "Nothing new: the song's controls stay");
  assert.equal(capital("Set it by hand"), "Set it by hand");
  assert.equal(capital("4 bars"), "4 bars");
  assert.equal(capital(""), "");
});

test("a slider's number shows two decimals, but a ramp's whole bars", () => {
  assert.equal(fixed("energy", "1"), "1.00");
  assert.equal(fixed("energy", 0.5), "0.50");
  assert.equal(fixed("feel", "-1"), "-1.00");
  assert.equal(fixed("feel", "0.25"), "0.25");
  assert.equal(fixed("ramp", "4"), "4");
});

test("a slider's value is said in words", () => {
  assert.equal(words("energy", "0.8"), "0.80, very high");
  assert.equal(words("energy", "1"), "1.00, very high");
  assert.equal(words("ghost_level", "0"), "0.00, very low");
  assert.equal(words("groove", "0.5"), "0.50, medium");
  assert.equal(words("feel", "-0.3"), "-0.30, pushed");
  assert.equal(words("feel", "0"), "0.00, on the beat");
  assert.equal(words("feel", "0.4"), "0.40, laid back");
  assert.equal(words("ramp", "0"), "no ramp");
  assert.equal(words("ramp", "1"), "1 bar");
  assert.equal(words("ramp", "4"), "4 bars");
});

test("section edits take bars from 1 and give them to the ops from 0", () => {
  const section = { start: 8, bars: 16 };

  assert.deepEqual(sectionEdit("split", section, { at: "17" }), { op: "split", at: 16 });
  assert.deepEqual(sectionEdit("merge", section, {}), { op: "merge", start: 8 });
  assert.deepEqual(sectionEdit("move", section, { to: "11" }), { op: "move", start: 8, to: 10 });
  assert.deepEqual(sectionEdit("rename", section, { name: " Chorus ", group: " B " }), {
    op: "rename",
    start: 8,
    name: "Chorus",
    group: "B",
  });
  assert.deepEqual(sectionEdit("rename", section, { name: "", group: "  " }), {
    op: "rename",
    start: 8,
    name: "",
  });
});

test("a split goes inside its section, and a move after the start of the section before", () => {
  const sections = [
    { start: 0, bars: 8 },
    { start: 8, bars: 16 },
  ];

  assert.deepEqual(editBars(sections, 0), { split: [2, 8], move: null });
  assert.deepEqual(editBars(sections, 1), { split: [10, 24], move: [2, 24] });
});

test("the kits list General MIDI first, name a library's kits when it has several, and flag guesses", () => {
  const maps = {
    libraries: [
      {
        id: "addictive-drums-2",
        name: "Addictive Drums 2",
        kits: [{ map: "addictive-drums-2/default", name: "Default map", articulations: 31, low_confidence: 31 }],
      },
      { id: "gm", name: "General MIDI", kits: [{ map: "gm/default", name: "Percussion key map", articulations: 47, low_confidence: 0 }] },
      {
        id: "iof-drummer",
        name: "iof-drummer",
        kits: [
          { map: "iof-drummer/default", name: "Default layout", articulations: 49, low_confidence: 10 },
          { map: "iof-drummer/old", name: "Old layout", articulations: 40, low_confidence: 20 },
        ],
      },
    ],
  };

  assert.deepEqual(kitOptions(maps, true), [
    { value: "gm/default", label: "General MIDI, or I don't know" },
    { value: "addictive-drums-2/default", label: "Addictive Drums 2 (mapping not yet checked)" },
    { value: "iof-drummer/default", label: "iof-drummer, Default layout" },
    { value: "iof-drummer/old", label: "iof-drummer, Old layout" },
  ]);
  assert.equal(kitOptions(maps, false)[0].label, "General MIDI");
});

test("the download is named after the file, cleaned and cut, and counted from 1", () => {
  assert.equal(downloadName("My Song (v2).mid", 1), "My Song (v2)-humanized-1.mid");
  assert.equal(downloadName("drums.MIDI", 3), "drums-humanized-3.mid");
  assert.equal(downloadName("a/b\\c:d*e?.mid", 1), "abcde-humanized-1.mid");
  assert.equal(downloadName("Groove_01 - Ünïcode ñ.mid", 2), "Groove_01 - Ünïcode ñ-humanized-2.mid");
  assert.equal(downloadName("x".repeat(100) + ".mid", 1), `${"x".repeat(80)}-humanized-1.mid`);
  assert.equal(downloadName("...mid", 1), "song-humanized-1.mid");
  assert.equal(downloadName("take.mid.mid", 1), "takemid-humanized-1.mid");
});

test("bars are labelled from 1, as a DAW shows them", () => {
  assert.equal(barsLabel(8, 16), "bars 9 to 24");
  assert.equal(barsLabel(0, 1), "bar 1");
});

test("the conversion's report and the creative sections' are a line each, in words", () => {
  const report = {
    changed: [
      { source: "cowbell.hit", target: "drop", notes: 1, steps: [] },
      { source: "ride.2.bow", target: "ride.1.bow", notes: 12, steps: [] },
    ],
    collisions: [
      { pitch: 38, channel: 9, count: 2, notes: 4, sources: ["snare.center", "clap.hit"], positions: [[3, 1]] },
    ],
    low_confidence: { read: {}, written: { "hat.open": 5 } },
  };

  assert.deepEqual(conversionLines(report), [
    "1 note of cowbell.hit left out",
    "12 notes of ride.2.bow written as ride.1.bow",
    "4 notes of snare.center and clap.hit land together on note 38, first in bar 4",
    "5 notes written as hat.open, a name not checked yet",
  ]);
  assert.deepEqual(conversionLines({ changed: [], collisions: [], low_confidence: { read: {}, written: {} } }), []);
  assert.deepEqual(creativeLines(null), []);
  assert.deepEqual(creativeLines({ added: { ghost: 12, fill: 8 }, skipped: { missing: { choke: 2 } } }), [
    "Added: 12 ghost, 8 fill",
    "Not added, as the kit to play it has no sound for them: 2 choke",
  ]);
});
