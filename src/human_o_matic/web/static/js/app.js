// The page: its steps from choosing a file to the download, over the engine in a Web Worker
// (ADR 0100), called by the worker API one call at a time (ADR 0114). The engine starts loading
// as the page opens. The page never sees a note and stores nothing: the chosen file's bytes stay
// in this page's memory and the worker's until "Delete my file now" ends the worker, or the tab
// is closed (the website plan's section 8). The rounds' questions come in feat/web-questions:
// until then each round is its Submit tab, with Fine-tune.

import { drawFields, element, readFields } from "./fields.js";
import {
  GROUP_CONTROLS,
  SONG_CONTROLS,
  batch,
  editBars,
  fineTune,
  form,
  kitOptions,
  mostRamp,
  sectionEdit,
  touchedControls,
} from "./forms.js";
import { barsLabel, conversionLines, creativeLines, downloadName } from "./review.js";
import { drawRound } from "./round.js";

const STEPS = ["file", "kits", "check", "drummer", "sections", "review", "download"];
// How long a download's Blob URL lives after the download starts.
const REVOKE_MS = 10_000;
const $ = (selector) => document.querySelector(selector);

let worker;
let waiting = new Map();
let calls = 0;
let kitNames = {};
// Whether the kit to play the file was chosen, so it no longer follows the kit it came from.
let toChosen = false;
let page = fresh();

/** What the page holds of one file, from choosing it to deleting it. */
function fresh() {
  return {
    file: null,
    open: {},
    session: null,
    toKit: null,
    decisions: [],
    table: [],
    sections: null,
    defaults: null,
    seed: 0,
    selected: 0,
    summary: null,
    downloads: 0,
    url: null,
    reached: "file",
  };
}

// The engine.

function startEngine() {
  $("#engine").value = 0;
  worker = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }) => {
    if ("progress" in data) {
      $("#engine").value = data.progress;
      say(data.progress === 1 ? "The engine is ready." : `Loading the engine: ${data.step} loaded`);
    } else if ("failed" in data) {
      problem(data.failed);
    } else {
      waiting.get(data.id)?.(data);
      waiting.delete(data.id);
    }
  };
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

function say(text) {
  $("#status").textContent = text;
}

function problem(text) {
  $("#problem").textContent = text;
}

// The steps.

/** Show `step` alone, the steps reached so far open in the top bar, and move focus to its
 * heading unless `focus` is false. */
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
    $(`#${step}-title`).focus();
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
  show(step);
  await ENTER[step]?.();
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
  page = { ...fresh(), file: { name: file.name, bytes: new Uint8Array(await file.arrayBuffer()) } };
  problem("");
  $("#chosen").textContent = `Chosen: ${file.name}`;
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
  say("Opening the song");
  await ask("reset");
  const reply = await ask(
    "open_session",
    { name: page.file.name, from_map: $("#from-map").value, to_map: $("#to-map").value, ...page.open },
    page.file.bytes,
  );
  if (failed(reply)) {
    say("");
    return;
  }
  page.session = reply.session_id ?? null;
  page.toKit = reply.to_kit ?? null;
  page.decisions = reply.decisions;
  page.table = reply.sections ?? [];
  page.reached = "kits";
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
      const button = element("button", { type: "button", "aria-pressed": pressed }, text);
      button.dataset.start = section.start;
      return element("li", {}, button);
    }),
  );
}

async function drawCheck() {
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
  await go("drummer");
}

// 4. Drummer, the song-wide round.

function remember(styled) {
  page.defaults = styled.defaults;
  page.seed = styled.seed;
  $("#seed").textContent = String(styled.seed);
}

async function drawDrummer() {
  const styled = await ask("set_style", { session_id: page.session });
  if (failed(styled)) {
    return;
  }
  remember(styled);
  const resolved = { ...styled.defaults, ...styled.controls, style: styled.style };
  drawRound($("#song-round"), {
    id: "song",
    name: "The drummer",
    questions: [],
    fineTune: fineTune(SONG_CONTROLS, resolved),
    send: sendSong,
  });
}

async function sendSong({ values, touched }) {
  const { style, tightness, ...controls } = touchedControls(values, touched);
  // The round as it stands: its style, and the controls touched.
  const styled = await ask("set_style", {
    session_id: page.session,
    style: values.style,
    ...(tightness !== undefined && { tightness }),
  });
  if (failed(styled)) {
    return "Not sent";
  }
  remember(styled);
  if (Object.keys(controls).length) {
    const reply = await ask("set_section_controls", { session_id: page.session, controls });
    if (failed(reply)) {
      return "Not sent";
    }
  }
  return "Sent.";
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
  if (failed(reply)) {
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

function drawGroup() {
  const { sections, controls } = page.sections;
  const { group } = selected();
  const members = sections.filter((section) => section.group === group);
  const groups = groupsOf(sections);
  const [first] = members;
  const resolved = { ...page.defaults, ...controls, ...first.controls };
  const ramp = Math.max(...members.map((section) => mostRamp(section.bars)));
  const title = `${group}: ${first.label}, ${first.plays}`;
  $("#group-title").textContent = title;
  drawRound($("#group-round"), {
    id: `group-${groups.indexOf(group)}`,
    name: title,
    questions: [],
    fineTune: fineTune(GROUP_CONTROLS, resolved, ramp),
    send: async ({ values, touched }) => {
      const reply = await ask("set_section_controls", {
        session_id: page.session,
        controls: touchedControls(values, touched),
        section_ids: members.map((section) => section.start),
      });
      return failed(reply) ? "Not sent" : "Sent.";
    },
  });
  $("#next-group").disabled = groups.indexOf(group) === groups.length - 1;
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
  const before = sections[sections.indexOf(section) - 1];
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
  if (failed(reply)) {
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
  if (failed(reply)) {
    return;
  }
  if (reply.decisions.length) {
    problem("Some notes still wait for an answer: see step 3, Check.");
    return;
  }
  page.summary = reply.summary;
  $("#said").replaceChildren(
    ...reply.sections.map(({ start, bars, group, take, skip, says }) => {
      const left = skip ? ", left as it came in" : "";
      return element("li", {}, `${group}: ${barsLabel(start, bars)}, take ${take}${left}: ${says}`);
    }),
  );
  $("#heard").replaceChildren(...listenFor().map((line) => element("li", {}, line)));
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
    if (!failed(out)) {
      problem("Some notes still wait for an answer: see step 3, Check.");
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
  toChosen = false;
  $("#midi").value = "";
  $("#chosen").textContent = "";
  $("#saved").textContent = "";
  $("#to-kits").disabled = true;
  $("#delete-box").hidden = true;
  for (const filled of ["#requests", "#song-round", "#group-round", "#said", "#heard"]) {
    $(filled).replaceChildren();
  }
  startEngine();
  show("file");
  problem("");
  say("Your file is deleted: the engine that held it has ended, and starts again.");
}

$("#midi").addEventListener("change", () => choose($("#midi").files[0]));
$("#drop").addEventListener("dragover", (event) => event.preventDefault());
$("#drop").addEventListener("drop", (event) => {
  event.preventDefault();
  choose(event.dataTransfer.files[0]);
});
$("#to-kits").addEventListener("click", () => go("kits"));
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
    go("kits");
  }
});
$("#to-sections").addEventListener("click", () => go("sections"));
$("#section-strip").addEventListener("click", (event) => {
  const start = event.target.closest("button")?.dataset.start;
  if (start !== undefined) {
    pick(Number(start), () => $(`#section-strip [data-start="${start}"]`));
  }
});
for (const op of ["split", "merge", "move", "rename"]) {
  $(`#${op}-form`).addEventListener("submit", (event) => edit(op, event));
}
$("#another-take").addEventListener("click", anotherTake);
$("#song-take").addEventListener("click", songTake);
$("#next-group").addEventListener("click", () => {
  const { sections } = page.sections;
  const groups = groupsOf(sections);
  const next = groups[groups.indexOf(selected().group) + 1];
  pick(sections.find((section) => section.group === next).start, () => $("#group-title"));
});
$("#to-review").addEventListener("click", () => go("review"));
$("#to-download").addEventListener("click", () => go("download"));
$("#get").addEventListener("click", download);
$("#delete").addEventListener("click", deleteFile);
$("#steps").addEventListener("click", (event) => {
  const step = event.target.closest("button")?.dataset.step;
  if (step) {
    go(step);
  }
});

startEngine();
show("file", false);
loadKits();
