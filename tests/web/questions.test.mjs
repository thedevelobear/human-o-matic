// The rounds' questions (the website plan's PRs 4 and 4b), on the pure module the page draws
// them from, with the vocabulary's rows as presets: every answer the page names is a row, each
// question offers section 6's rows, "your call" sets nothing new, rows move from the song's own
// controls, a round applied sends the whole round as it stands, replacing what it set before,
// and only when it was never applied or has changed since, and an edit keeps a round's draft only
// over the sections it leaves as they were.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  SECTION_KINDS,
  TABS,
  YOUR_CALL,
  answerLines,
  applyRound,
  cameUp,
  described,
  echo,
  groupCalls,
  groupControls,
  groupTabs,
  inSongOrder,
  keptAfterEdit,
  kindByName,
  kindOf,
  noteGrid,
  offered,
  overSong,
  rampTabs,
  roundsAfterEdit,
  rowsOf,
  shownGroup,
  signature,
  songCalls,
  songControls,
  songTabs,
} from "../../src/human_o_matic/web/static/js/questions.js";
import { vocabulary } from "./vocabulary.mjs";

const presets = await vocabulary();
const rows = rowsOf(presets);
const DEFAULTS = {
  energy: 0.5,
  groove: 0.5,
  dynamic_range: 0.5,
  tightness: 0.75,
  feel: 0,
  arc: "steady",
  fill_intensity: 0.5,
  ghost_level: 0.5,
  skip: false,
  creative: false,
  ramp: 0,
};

/** A section of a `get_sections` reply, with only what the page reads. */
const section = (start, bars, group, questions, extra = {}) => ({
  start,
  bars,
  group,
  label: `bars ${start + 1} to ${start + bars}`,
  plays: "hats",
  pattern: { lines: ["hat  x.x.x.x."] },
  name: "",
  controls: {},
  questions,
  ...extra,
});
const ENERGY = (at) => `What's the energy in ${at} (hats, 4 soft snare notes)?`;
const SOFT = "Should its soft notes be more present, or tucked away?";
const GROOVE = "Steady and even, or more groove, with more light and shade?";
const LAST = "Bars 9 to 12 play like bars 1 to 4: the same, or bigger, as the last time?";
const RAMP = (most) =>
  "Build up into bars 5 to 8 over the last bars of bars 1 to 4, each a little harder, or go " +
  `straight in? How many bars, up to ${most}?`;
const reply = (sections, controls = {}) => ({ controls, sections });
const SONG = reply([
  section(0, 4, "A", [ENERGY("bars 1 to 4"), SOFT]),
  section(4, 4, "B", [ENERGY("bars 5 to 8"), GROOVE]),
  section(8, 4, "A", [LAST]),
]);
const members = (found, group) => found.sections.filter((each) => each.group === group);
/** A round's draft: its answers by tab, and the controls moved, by tab and of Fine-tune. */
const round = (answered = {}, more = {}) => ({ answered, hand: {}, fine: {}, ...more });
/** The answer index of `name` on `tab`, "your call" after the rows. */
const index = (tab, name) => (name === YOUR_CALL ? tab.rows.length : tab.rows.indexOf(name));

test("every answer the page names is a row of the vocabulary, but Set it by hand", () => {
  const named = [...SECTION_KINDS, YOUR_CALL, ...Object.values(TABS).flatMap((tab) => tab.rows)];
  const tabs = [
    ...songTabs(presets, { ...DEFAULTS, style: "tight" }),
    ...groupTabs(SONG, "A", presets, DEFAULTS),
    ...groupTabs(SONG, "B", presets, DEFAULTS),
  ];

  for (const name of named) {
    assert.ok(name in rows, name);
  }
  for (const tab of tabs) {
    assert.deepEqual(
      tab.answers.map(({ label }) => label),
      [...tab.rows, YOUR_CALL],
    );
  }
});

test("each tab offers the rows section 6 gives it", () => {
  assert.deepEqual(TABS.drummer.rows, [
    "tight, modern metal",
    "somewhere in between",
    "loose, like a live drummer",
    "machine tight, nearly quantized",
  ]);
  assert.deepEqual(TABS.feel.rows, ["laid back", "way behind the beat, lazy", "pushing, on top of the beat"]);
  assert.deepEqual(TABS.soft.rows, ["soft notes more present", "soft notes tucked away"]);
  assert.deepEqual(TABS.groove.rows, ["steady and even", "more groove, more light and shade"]);
  assert.deepEqual(TABS.fill.rows, ["fill, big into the chorus", "small fill, just a turnaround"]);
  assert.deepEqual(TABS.last.rows, ["a bit harder", "big last chorus"]);
  assert.deepEqual(TABS.ramp.rows, ["build into it over 2 bars", "a 4-bar ramp", "no ramp, straight in"]);
});

test("the Energy tab offers the 11 section kinds only, loudest first, ties in the vocabulary's order", () => {
  const kinds = offered("energy", rows);

  assert.deepEqual(kinds, [
    "breakdown, full power",
    "the drop, everything hits",
    "big last chorus",
    "chorus, big and open",
    "halftime, heavy",
    "pre-chorus, lifting into the chorus",
    "verse, steady and solid",
    "verse, holding back, building",
    "outro, winding down",
    "bridge, low energy, high groove",
    "quiet intro",
  ]);
  assert.ok(!kinds.includes("full power") && !kinds.includes("fairly hard, not all out"));
  for (const [a, b] of kinds.slice(1).map((kind, at) => [kinds[at], kind])) {
    assert.ok(rows[a].energy >= rows[b].energy);
  }
});

test("a group's tabs are its sections' questions in song order, the ramp question left to join", () => {
  const found = reply([section(0, 4, "A", [ENERGY("bars 1 to 4"), SOFT, RAMP(2)]), ...SONG.sections.slice(1)]);

  const tabs = groupTabs(found, "A", presets, DEFAULTS);

  assert.deepEqual(
    tabs.map(({ id, kind, sections }) => [id, kind, sections]),
    [
      ["energy-0", "energy", [0, 8]],
      ["soft-0", "soft", [0, 8]],
      ["last-8", "last", [8]],
    ],
  );
  assert.equal(tabs[0].question, ENERGY("bars 1 to 4"));
  assert.deepEqual(tabs[0].pattern, ["hat  x.x.x.x."]);
  assert.deepEqual(
    tabs[0].hand.map(({ name }) => name),
    ["energy", "arc"],
  );
  assert.deepEqual(groupTabs(reply([section(0, 4, "A", [])]), "A", presets, DEFAULTS), []);
});

test("each question get_sections asks is a tab kind, and one it doesn't is none", () => {
  assert.equal(kindOf(ENERGY("bars 1 to 4")), "energy");
  assert.equal(kindOf(SOFT), "soft");
  assert.equal(kindOf(GROOVE), "groove");
  assert.equal(kindOf("How hard should the fill in bars 13 to 14 hit?"), "fill");
  assert.equal(kindOf(LAST), "last");
  assert.equal(kindOf("Bar 9 plays like bar 1: the same, or bigger, as the last time?"), "last");
  assert.equal(kindOf(RAMP(8)), "ramp");
  assert.equal(kindOf("Anything else?"), null);
});

test("a row's description is its controls at their starting points, in words, with two decimals", () => {
  assert.equal(
    described(rows["chorus, big and open"]),
    "energy 0.80, groove 0.50, dynamic range 0.45, tightness 0.75, feel 0.00, soft notes 0.35",
  );
  assert.equal(described(rows["fill, big into the chorus"]), "fills 0.85");
  assert.equal(described(rows["a bit harder"], true), "energy +0.10");
  assert.equal(described({ style: "loose", ramp: 2, creative: true }), "style loose, ramp 2, creative true");
});

test("your call takes the one kind a section's name gives: equal, trimmed, in any case", () => {
  assert.equal(kindByName("Chorus "), "chorus, big and open");
  assert.equal(kindByName("QUIET INTRO"), "quiet intro");
  assert.equal(kindByName("the drop"), "the drop, everything hits");
  assert.equal(kindByName("verse"), null);
  assert.equal(kindByName("chor"), null);
  assert.equal(kindByName("chorus, big and open"), null);
  assert.equal(kindByName(""), null);
});

test("your call sets nothing new, takes the kind a name gives on Energy, and is no ramp on Ramp", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const context = { presets, song: {}, defaults: DEFAULTS, members: members(SONG, "A") };
  const calls = Object.fromEntries(tabs.map((tab) => [tab.id, index(tab, YOUR_CALL)]));

  assert.deepEqual(groupControls(tabs, round(calls), context).controls, { 0: {}, 8: {} });
  assert.deepEqual(groupControls(tabs, round(), context).controls, { 0: {}, 8: {} });

  const named = { ...SONG, sections: SONG.sections.map((each) => ({ ...each, name: "Chorus " })) };
  const own = groupControls(tabs, round(), { ...context, members: members(named, "A") }).controls;
  assert.deepEqual(own[0], rows["chorus, big and open"]);
  assert.deepEqual(own[8], rows["chorus, big and open"]);
  const verse = { ...context, members: members(SONG, "A").map((each) => ({ ...each, name: "verse" })) };
  assert.deepEqual(groupControls(tabs, round(), verse).controls[0], {});

  const [ramp] = rampTabs(
    reply([section(0, 4, "A", [RAMP(2)]), section(4, 4, "B", [])]),
    new Set(["A", "B"]),
    presets,
    DEFAULTS,
  );
  const ramped = (answered) => groupControls([ramp], round(answered), { ...context, members: [] });
  assert.deepEqual(ramped({}).controls, { 0: { ramp: 0 } });
  assert.deepEqual(ramped({ [ramp.id]: index(ramp, YOUR_CALL) }).controls, { 0: { ramp: 0 } });
  assert.deepEqual(ramped({ [ramp.id]: index(ramp, "build into it over 2 bars") }).controls, {
    0: { ramp: 2 },
  });
});

test("a row over the song's tightness or feel moves it from the song's, and is unset at the default", () => {
  const song = { tightness: 0.9, feel: 0.4 };

  assert.deepEqual(overSong(rows["bridge, low energy, high groove"], song, DEFAULTS), {
    energy: 0.35,
    groove: 0.85,
    dynamic_range: 0.7,
    tightness: 0.75,
    feel: 0.6,
    ghost_level: 0.7,
  });
  const chorus = overSong(rows["chorus, big and open"], song, DEFAULTS);
  assert.ok(!("tightness" in chorus) && !("feel" in chorus));
  assert.equal(chorus.energy, 0.8);
  assert.deepEqual(overSong(rows["chorus, big and open"], {}, DEFAULTS), rows["chorus, big and open"]);

  const tabs = groupTabs(reply(SONG.sections, song), "A", presets, DEFAULTS);
  const [energy] = tabs;
  const answered = round({ [energy.id]: index(energy, "halftime, heavy") });
  const context = { presets, song, defaults: DEFAULTS, members: members(SONG, "A") };
  const { controls } = groupControls(tabs, answered, context);
  assert.equal(controls[0].feel, 0.6);
  assert.ok(!("tightness" in controls[0]));
});

test("the last repeat takes its own answer over the group's, a bit harder added to the group's energy", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy, , last] = tabs;
  const context = { presets, song: {}, defaults: DEFAULTS, members: members(SONG, "A") };
  const chorus = index(energy, "chorus, big and open");

  const harder = groupControls(tabs, round({ [energy.id]: chorus, [last.id]: 0 }), context).controls;
  const bigger = groupControls(tabs, round({ [last.id]: 1 }), context).controls;
  const alone = groupControls(tabs, round({ [last.id]: 0 }), context).controls;
  const same = groupControls(tabs, round({ [energy.id]: chorus, [last.id]: 2 }), context).controls;

  assert.equal(harder[0].energy, 0.8);
  assert.equal(harder[8].energy, 0.9);
  assert.deepEqual(bigger, { 0: {}, 8: rows["big last chorus"] });
  assert.deepEqual(alone, { 0: {}, 8: { energy: 0.6 } });
  assert.deepEqual(same[8], same[0]);
});

test("Set it by hand gives the controls it moved, and Fine-tune's moved controls go over every answer", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy] = tabs;
  const context = { presets, song: {}, defaults: DEFAULTS, members: members(SONG, "A") };
  const byHand = round({ [energy.id]: energy.rows.length + 1 }, { hand: { [energy.id]: { energy: 0.7 } } });
  const fine = round({ [energy.id]: index(energy, "quiet intro") }, { fine: { energy: 0.4 } });

  assert.deepEqual(groupControls(tabs, byHand, context).controls[0], { energy: 0.7 });
  assert.deepEqual(groupControls(tabs, fine, context).controls[0], { ...rows["quiet intro"], energy: 0.4 });
});

test("a round sent again takes back what its answers set before and set no longer", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy] = tabs;
  const context = { presets, song: {}, defaults: DEFAULTS, members: members(SONG, "A") };
  const building = round({ [energy.id]: index(energy, "verse, holding back, building") });
  const { set: before } = groupControls(tabs, building, context);

  const chorus = round({ [energy.id]: index(energy, "chorus, big and open") });
  const changed = groupControls(tabs, chorus, { ...context, before }).controls;
  const mine = groupControls(tabs, round({ [energy.id]: index(energy, YOUR_CALL) }), {
    ...context,
    before,
  }).controls;
  const kept = groupControls(tabs, { ...chorus, fine: { arc: "build" } }, { ...context, before });

  assert.deepEqual(before, { 0: Object.keys(rows["verse, holding back, building"]), 8: before[0] });
  assert.deepEqual(changed[0], { ...rows["chorus, big and open"], arc: null });
  assert.deepEqual(
    mine[0],
    Object.fromEntries(Object.keys(rows["verse, holding back, building"]).map((name) => [name, null])),
  );
  assert.equal(kept.controls[0].arc, "build");
});

test("a group's round is sent in one call for each set of controls, with the sections that take it", () => {
  const calls = groupCalls({ 0: { energy: 0.8 }, 8: { energy: 0.9 }, 16: { energy: 0.8 }, 4: { ramp: 2 } });

  assert.deepEqual(calls, [
    { call: "set_section_controls", args: { controls: { energy: 0.8 }, section_ids: [0, 16] } },
    { call: "set_section_controls", args: { controls: { ramp: 2 }, section_ids: [4] } },
    { call: "set_section_controls", args: { controls: { energy: 0.9 }, section_ids: [8] } },
  ]);
});

test("the song-wide round sets the style and tightness by set_style and the feel for the song", () => {
  const tabs = songTabs(presets, { ...DEFAULTS, style: "tight" });
  const [drummer, feel] = tabs;
  const answers = round({ [drummer.id]: 2, [feel.id]: 0 });

  const { controls, set } = songControls(tabs, answers, { presets });
  const again = songControls(tabs, round({ [drummer.id]: 4 }), { presets, before: set }).controls;

  assert.deepEqual(controls, { tightness: 0.7, style: "loose", feel: 0.4 });
  assert.deepEqual(set, ["tightness", "feel"]);
  assert.deepEqual(songCalls(controls, "loose"), [
    { call: "set_style", args: { style: "loose", tightness: 0.7 } },
    { call: "set_section_controls", args: { controls: { feel: 0.4 } } },
  ]);
  assert.deepEqual(again, { tightness: null, feel: null });
  assert.deepEqual(songCalls(again, "tight"), [
    { call: "set_style", args: { style: "tight" } },
    { call: "set_section_controls", args: { controls: { feel: null, tightness: null } } },
  ]);
  assert.deepEqual(songCalls({}, "medium"), [
    { call: "set_style", args: { style: "medium" } },
    { call: "set_section_controls", args: { controls: {} } },
  ]);
});

test("Fine-tune shows what the answers set over the section without what the round set before", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy] = tabs;
  const own = { energy: 0.8, arc: "build" };
  const sent = { ...SONG, sections: SONG.sections.map((each) => ({ ...each, controls: own })) };
  const context = { presets, song: {}, defaults: DEFAULTS, members: members(sent, "A") };
  context.before = { 0: ["energy"] };

  const shown = shownGroup(tabs, round({ [energy.id]: index(energy, "quiet intro") }), context);
  const mine = shownGroup(tabs, round({ [energy.id]: index(energy, YOUR_CALL) }), context);

  assert.equal(shown.energy, 0.3);
  assert.equal(shown.arc, "build");
  assert.equal(mine.energy, 0.5);
  assert.equal(mine.ramp, 0);
});

test("a Ramp tab waits until both groups are asked about, and is one per group over its leading sections", () => {
  const found = reply([
    section(0, 4, "A", [RAMP(2)]),
    section(4, 4, "B", []),
    section(8, 2, "A", [RAMP(1)]),
    section(10, 8, "C", []),
  ]);

  assert.deepEqual(rampTabs(found, new Set(["A"]), presets, DEFAULTS), []);
  const [early] = rampTabs(found, new Set(["A", "B"]), presets, DEFAULTS);
  const [both] = rampTabs(found, new Set(["A", "B", "C"]), presets, DEFAULTS);

  assert.deepEqual(
    [early.id, early.sections, early.rows],
    ["ramp-0", [0], ["build into it over 2 bars", "no ramp, straight in"]],
  );
  assert.deepEqual(both.sections, [0, 8]);
  assert.equal(both.plays, "Set on 2 sections of A: bars 1 to 4, bars 9 to 10");
  const short = reply([section(0, 2, "A", [RAMP(1)]), section(2, 4, "B", [])]);
  const small = rampTabs(short, new Set(["A", "B"]), presets, DEFAULTS);
  assert.deepEqual(small[0].rows, ["no ramp, straight in"]);
  assert.deepEqual([small[0].hand[0].name, small[0].hand[0].max], ["ramp", 1]);
});

test("a ramp question on the last section, with nothing after it, joins no round", () => {
  const found = reply([section(0, 4, "A", []), section(4, 4, "B", [RAMP(2)])]);

  assert.deepEqual(rampTabs(found, new Set(["A", "B"]), presets, DEFAULTS), []);
});

test("the echo says what each section plays and what the engine clamped, a line each", () => {
  const replies = [
    {
      sections: [
        { start: 0, label: "bars 1 to 4", expected: "kick about 100" },
        { start: 4, label: "bars 5 to 8", expected: "kick about 110" },
      ],
      clamped: [
        { control: "ramp", given: 4, used: 2, section: 0 },
        { control: "energy", given: 1.3, used: 1 },
      ],
    },
  ];

  assert.deepEqual(echo(replies), [
    "Bars 1 to 4: kick about 100.",
    "Bars 5 to 8: kick about 110.",
    "Ramp 4 was taken as 2 in bars 1 to 4.",
    "Energy 1.30 was taken as 1.00.",
  ]);
  assert.deepEqual(echo(replies, [4]), [
    "Bars 5 to 8: kick about 110.",
    "Ramp 4 was taken as 2 in bars 1 to 4.",
    "Energy 1.30 was taken as 1.00.",
  ]);
});

test("a section edit keeps what a round set only on the sections it leaves as they were", () => {
  const before = [
    { start: 0, bars: 4, group: "A" },
    { start: 4, bars: 4, group: "B" },
    { start: 8, bars: 4, group: "A" },
  ];
  const sent = { song: ["feel"], A: { 0: ["energy"], 8: ["energy"] }, B: { 4: ["groove"] } };
  const split = [before[0], { start: 4, bars: 2, group: "B" }, { start: 6, bars: 2, group: "B" }, before[2]];
  const regrouped = [before[0], before[1], { start: 8, bars: 4, group: "C" }];
  const merged = [{ start: 0, bars: 8, group: "A" }, before[2]];
  const moved = [{ start: 0, bars: 6, group: "A" }, { start: 6, bars: 2, group: "B" }, before[2]];
  const renamed = before.map((section) => ({ ...section, name: "chorus" }));

  assert.deepEqual(keptAfterEdit(sent, before, before), sent);
  assert.deepEqual(keptAfterEdit(sent, before, renamed), sent);
  assert.deepEqual(keptAfterEdit(sent, before, moved), { song: ["feel"], A: { 8: ["energy"] }, B: {} });
  assert.deepEqual(keptAfterEdit(sent, before, split), { ...sent, B: {} });
  assert.deepEqual(keptAfterEdit(sent, before, regrouped), { ...sent, A: { 0: ["energy"] } });
  assert.deepEqual(keptAfterEdit(sent, before, merged), { song: ["feel"], A: { 8: ["energy"] }, B: {} });
});

test("a round's signature changes with an answer, a control moved or a question joining, and only then", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy] = tabs;
  const draft = round({ [energy.id]: 2 });
  const [ramp] = rampTabs(reply([section(0, 4, "A", [RAMP(2)]), section(4, 4, "B", [])]), new Set(["A", "B"]), presets, DEFAULTS);

  assert.equal(signature(tabs, draft), signature(tabs, round({ [energy.id]: 2 })));
  for (const changed of [
    signature(tabs, round({ [energy.id]: 3 })),
    signature(tabs, round({ [energy.id]: 2 }, { hand: { [energy.id]: { energy: 0.7 } } })),
    signature(tabs, round({ [energy.id]: 2 }, { fine: { creative: true } })),
    signature([...tabs, ramp], draft),
  ]) {
    assert.notEqual(changed, signature(tabs, draft));
  }
});

/** applyRound with a send that records each draft it sends, and fails when `fails` is set. */
function applying(tabs, draft, { applied, due = [], stay = true, fails = false } = {}) {
  const sent = [];
  const send = async (shown, given) => {
    sent.push(structuredClone(given));
    return fails ? { error: "the engine said no" } : ["Bars 1 to 4: kick about 100."];
  };
  return applyRound({ tabs, draft, applied, send, due: () => due, stay }).then((done) => ({ ...done, sent }));
}

test("a round is applied when the page moves on only if it was never applied or has changed since", async () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy] = tabs;
  // Never applied and untouched: sent, so "your call" counts as its answer.
  const untouched = round();

  const first = await applying(tabs, untouched);
  const again = await applying(tabs, untouched, { applied: first.applied });
  const changed = await applying(tabs, round({ [energy.id]: 1 }), { applied: first.applied });

  assert.deepEqual([first.move, first.sent.length, first.said], [true, 1, ["Bars 1 to 4: kick about 100."]]);
  assert.equal(first.applied, signature(tabs, untouched));
  assert.deepEqual([again.move, again.sent.length, again.applied], [true, 0, first.applied]);
  assert.deepEqual([changed.move, changed.sent.length], [true, 1]);
  assert.notEqual(changed.applied, first.applied);
});

test("a round that fails to apply stays, with its draft as it was and its last apply kept", async () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const draft = round({ [tabs[0].id]: 4 }, { fine: { energy: 0.6 } });
  const before = structuredClone(draft);

  const done = await applying(tabs, draft, { applied: "before", fails: true });

  assert.deepEqual([done.move, done.applied, done.error], [false, "before", "the engine said no"]);
  assert.deepEqual(draft, before);
  assert.deepEqual(done.sent, [before]);
});

test("a Ramp question an apply brings up joins the round, which stays for it when its Next asks", async () => {
  const tabs = groupTabs(SONG, "B", presets, DEFAULTS);
  const [ramp] = rampTabs(reply([section(0, 4, "A", [RAMP(2)]), section(4, 4, "B", [])]), new Set(["A", "B"]), presets, DEFAULTS);

  const next = await applying(tabs, round(), { due: [ramp] });
  const bar = await applying(tabs, round(), { due: [ramp], stay: false });
  const shown = await applying([...tabs, ramp], round(), { applied: next.applied, due: [ramp] });

  assert.deepEqual([next.move, next.joined], [false, [ramp]]);
  assert.equal(next.applied, signature(tabs, round()));
  // The top bar moves on anyway, the ramp left unset to join the next round drawn.
  assert.deepEqual([bar.move, bar.joined], [true, [ramp]]);
  // Joined, the round has changed, so the next click applies it with its ramp and moves on.
  assert.deepEqual([shown.move, shown.sent.length, shown.joined], [true, 1, []]);
});

test("a section's pattern is a grid of its drums' steps, a beat's steps apart, for the piano roll", () => {
  const grid = noteGrid(["ride  X.x. X.x.", "hat   ..x. ..x.", "snare .... X.o.", "kick  X..x ..X."]);

  assert.equal(grid.perBeat, 4);
  assert.deepEqual(
    grid.rows.map(({ drum, cells }) => [drum, cells.join("")]),
    [
      ["ride", "X.x.X.x."],
      ["hat", "..x...x."],
      ["snare", "....X.o."],
      ["kick", "X..x..X."],
    ],
  );
  assert.equal(noteGrid(["kick xxx xxx xx"]).perBeat, 3);
  assert.deepEqual(noteGrid([]), { rows: [], perBeat: 1 });
});

test("a question an apply brings up opens a dialog that asks it in the engine's own words", async () => {
  const tabs = groupTabs(SONG, "B", presets, DEFAULTS);
  const found = reply([section(0, 4, "A", [RAMP(2)]), section(4, 4, "B", []), section(8, 2, "A", [RAMP(1)]), section(10, 4, "C", [])]);
  const [ramp] = rampTabs(found, new Set(["A", "B"]), presets, DEFAULTS);

  // The dialog opens when Next applied the round and stayed for the question, and not otherwise.
  const next = await applying(tabs, round(), { due: [ramp] });
  const bar = await applying(tabs, round(), { due: [ramp], stay: false });
  const said = cameUp(next.joined);

  assert.deepEqual([next.move, bar.move], [false, true]);
  assert.equal(said.title, "One more question came up");
  assert.deepEqual(said.asked, [{ question: RAMP(2), where: "Set on 1 section of A: bars 1 to 4." }]);
  assert.match(said.lead, /leads into a louder one/);
  assert.equal(cameUp([ramp, ramp]).title, "2 more questions came up");
});

test("Last applied lists the rounds applied in the sections' order, the song-wide round first", () => {
  const rounds = {
    B: { said: ["b"], at: 1 },
    song: { said: ["song"], at: 3 },
    C: { draft: {} },
    A: { said: [], at: 2 },
  };

  assert.deepEqual(
    inSongOrder(rounds, ["A", "B", "C"]).map(({ said }) => said),
    [["song"], [], ["b"]],
  );
  assert.deepEqual(inSongOrder({}, ["A"]), []);
});

test("a section edit keeps a group's draft only when its sections, and its Ramp tabs', are as they were", () => {
  const before = [
    { start: 0, bars: 4, group: "A" },
    { start: 4, bars: 4, group: "B" },
    { start: 8, bars: 4, group: "A" },
  ];
  const ramp = { id: "ramp-0", kind: "ramp", sections: [0] };
  const kept = {
    song: { draft: round({ drummer: 1 }) },
    A: { draft: round({ "energy-0": 2 }), applied: "A" },
    B: { draft: { ...round({ "energy-4": 1 }), ramps: [ramp] }, applied: "B" },
  };
  const renamed = before.map((section) => ({ ...section, name: "chorus" }));
  const splitB = [before[0], { start: 4, bars: 2, group: "B" }, { start: 6, bars: 2, group: "B" }, before[2]];
  const splitA = [{ start: 0, bars: 2, group: "A" }, { start: 2, bars: 2, group: "A" }, ...before.slice(1)];
  const joined = [before[0], before[1], { start: 8, bars: 4, group: "B" }];

  assert.deepEqual(roundsAfterEdit(kept, before, renamed), kept);
  assert.deepEqual(Object.keys(roundsAfterEdit(kept, before, splitB)), ["song", "A"]);
  // A split of A changes the section B's ramp builds over, so B's draft goes with A's.
  assert.deepEqual(Object.keys(roundsAfterEdit(kept, before, splitA)), ["song"]);
  // A section moved from A into B changes both groups.
  assert.deepEqual(Object.keys(roundsAfterEdit(kept, before, joined)), ["song"]);
});

test("the review says each round's answers in words, by hand with what it moved, and Fine-tune's", () => {
  const tabs = groupTabs(SONG, "A", presets, DEFAULTS);
  const [energy, soft, last] = tabs;
  const draft = round(
    { [energy.id]: index(energy, "chorus, big and open"), [soft.id]: soft.rows.length + 1 },
    { hand: { [soft.id]: { ghost_level: 0.2 } }, fine: { creative: true } },
  );

  // Each answer starts with a capital, as the page shows it, while the rows keep their own case.
  assert.deepEqual(answerLines(tabs, draft), [
    "Energy: Chorus, big and open",
    "Soft notes: Set by hand, soft notes 0.20",
    "Last repeat: Your call",
    "Fine-tune: Creative true",
  ]);
  assert.equal(last.label, "Last repeat");
  assert.equal(energy.rows[index(energy, "chorus, big and open")], "chorus, big and open");
  assert.deepEqual(answerLines(tabs.slice(1, 2), round({ [soft.id]: soft.rows.length + 1 })), [
    "Soft notes: Set by hand, nothing moved",
  ]);
});
