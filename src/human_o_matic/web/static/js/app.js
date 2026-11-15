// The page: its steps from choosing a file to the download, over the engine in a Web Worker
// (ADR 0100), called by the worker API one call at a time (ADR 0114). The engine starts loading
// as the page opens. The page never sees a note and stores nothing: the chosen file's bytes stay
// in this page's memory and the worker's until "Delete my file now" ends the worker, or the tab
// is closed (the website plan's section 8). The song-wide round and each repeat group's ask
// their questions on one card, from questions.js, whose answers stay a draft in this page's
// memory until the song is opened again, and a round is applied when the user moves on from it
// (ADR 0124).

import { drawFields, element, readFields } from "./fields.js";
import {
  GROUP_CONTROLS,
  SONG_CONTROLS,
  batch,
  capital,
  count,
  editBars,
  fineTune,
  form,
  kitOptions,
  mostRamp,
  sectionEdit,
} from "./forms.js";
import {
  answerLines,
  applyRound,
  cameUp,
  echo,
  groupCalls,
  groupControls,
  groupTabs,
  inSongOrder,
  keptAfterEdit,
  membersOf,
  rampTabs,
  resolvedOf,
  roundsAfterEdit,
  shownGroup,
  shownSong,
  signature,
  songCalls,
  songControls,
  songTabs,
} from "./questions.js";
import { barsLabel, conversionLines, creativeLines, downloadName } from "./review.js";
import { engineState } from "./loading.js";
import { drawRound } from "./round.js";

const STEPS = ["file", "kits", "check", "drummer", "sections", "review", "download"];
// How long a download's Blob URL lives after the download starts, and the toast stays.
const REVOKE_MS = 10_000;
const TOAST_MS = 6_000;
const $ = (selector) => document.querySelector(selector);

let worker;
let waiting = new Map();
let calls = 0;
let kitNames = {};
// The vocabulary's rows at their starting points, from the worker's `presets` call.
let presets = null;
// Whether the kit to play the file was chosen, so it no longer follows the kit it came from.
let toChosen = false;
// Whether the page is moving on, so a second click can't apply a round twice.
let moving = false;
let toastTimer;
let page = fresh();

/** What the page holds of one file, from choosing it to deleting it. */
function fresh() {
  return {
    file: null,
    open: {},
    session: null,
    bars: 0,
    toKit: null,
    decisions: [],
    table: [],
    sections: null,
    defaults: null,
    song: {},
    // The session's style, which the Drummer step's "your call" keeps.
    drummer: null,
    seed: 0,
    // Each round, "song" or a group's, as `{draft, applied, said, lines, at, name, title}`: its
    // draft of answers, its signature and echo's lines when last applied, its answers in words
    // for the review, and when it was applied, by `applies`, and its names, for "Last applied"; the round on screen, `{key, drawn, send, due}`; the controls each round's
    // answers set at its last send, by section; and the groups whose rounds were sent, all of
    // the song as opened; and the questions asked.
    rounds: {},
    applies: 0,
    round: null,
    sent: {},
    groupsAsked: new Set(),
    asked: new Set(),
    selected: 0,
    summary: null,
    downloads: 0,
    url: null,
    reached: "file",
  };
}

// The engine.

function startEngine() {
  loading(engineState({}));
  worker = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
  worker.onerror = () => loading(engineState({ failed: "this browser couldn't start it" }));
  worker.onmessage = ({ data }) => {
    if ("progress" in data || "failed" in data) {
      loading(engineState(data));
    } else {
      waiting.get(data.id)?.(data);
      waiting.delete(data.id);
    }
  };
}

/** The loading view, alone while the engine loads, with its real progress, and the page in its
 * place once it is ready: hidden and inert until then (ADR 0125). */
function loading({ phase, text, value }) {
  const bar = $("#engine");
  bar.value = value;
  const ready = phase === "ready";
  bar.hidden = phase === "failed";
  $("#engine-status").textContent = text;
  $("#reload").hidden = phase !== "failed";
  $("#loading").hidden = ready;
  $("#app").hidden = !ready;
  $("#app").inert = !ready;
  if (ready) {
    say(text);
    $("#file-title").focus();
  }
}

/** One call of the worker API: its reply, a download's bytes, or `{error}`. */
function ask(call, args = {}, file = undefined) {
  return new Promise((resolve) => {
    const id = calls++;
    waiting.set(id, ({ out, error }) =>
      resolve(error ? { error } : out instanceof Uint8Array ? out : JSON.parse(out)),
    );
    worker.postMessage({ id, request: { call, args }, file });
  });
}

/** Whether `reply` is an error, which it shows. */
function failed(reply) {
  if (reply.error) {
    problem(reply.error);
  }
  return Boolean(reply.error);
}

const WAITING = "Some notes still wait for an answer: see step 3, Check.";

/** Whether `reply` holds requests still open, so nothing rendered, which it shows. */
function waits(reply) {
  const open = Boolean(reply.decisions?.length);
  if (open) {
    problem(WAITING);
  }
  return open;
}

function say(text) {
  $("#status").textContent = text;
}

function problem(text) {
  $("#problem").textContent = text;
}

/** What the page has just applied, in the toast for a while and in the status line. */
function toast(title, body) {
  say(`${title}. ${body}`);
  $("#toast-title").textContent = title;
  $("#toast-body").textContent = body;
  $("#toast").classList.add("shown");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("shown"), TOAST_MS);
}

/** "Last applied", in the top bar: the round applied last, by a short name, once a song is open. */
function drawApplied() {
  const [last] = Object.values(page.rounds)
    .filter(({ said }) => said)
    .sort((a, b) => b.at - a.at);
  $("#last-applied").hidden = !page.session;
  $("#last-applied").textContent = last ? `Last applied: ${capital(last.name)}` : "Nothing applied yet";
}

/** The dialog behind "Last applied": each round applied, in the sections' order, its echo a line
 * each, and the count of questions so far. */
function showApplied() {
  const blocks = inSongOrder(page.rounds, groupsOf(page.table)).map(({ title, said }) =>
    element(
      "li",
      {},
      element("h3", {}, title),
      element("ul", {}, ...(said.length ? said : ["Nothing new: the song's controls stay."]).map((line) => element("li", {}, line))),
    ),
  );
  const none = element("li", {}, "Nothing is applied yet: a round applies when you move on from it.");
  $("#applied-list").replaceChildren(...(blocks.length ? blocks : [none]));
  $("#applied-count").textContent = `Questions so far: ${page.asked.size}`;
  openDialog($("#applied-dialog"));
}

/** Open `dialog`, the page's one dialog pattern, at the top of what its body holds. */
function openDialog(dialog) {
  dialog.showModal();
  dialog.querySelector(".modal-body").scrollTop = 0;
}

/** Whether `event`, a click on `dialog` itself, fell outside its box, on the blurred backdrop. */
function onBackdrop(dialog, event) {
  const box = dialog.getBoundingClientRect();
  const { clientX: x, clientY: y } = event;
  return event.target === dialog && (x < box.left || x > box.right || y < box.top || y > box.bottom);
}

/** A round's names: short, for "Last applied" and the toast, and whole, for its dialog. */
function namesOf(key) {
  if (key === "song") {
    return { name: "the drummer", title: "The drummer" };
  }
  const [first] = membersOf(page.sections, key);
  return { name: `${first.label} (${key})`, title: groupTitle(key) };
}

// The steps.

/** Show `step` alone, the steps reached so far open in the top bar, and unless `focus` is false,
 * scroll to the top of it, its status and alert lines included, and move focus to its heading. */
function show(step, focus = true) {
  for (const name of STEPS) {
    $(`#${name}`).hidden = name !== step;
  }
  for (const button of document.querySelectorAll("#steps button")) {
    const name = button.dataset.step;
    button.disabled = STEPS.indexOf(name) > STEPS.indexOf(page.reached);
    if (name === step) {
      button.setAttribute("aria-current", "step");
    } else {
      button.removeAttribute("aria-current");
    }
  }
  if (focus) {
    $("main").scrollIntoView({ block: "start" });
    $(`#${step}-title`).focus({ preventScroll: true });
  }
}

const ENTER = {
  check: drawCheck,
  drummer: drawDrummer,
  sections: drawSections,
  review: drawReview,
  download: drawDownload,
};

async function go(step) {
  if (STEPS.indexOf(step) > STEPS.indexOf(page.reached)) {
    page.reached = step;
  }
  problem("");
  page.round = null;
  show(step);
  await ENTER[step]?.();
}

/** Leave the round on screen, applying it, then `then()` if the page may move on: a round that
 * fails to apply, or that `stay` keeps for a Ramp question it brought up, stays. */
async function moveOn(stay, then) {
  if (moving) {
    return;
  }
  moving = true;
  try {
    if (await leave(stay)) {
      await then();
    }
  } finally {
    moving = false;
  }
}

/** Apply the round on screen if it was never applied or has changed since (ADR 0124), and say
 * whether the page may move on from it. */
async function leave(stay) {
  const shown = page.round;
  // A round an edit has just forgotten, still on screen until it is drawn again, has no draft.
  const kept = page.rounds[shown?.key];
  if (!kept) {
    return true;
  }
  const tabs = shown.drawn.tabs();
  const send = (given, draft) => {
    shown.drawn.say("Applying your answers");
    return shown.send(given, draft);
  };
  const { due } = shown;
  const done = await applyRound({ tabs, draft: kept.draft, applied: kept.applied, send, due, stay });
  if (done.error !== undefined) {
    shown.drawn.say(`Not applied: ${done.error}. Your answers are kept, to apply when you move on.`);
    return false;
  }
  if (done.said !== undefined) {
    const lines = answerLines(tabs, kept.draft);
    Object.assign(kept, { applied: done.applied, said: done.said, lines, at: ++page.applies, ...namesOf(shown.key) });
    drawApplied();
  }
  if (done.move) {
    if (done.said !== undefined) {
      toast(`Applied: ${capital(kept.name)}`, "What it set is under \u201cLast applied\u201d, at the top.");
    }
    return true;
  }
  // A Ramp question both of whose groups are now asked about joins this round (ADR 0108), which
  // stays for it, and is applied with it when the user moves on again; a dialog says so.
  for (const tab of done.joined) {
    shown.drawn.join(tab);
  }
  shown.drawn.say(`\u2713 Applied. ${cameUp(done.joined).title}, below: it applies when you move on.`);
  showCameUp(done.joined, shown.drawn);
  return false;
}

/** The dialog that tells of the questions `joined` that applying the round on screen brought up,
 * in the engine's own words, whose "Answer it" scrolls to the first and focuses its answer, while
 * Escape or the backdrop leaves focus to return where it was (ADR 0124). */
function showCameUp(joined, drawn) {
  const { title, lead, asked, after } = cameUp(joined);
  $("#more-title").textContent = title;
  $("#more-what").replaceChildren(
    element("p", { class: "mb-3" }, lead),
    ...asked.flatMap(({ question, where }) => [
      element("p", { class: "font-bold mb-1" }, question),
      element("p", { class: "font-mono text-xs text-ink/75 mb-3" }, where),
    ]),
    element("p", {}, after),
  );
  const dialog = $("#more-dialog");
  dialog.returnValue = "";
  dialog.addEventListener(
    "close",
    () => {
      if (dialog.returnValue === "answer") {
        drawn.answer(joined[0].id);
      }
    },
    { once: true },
  );
  openDialog(dialog);
}

/** The line a round shows: applied or not yet; what it applied is behind "Last applied". */
function stateOf(key, tabs) {
  const { draft, applied } = page.rounds[key];
  return applied === signature(tabs, draft) ? "\u2713 Applied" : "Not applied yet: applies when you move on.";
}

/** Draw the round of `key` in `parent` from its draft, as the round on screen. */
function drawShown(key, parent, { send, due = () => [], ...options }) {
  const kept = (page.rounds[key] ??= {});
  const drawn = drawRound(parent, {
    ...options,
    draft: kept.draft,
    keep: (tabs, draft) => {
      kept.draft = draft;
      return stateOf(key, tabs);
    },
  });
  page.round = { key, drawn, send, due };
}

// 1. Choose a file.

async function choose(file) {
  if (!file) {
    return;
  }
  if (!/\.midi?$/i.test(file.name)) {
    problem(`${file.name} isn't a .mid or .midi file`);
    return;
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  // The downloads count this visit's, so another file, or the same again, never takes a name
  // given before; only "Delete my file now" starts the count again.
  page = { ...fresh(), downloads: page.downloads, file: { name: file.name, bytes } };
  problem("");
  $("#deleted").textContent = "";
  $("#chosen").textContent = `Chosen: ${file.name}`;
  drawApplied();
  $("#to-kits").disabled = false;
  $("#delete-box").hidden = false;
  show("file", false);
}

// 2. Kits.

async function loadKits() {
  const maps = await ask("list_maps");
  if (failed(maps)) {
    return;
  }
  for (const [select, source] of [
    [$("#from-map"), true],
    [$("#to-map"), false],
  ]) {
    select.replaceChildren(...kitOptions(maps, source).map(({ value, label }) => new Option(label, value)));
  }
  kitNames = Object.fromEntries(kitOptions(maps, false).map(({ value, label }) => [value, label]));
  $("#open").disabled = false;
}

/** Open the chosen file in a new session, with the kits chosen and any tempo or track given. */
async function openSong() {
  // One opening at a time, so two clicks can't interleave their reset and open_session.
  if ($("#open").disabled) {
    return;
  }
  $("#open").disabled = true;
  say("Opening the song");
  let reply;
  try {
    await ask("reset");
    reply = await ask(
      "open_session",
      { name: page.file.name, from_map: $("#from-map").value, to_map: $("#to-map").value, ...page.open },
      page.file.bytes,
    );
  } finally {
    $("#open").disabled = false;
  }
  if (failed(reply)) {
    say("");
    return;
  }
  page.session = reply.session_id ?? null;
  page.bars = reply.summary?.bars ?? 0;
  page.toKit = reply.to_kit ?? null;
  Object.assign(page, { rounds: {}, sent: {}, groupsAsked: new Set() });
  if (page.session) {
    page.asked.add("kits");
  }
  page.decisions = reply.decisions;
  page.table = reply.sections ?? [];
  page.reached = "kits";
  drawApplied();
  say(page.session ? `Opened: ${reply.summary.bars} bars in ${page.table.length} sections.` : "");
  await go("check");
}

// 3. Check, one batch.

function drawStrip(list, sections, pick) {
  list.replaceChildren(
    ...sections.map((section) => {
      const text = `${section.group}: ${section.label}${section.name ? `, ${section.name}` : ""}`;
      if (!pick) {
        return element("li", {}, text);
      }
      const pressed = String(section.start === page.selected);
      const button = element("button", { type: "button", class: "retro-btn btn", "aria-pressed": pressed }, text);
      button.dataset.start = section.start;
      return element("li", {}, button);
    }),
  );
}

async function drawCheck() {
  $("#opened-facts").textContent = `${count(page.bars, "bar")} in ${count(page.table.length, "section")}.`;
  drawStrip($("#check-sections"), page.table, false);
  const box = $("#requests");
  box.replaceChildren();
  for (const [index, request] of page.decisions.entries()) {
    const unmapped = request.kind === "unmapped_notes";
    const extra = unmapped ? await ask("kit_articulations", { map: request.details.kit }) : {};
    const part = element("div", { class: "request" }, element("p", {}, request.message));
    drawFields(part, form(request, extra.error ? {} : extra), `request-${index}`);
    box.append(part);
  }
  if (!page.decisions.length) {
    box.append(element("p", {}, "Nothing else to check: confirm the sections to go on."));
  }
}

async function confirmCheck(event) {
  event.preventDefault();
  if (!page.decisions.length) {
    page.asked.add("check");
    await go("drummer");
    return;
  }
  const { call, args } = batch(page.decisions, readFields($("#requests")));
  if (call === "open_session") {
    page.open = { ...page.open, ...args };
    await openSong();
    return;
  }
  const reply = await ask(call, { session_id: page.session, ...args });
  if (failed(reply)) {
    return;
  }
  page.decisions = reply.decisions;
  if (page.decisions.length) {
    await drawCheck();
    return;
  }
  page.asked.add("check");
  await go("drummer");
}

// 4. Drummer, the song-wide round.

function remember(styled) {
  page.defaults = styled.defaults;
  page.drummer = styled.style;
  page.song = styled.controls;
  page.seed = styled.seed;
  $("#seed").textContent = String(styled.seed);
}

/** The vocabulary's rows, asked of the worker once. */
async function vocabulary() {
  if (!presets) {
    const reply = await ask("presets");
    presets = failed(reply) ? null : reply;
  }
  return presets;
}

function songContext() {
  const { song, defaults, drummer, sent } = page;
  return { presets, song, defaults, style: drummer, before: sent.song ?? [] };
}

async function drawDrummer() {
  const styled = await ask("set_style", { session_id: page.session });
  if (failed(styled) || !(await vocabulary())) {
    return;
  }
  remember(styled);
  const resolved = { ...styled.defaults, ...styled.controls, style: styled.style };
  drawShown("song", $("#song-round"), {
    id: "song",
    questions: songTabs(presets, resolved),
    fineTune: fineTune(SONG_CONTROLS, resolved),
    follow: (tabs, draft) => shownSong(tabs, draft, songContext()),
    send: sendSong,
  });
}

/** Send the song-wide round's draft: its style as it stands, its answers, and of Fine-tune the
 * controls moved. Gives the echo, or the failed reply. */
async function sendSong(tabs, draft) {
  const { controls, set } = songControls(tabs, draft, songContext());
  const replies = [];
  for (const { call, args } of songCalls(controls, page.drummer)) {
    const reply = await ask(call, { session_id: page.session, ...args });
    if (failed(reply)) {
      return reply;
    }
    replies.push(reply);
  }
  const [styled, tuned] = replies;
  remember({ ...styled, controls: tuned.song.controls });
  // shortcut: groups applied before keep the rows they took over the song's tightness and feel
  // then; apply them again here if they should follow a later song-wide answer.
  page.sent.song = set;
  for (const tab of tabs) {
    page.asked.add(tab.id);
  }
  const firsts = groupsOf(page.table).map(
    (group) => page.table.find((section) => section.group === group).start,
  );
  return echo(replies, firsts);
}

// 5. Sections, their edits and each repeat group's round.

function selected() {
  return page.sections.sections.find((section) => section.start === page.selected);
}

function groupsOf(sections) {
  return [...new Set(sections.map((section) => section.group))];
}

async function drawSections() {
  const reply = await ask("get_sections", { session_id: page.session });
  if (failed(reply) || !(await vocabulary())) {
    return;
  }
  page.sections = reply;
  page.table = reply.sections;
  const { sections } = reply;
  if (!sections.some((section) => section.start === page.selected)) {
    page.selected = sections[0].start;
  }
  drawStrip($("#section-strip"), sections, true);
  $("#seed").textContent = String(reply.seed);
  page.seed = reply.seed;
  drawEdits();
  drawGroup();
}

function drawEdits() {
  const { sections } = page.sections;
  const index = sections.indexOf(selected());
  const section = sections[index];
  const { split, move } = editBars(sections, index);
  $("#editing").textContent = `${section.group}: ${section.label}`;
  for (const [field, bounds, buttons] of [
    [$("#split-at"), split, ["#split-form button"]],
    [$("#move-to"), move, ["#move"]],
  ]) {
    const usable = bounds !== null && bounds[0] <= bounds[1];
    field.value = "";
    field.disabled = !usable;
    field.min = usable ? bounds[0] : "";
    field.max = usable ? bounds[1] : "";
    for (const button of buttons) {
      $(button).disabled = !usable;
    }
  }
  $("#merge").disabled = index === 0;
  $("#rename-name").value = section.name;
  $("#rename-group").value = section.group;
  $("#take").textContent = String(section.take);
}

/** A group's name, by its first section: its letter, bars and what it plays. */
function groupTitle(group) {
  const [first] = membersOf(page.sections, group);
  return `${group}: ${first.label}, ${first.plays}`;
}

function groupContext(group) {
  const members = membersOf(page.sections, group);
  const { controls: song } = page.sections;
  return { presets, song, defaults: page.defaults, members, before: page.sent[group] ?? {} };
}

function drawGroup() {
  const { sections, controls } = page.sections;
  const { group } = selected();
  const members = membersOf(page.sections, group);
  const groups = groupsOf(sections);
  const [first] = members;
  const title = groupTitle(group);
  $("#group-title").textContent = title;
  $("#next-group").disabled = groups.indexOf(group) === groups.length - 1;
  const questions = groupTabs(page.sections, group, presets, page.defaults);
  if (!questions.length) {
    // A group whose sections ask nothing has no round: they play no notes.
    page.round = null;
    $("#group-round").replaceChildren(element("p", {}, "Nothing to ask here: no drums play."));
    return;
  }
  const resolved = resolvedOf(first, controls, page.defaults);
  const ramp = Math.max(...members.map((section) => mostRamp(section.bars)));
  // Its Ramp tabs, kept in its draft, then any Ramp question due that no round shows yet.
  const ramps = page.rounds[group]?.draft?.ramps ?? [];
  drawShown(group, $("#group-round"), {
    id: `group-${groups.indexOf(group)}`,
    questions: [...questions, ...ramps, ...dueRamps()],
    fineTune: fineTune(GROUP_CONTROLS, resolved, ramp),
    follow: (tabs, draft) => shownGroup(tabs, draft, groupContext(group)),
    send: (tabs, draft) => sendGroup(group, tabs, draft),
    due: dueRamps,
  });
}

/** The Ramp tabs due, both of whose groups are asked about (ADR 0108), that no round's draft
 * holds yet. */
function dueRamps() {
  const held = new Set(
    Object.values(page.rounds).flatMap(({ draft }) => (draft?.ramps ?? []).map((tab) => tab.id)),
  );
  const due = rampTabs(page.sections, page.groupsAsked, presets, page.defaults);
  return due.filter((tab) => !held.has(tab.id));
}

/** Send a group's round's draft. Gives the echo, or the failed reply. */
async function sendGroup(group, tabs, draft) {
  const { controls, set } = groupControls(tabs, draft, groupContext(group));
  const replies = [];
  for (const { call, args } of groupCalls(controls)) {
    const reply = await ask(call, { session_id: page.session, ...args });
    if (failed(reply)) {
      return reply;
    }
    replies.push(reply);
  }
  page.sent[group] = set;
  page.groupsAsked.add(group);
  for (const tab of tabs) {
    page.asked.add(tab.id);
  }
  // The sections as they now are, which say what ramp questions are due.
  const reply = await ask("get_sections", { session_id: page.session });
  if (!failed(reply)) {
    page.sections = reply;
  }
  return echo(replies);
}

async function pick(start, focus) {
  page.selected = start;
  await drawSections();
  focus()?.focus();
}

async function edit(op, event) {
  event.preventDefault();
  const section = selected();
  const values = Object.fromEntries(new FormData(event.target));
  const change = sectionEdit(op, section, values);
  const reply = await ask("update_sections", { session_id: page.session, ops: [change] });
  if (failed(reply)) {
    return;
  }
  const { sections } = page.sections;
  page.sent = keptAfterEdit(page.sent, sections, reply.sections);
  page.rounds = roundsAfterEdit(page.rounds, sections, reply.sections);
  const before =sections[sections.indexOf(section) - 1];
  const start = { merge: before?.start, move: change.to }[op] ?? section.start;
  say(`The sections are changed: ${reply.sections.length} sections.`);
  await pick(start, () => $('#section-strip [aria-pressed="true"]'));
}

async function anotherTake() {
  const section = selected();
  const take = section.take + 1;
  const reply = await ask("render", {
    session_id: page.session,
    section_ids: [section.start],
    take,
  });
  if (failed(reply) || waits(reply)) {
    return;
  }
  say(`Take ${take} of ${section.label}.`);
  await pick(section.start, () => $("#another-take"));
}

async function songTake() {
  const styled = await ask("set_style", { session_id: page.session, seed: page.seed + 1 });
  if (failed(styled)) {
    return;
  }
  remember(styled);
  say(`A new take of the song, seed ${styled.seed}.`);
}

// 6. Review.

async function drawReview() {
  $("#said").replaceChildren();
  $("#heard").replaceChildren();
  const reply = await ask("render", { session_id: page.session });
  if (failed(reply) || waits(reply)) {
    return;
  }
  page.summary = reply.summary;
  $("#asked").textContent = `Questions asked: ${page.asked.size}`;
  $("#said").replaceChildren(
    ...reply.sections.map(({ start, bars, group, take, skip, says }) => {
      const left = skip ? ", left as it came in" : "";
      return element("li", {}, `${group}: ${barsLabel(start, bars)}, take ${take}${left}: ${says}`);
    }),
  );
  $("#heard").replaceChildren(...listenFor().map((line) => element("li", {}, line)));
  drawAnswers();
}

/** Each round's answers as applied, in words, with a way back to change them, and each group
 * with questions not asked yet. */
function drawAnswers() {
  const asks = (group) => groupTabs(page.sections, group, presets, page.defaults).length > 0;
  const keys = ["song", ...groupsOf(page.sections.sections).filter(asks)];
  $("#answers").replaceChildren(
    ...keys.map((key) => {
      const { lines } = page.rounds[key] ?? {};
      const whose = key === "song" ? "the drummer's" : `${key}'s`;
      const back = lines ? `Change ${whose} answers` : `Answer ${whose} questions`;
      const button = element("button", { type: "button", class: "retro-btn btn", "data-round": key }, back);
      const name = key === "song" ? "The drummer" : groupTitle(key);
      if (!lines) {
        return element("li", {}, element("p", {}, `${name}: not asked yet.`), button);
      }
      const answers = element("ul", {}, ...lines.map((line) => element("li", {}, line)));
      return element("li", {}, element("p", {}, name), answers, button);
    }),
  );
}

function listenFor() {
  const { conversion, creative } = page.summary;
  const lines = [...conversionLines(conversion), ...creativeLines(creative)];
  return lines.length ? lines : ["Every note plays as it was written, in the kit chosen to play it."];
}

// 7. Download.

function drawDownload() {
  const kit = kitNames[page.toKit] ?? page.toKit;
  const listen = page.summary ? ` Listen for: ${listenFor().join("; ")}.` : "";
  $("#listen").textContent =
    `Drag the file onto the track whose drum instrument is ${kit}, and play it from bar 1, or ` +
    `from the first bar of a section the review lists.${listen}`;
}

async function download() {
  const out = await ask("download", { session_id: page.session });
  if (!(out instanceof Uint8Array)) {
    if (!failed(out) && !waits(out)) {
      problem("The engine gave no file; start over.");
    }
    return;
  }
  page.downloads += 1;
  const name = downloadName(page.file.name, page.downloads);
  const url = URL.createObjectURL(new Blob([out], { type: "audio/midi" }));
  page.url = url;
  const link = element("a", { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_MS);
  $("#saved").textContent = `Saved as ${name}.`;
}

// Delete my file now.

function deleteFile() {
  worker.terminate();
  waiting = new Map();
  if (page.url) {
    URL.revokeObjectURL(page.url);
  }
  page = fresh();
  drawApplied();
  toChosen = false;
  // A move the ended worker never answered would otherwise hold every later one.
  moving = false;
  $("#midi").value = "";
  $("#chosen").textContent = "";
  $("#saved").textContent = "";
  $("#to-kits").disabled = true;
  $("#delete-box").hidden = true;
  for (const filled of ["#requests", "#song-round", "#group-round", "#said", "#heard", "#answers"]) {
    $(filled).replaceChildren();
  }
  // An opening the ended worker never answered leaves the button to open again.
  $("#open").disabled = !$("#from-map").options.length;
  startEngine();
  show("file");
  problem("");
  // Apart from the status, which the new engine's progress takes over, until a file is chosen.
  $("#deleted").textContent =
    "Your file is deleted: the engine that held it has ended, and starts again.";
}

$("#midi").addEventListener("change", () => choose($("#midi").files[0]));
$("#drop").addEventListener("dragover", (event) => event.preventDefault());
$("#drop").addEventListener("drop", (event) => {
  event.preventDefault();
  choose(event.dataTransfer.files[0]);
});
$("#to-kits").addEventListener("click", () => moveOn(false, () => go("kits")));
$("#from-map").addEventListener("change", () => {
  if (!toChosen) {
    $("#to-map").value = $("#from-map").value;
  }
});
$("#to-map").addEventListener("change", () => {
  toChosen = true;
});
$("#kits-form").addEventListener("submit", (event) => {
  event.preventDefault();
  openSong();
});
$("#check-form").addEventListener("submit", confirmCheck);
$("#requests").addEventListener("click", (event) => {
  if (event.target.name === "kits") {
    moveOn(false, () => go("kits"));
  }
});
// Moving on applies the round on screen (ADR 0124); its Next buttons stay for a Ramp question
// the applying brings up, and move on at their next click.
$("#to-sections").addEventListener("click", () => moveOn(true, () => go("sections")));
$("#section-strip").addEventListener("click", (event) => {
  const start = event.target.closest("button")?.dataset.start;
  if (start !== undefined) {
    moveOn(false, () => pick(Number(start), () => $(`#section-strip [data-start="${start}"]`)));
  }
});
for (const op of ["split", "merge", "move", "rename"]) {
  $(`#${op}-form`).addEventListener("submit", (event) => edit(op, event));
}
$("#another-take").addEventListener("click", anotherTake);
$("#song-take").addEventListener("click", songTake);
$("#next-group").addEventListener("click", () =>
  moveOn(true, () => {
    const { sections } = page.sections;
    const groups = groupsOf(sections);
    const next = groups[groups.indexOf(selected().group) + 1];
    return pick(sections.find((section) => section.group === next).start, () => $("#group-title"));
  }),
);
$("#to-review").addEventListener("click", () => moveOn(true, () => go("review")));
$("#answers").addEventListener("click", (event) => {
  const key = event.target.closest("button")?.dataset.round;
  if (key === "song") {
    moveOn(false, () => go("drummer"));
  } else if (key) {
    page.selected = membersOf(page.sections, key)[0].start;
    moveOn(false, () => go("sections"));
  }
});
$("#to-download").addEventListener("click", () => moveOn(false, () => go("download")));
$("#get").addEventListener("click", download);
$("#delete").addEventListener("click", () => {
  const { file, bars } = page;
  const song = bars ? `${file.name}, ${count(bars, "bar")}` : file.name;
  $("#delete-what").textContent =
    `This ends the engine, which holds your file, ${song}, and everything made from it, and ` +
    "starts again from step 1.";
  // Escape or the backdrop closes the dialog without a value, so a choice made before never
  // counts again.
  $("#delete-dialog").returnValue = "";
  openDialog($("#delete-dialog"));
});
// A click on a dialog's blurred backdrop closes it, as Escape does.
for (const dialog of document.querySelectorAll("dialog.modal")) {
  dialog.addEventListener("click", (event) => {
    if (onBackdrop(dialog, event)) {
      dialog.close();
    }
  });
}
$("#delete-dialog").addEventListener("close", () => {
  if ($("#delete-dialog").returnValue === "delete") {
    deleteFile();
  }
});
$("#reload").addEventListener("click", () => location.reload());
$("#last-applied").addEventListener("click", showApplied);
$("#steps").addEventListener("click", (event) => {
  const step = event.target.closest("button")?.dataset.step;
  if (step) {
    moveOn(false, () => go(step));
  }
});

startEngine();
show("file", false);
loadKits();
