// The engine under Pyodide in Node: the calls of flow.json on the built site's test song give
// the download whose SHA-256 the flow holds, as they do natively, and its remap's calls the file
// the remap tool writes (ADRs 0100, 0112 and 0131), and the
// page's forms, as it serves them, make calls the engine takes, and the feedback's settings of a
// song it opens hold only their allowed keys. It loads what
// `uv run python tools/build_site.py build` wrote into dist/site/, so the build runs first.

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { fourGroups } from "./song.mjs";
import { vocabulary } from "./vocabulary.mjs";

const site = new URL("../../dist/site/", import.meta.url);
const flow = JSON.parse(await readFile(new URL("flow.json", import.meta.url), "utf8"));

/** The engine, loaded afresh. A failure to load it says why, with its stack, on stderr and in
 * the error, so a test that fails at once can be read: a build empties dist/site before it
 * writes it again, so one running beside `node --test` fails every test here. */
async function engine() {
  try {
    await access(new URL("engine.json", site)).catch(() => {
      throw new Error(
        "no built site: run `uv run python tools/build_site.py build` first, and not while " +
          "`node --test` runs, since a build empties dist/site before it writes it again",
      );
    });
    const { startEngine } = await import(new URL("js/engine.js", site).href);
    const steps = [];
    const started = await startEngine({
      base: site,
      read: async (url) => new Uint8Array(await readFile(fileURLToPath(url))),
      place: (url) => fileURLToPath(url),
      progress: (done, step) => steps.push([done, step]),
    });
    return { ...started, steps };
  } catch (error) {
    const reason = `the engine didn't load under Pyodide: ${error?.stack ?? error}`;
    console.error(reason);
    throw new Error(reason, { cause: error });
  }
}

/** The SHA-256 of the file `calls` download from the test song, each other reply checked for an
 * error: the song's bytes go with an `open_session` or a `remap`, and `$session` is the session
 * the first opened. */
async function downloaded(call, calls) {
  const data = new Uint8Array(await readFile(fileURLToPath(new URL(flow.song, site))));
  let session = null;
  let digest = null;
  for (const { call: name, args } of calls) {
    const given = JSON.parse(JSON.stringify(args).replaceAll('"$session"', JSON.stringify(session)));
    const out = call({ call: name, args: given }, ["open_session", "remap"].includes(name) ? data : undefined);
    if (out instanceof Uint8Array) {
      digest = createHash("sha256").update(out).digest("hex");
      continue;
    }
    const reply = JSON.parse(out);
    assert.equal(reply.error, undefined, `${name}: ${reply.error}`);
    session = reply.session_id ?? session;
  }
  return digest;
}

test("the flow's calls under Pyodide download the file of the flow's SHA-256", async () => {
  const { call, steps } = await engine();

  assert.equal(await downloaded(call, flow.calls), flow.sha256);
  assert.deepEqual(
    steps.map(([, step]) => step),
    ["runtime", "packages", "wheels", "app"],
  );
  assert.equal(steps.at(-1)[0], 1);
});

test("the remap's calls under Pyodide download the file the remap tool writes natively", async () => {
  const { call } = await engine();

  assert.equal(await downloaded(call, flow.remap.calls), flow.remap.sha256);
});

/** Each field's starting value, by name, as the page's form holds it before any change. */
function startingValues(fields, values = {}) {
  for (const field of fields) {
    if (field.type === "group") {
      startingValues(field.fields, values);
    } else if (field.name && !["button", "list"].includes(field.type)) {
      values[field.name] = field.type === "checkbox" ? Boolean(field.checked) : field.value;
    }
  }
  return values;
}

test("the page's forms make calls the engine takes, from opening the song to its download", async () => {
  const { call } = await engine();
  const forms = await import(new URL("js/forms.js", site).href);
  const { downloadName } = await import(new URL("js/review.js", site).href);
  const data = new Uint8Array(await readFile(fileURLToPath(new URL(flow.song, site))));
  const ask = (name, args, file) => {
    const out = call({ call: name, args }, file);
    return out instanceof Uint8Array ? out : JSON.parse(out);
  };
  const maps = ask("list_maps", {});
  const [from] = forms.kitOptions(maps, true);

  const opened = ask("open_session", { name: "My Song (v2).mid", from_map: from.value }, data);
  const fields = opened.decisions.flatMap((request) => forms.form(request));
  const answered = forms.batch(opened.decisions, startingValues(fields));
  const checked = ask(answered.call, { session_id: opened.session_id, ...answered.args });
  const sections = ask("get_sections", { session_id: opened.session_id });
  const [first, second] = sections.sections;
  const styled = ask("set_style", { session_id: opened.session_id });
  const resolved = { ...styled.defaults, ...sections.controls, ...first.controls };
  const tuned = forms.fineTune(forms.GROUP_CONTROLS, resolved, forms.mostRamp(first.bars));
  const values = startingValues(tuned);
  const controls = forms.touchedControls(
    { ...values, energy: "0.9", arc: "build", ramp: "2", creative: true },
    new Set(["energy", "arc", "ramp", "creative"]),
  );
  const set = ask("set_section_controls", {
    session_id: opened.session_id,
    controls,
    section_ids: [first.start],
  });
  const split = forms.sectionEdit("split", second, { at: String(second.start + 3) });
  const edited = ask("update_sections", { session_id: opened.session_id, ops: [split] });
  const file = ask("download", { session_id: opened.session_id });

  assert.equal(from.value, "gm/default");
  assert.deepEqual(
    opened.decisions.map(({ kind }) => kind),
    ["hit_types"],
  );
  assert.equal(answered.call, "set_hit_types");
  assert.deepEqual(checked.decisions, []);
  assert.equal(set.error, undefined, set.error);
  assert.deepEqual(set.clamped, []);
  assert.deepEqual(set.sections[0].controls, { energy: 0.9, arc: "build", creative: true, ramp: 2 });
  assert.equal(edited.sections[2].start, second.start + 2);
  assert.ok(file instanceof Uint8Array && file.length > 0);
  assert.equal(downloadName("My Song (v2).mid", 1), "My Song (v2)-humanized-1.mid");
});

test("the presets under Pyodide equal vocabulary.md's rows at their starting points", async () => {
  const { call } = await engine();

  assert.deepEqual(JSON.parse(call({ call: "presets", args: {} })), await vocabulary());
});

// Each group's answers on the four-group song, by tab kind; a kind not named is left unanswered,
// so it is "your call". A's last repeat, a bit harder, keeps it under C by less than a ramp asks.
const ANSWERS = {
  A: { energy: "quiet intro", soft: "soft notes tucked away", last: "a bit harder" },
  B: { energy: "chorus, big and open", groove: "steady and even", last: "big last chorus" },
  C: { fill: "fill, big into the chorus" },
  D: { energy: "halftime, heavy" },
};
const RAMP = "build into it over 2 bars";

test("on a four-group song the flow asks each question get_sections gives, once, counted", async () => {
  const { call } = await engine();
  const forms = await import(new URL("js/forms.js", site).href);
  const questions = await import(new URL("js/questions.js", site).href);
  const ask = (name, args, file) => {
    const reply = JSON.parse(call({ call: name, args }, file));
    assert.equal(reply.error, undefined, `${name}: ${reply.error}`);
    return reply;
  };
  const presets = ask("presets", {});
  const opened = ask("open_session", { name: "four.mid", from_map: "gm" }, fourGroups());
  const session_id = opened.session_id;
  const send = (calls) => calls.map(({ call: name, args }) => ask(name, { session_id, ...args }));
  // The count, as the page keeps it: the kits window, the check batch, then each question tab
  // the first time its round is sent.
  const asked = new Set(["kits"]);
  const fields = opened.decisions.flatMap((request) => forms.form(request));
  const checked = forms.batch(opened.decisions, startingValues(fields));
  assert.deepEqual(send([checked])[0].decisions, []);
  asked.add("check");

  const styled = ask("set_style", { session_id });
  const songTabs = questions.songTabs(presets, { ...styled.defaults, style: styled.style });
  const song = { answered: { drummer: 0 }, hand: {}, fine: {} };
  const { controls: wide } = questions.songControls(songTabs, song, { presets });
  send(questions.songCalls(wide, styled.style));
  songTabs.forEach((tab) => asked.add(tab.id));

  // Each question by its section, as `start: question`: what get_sections gives when it is due,
  // a group's own questions when its round is drawn, and a ramp question once both its groups
  // are asked about (ADR 0108); and what the flow's tabs asked.
  const given = [];
  const covered = [];
  const groupsAsked = new Set();
  let sections = ask("get_sections", { session_id });
  const order = [...new Set(sections.sections.map((section) => section.group))];
  const isRamp = (question) => questions.kindOf(question) === "ramp";
  const due = () =>
    sections.sections.flatMap((each, index) => {
      const after = sections.sections[index + 1];
      const ready = after && groupsAsked.has(each.group) && groupsAsked.has(after.group);
      return ready ? each.questions.filter(isRamp).map((question) => `${each.start}: ${question}`) : [];
    });
  // A round's send, as the page's: its calls, the questions counted, and the sections again.
  const sends = [];
  const sendRound = (group, tabs, draft) => {
    const context = {
      presets,
      song: sections.controls,
      defaults: styled.defaults,
      members: questions.membersOf(sections, group),
    };
    const calls = questions.groupCalls(questions.groupControls(tabs, draft, context).controls);
    for (const tab of tabs.filter((each) => !asked.has(each.id))) {
      asked.add(tab.id);
      const leading = sections.sections.filter((each) => tab.sections.includes(each.start));
      covered.push(
        ...(tab.kind === "ramp"
          ? leading.map((each) => `${each.start}: ${each.questions.find(isRamp)}`)
          : [`${tab.id.split("-").at(-1)}: ${tab.question}`]),
      );
    }
    send(calls);
    sends.push(calls);
    groupsAsked.add(group);
    sections = ask("get_sections", { session_id });
    given.push(...due());
    return [];
  };
  for (const group of order) {
    const members = questions.membersOf(sections, group);
    given.push(
      ...members.flatMap((each) =>
        each.questions.filter((question) => !isRamp(question)).map((question) => `${each.start}: ${question}`),
      ),
    );
    const tabs = questions.groupTabs(sections, group, presets, styled.defaults);
    const answered = {};
    for (const tab of tabs) {
      const name = ANSWERS[group][tab.kind];
      if (name) {
        answered[tab.id] = tab.rows.indexOf(name);
      }
    }
    // The group's round is applied as the page moves on by its Next button (ADR 0124): a Ramp
    // question that brings up joins it and keeps it, and the next click applies the whole round
    // again with it, then moves on.
    const draft = { answered, hand: {}, fine: {} };
    const sent = sends.length;
    let shown = tabs;
    let applied;
    for (;;) {
      const done = await questions.applyRound({
        tabs: shown,
        draft,
        applied,
        send: (each, given) => sendRound(group, each, given),
        due: () => questions.rampTabs(sections, groupsAsked, presets, styled.defaults),
        stay: true,
      });
      applied = done.applied;
      if (done.move) {
        break;
      }
      for (const tab of done.joined) {
        const most = tab.rows.indexOf(RAMP);
        if (most !== -1) {
          answered[tab.id] = most;
        }
      }
      shown = [...shown, ...done.joined];
    }
    const [first, again] = sends.slice(sent);
    if (again) {
      const ramps = shown.filter((tab) => tab.kind === "ramp");
      const own = again.filter((each) => !ramps.some((tab) => tab.sections.includes(each.args.section_ids[0])));
      assert.deepEqual(own, first);
    }
    // Moving on again sends nothing: the round is as it was applied.
    const left = await questions.applyRound({ tabs: shown, draft, applied, send: () => assert.fail("sent") });
    assert.equal(left.move, true);
  }

  const ramps = sections.sections.flatMap((each) => each.questions).filter(isRamp);
  const controls = Object.fromEntries(sections.sections.map((each) => [each.start, each.controls]));
  assert.deepEqual(order, ["A", "B", "C", "D"]);
  assert.deepEqual(covered.toSorted(), [...new Set(given)].toSorted());
  assert.equal(new Set(covered).size, covered.length);
  assert.deepEqual(ramps, []);
  assert.deepEqual(
    covered.map((question) => questions.kindOf(question.split(": ").slice(1).join(": "))),
    ["energy", "soft", "last", "energy", "groove", "last", "ramp", "fill", "energy", "groove", "ramp"],
  );
  // ADR 0090's count: one for the kits, one for the check batch, one for each question tab, and
  // A alone asks three before its ramp: no limit of two a group.
  assert.equal(asked.size, 2 + songTabs.length + covered.length);
  assert.equal(asked.size, 15);
  assert.equal(controls[0].ramp, 2);
  assert.equal(controls[12].ramp, 0);
  assert.equal(controls[8].energy, 0.4);
  assert.equal(controls[4].energy, 0.8);
  assert.ok(!("tightness" in controls[4]));
  assert.equal(controls[18].energy, 0.9);
  assert.deepEqual(sections.controls, { tightness: 0.85 });
  assert.equal(sections.style, "tight");
});

test("the feedback's settings of a song opened under Pyodide hold only their keys and the takes", async () => {
  const { call } = await engine();
  const forms = await import(new URL("js/forms.js", site).href);
  const { feedbackRequest, settingsOf } = await import(new URL("js/feedback.js", site).href);
  const ask = (name, args, file) => {
    const reply = JSON.parse(call({ call: name, args }, file));
    assert.equal(reply.error, undefined, `${name}: ${reply.error}`);
    return reply;
  };
  const kits = { from_map: "gm/default", to_map: "gm/default" };
  const opened = ask("open_session", { name: "My Secret Song.mid", ...kits }, fourGroups());
  const session_id = opened.session_id;
  const fields = opened.decisions.flatMap((request) => forms.form(request));
  const checked = forms.batch(opened.decisions, startingValues(fields));
  assert.deepEqual(ask(checked.call, { session_id, ...checked.args }).decisions, []);
  ask("set_style", { session_id, style: "loose", seed: 11 });
  ask("set_section_controls", { session_id, controls: { feel: 0.3 } });
  ask("set_section_controls", { session_id, controls: { energy: 0.9, creative: true }, section_ids: [4] });
  ask("update_sections", { session_id, ops: [{ op: "rename", start: 4, name: "Big chorus" }] });
  ask("render", { session_id, section_ids: [4], take: 2 });
  const read = ask("get_sections", { session_id });

  const settings = settingsOf(kits, read);
  const sent = new URLSearchParams(feedbackRequest({ rating: "5" }, settings).body).get("settings");

  assert.deepEqual(Object.keys(settings), [
    "from_map",
    "to_map",
    "style",
    "seed",
    "bars",
    "sections",
    "song_controls",
    "section_controls",
    "takes",
  ]);
  assert.equal(settings.style, "loose");
  assert.equal(settings.seed, 11);
  assert.equal(settings.bars, read.bars);
  assert.equal(settings.sections, read.sections.length);
  assert.deepEqual(settings.song_controls, { feel: 0.3 });
  assert.deepEqual(settings.section_controls[1], { energy: 0.9, creative: true });
  assert.deepEqual(settings.takes, read.sections.map(({ start }) => (start === 4 ? 2 : 0)));
  const names = [settings.song_controls, ...settings.section_controls].flatMap(Object.keys);
  assert.ok(names.length > 0 && names.every((name) => forms.GROUP_CONTROLS.includes(name)), names);
  assert.deepEqual(JSON.parse(sent), settings);
  for (const left of ["My Secret Song", ".mid", "Big chorus", session_id, "pattern", "kick", "snare"]) {
    assert.ok(!sent.includes(left), left);
  }
});

test("a call off the allowlist is an error in plain words under Pyodide", async () => {
  const { call } = await engine();

  const reply = JSON.parse(call({ call: "export", args: {} }));

  assert.match(reply.error, /^the request: call: Input should be/);
});
