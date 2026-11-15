// The engine under Pyodide in Node: the calls of flow.json on the built site's test song give
// the download whose SHA-256 the flow holds, as they do natively (ADRs 0100 and 0112), and the
// page's forms, as it serves them, make calls the engine takes. It loads what
// `uv run python tools/build_site.py build` wrote into dist/site/, so the build runs first.

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const site = new URL("../../dist/site/", import.meta.url);
const flow = JSON.parse(await readFile(new URL("flow.json", import.meta.url), "utf8"));

async function engine() {
  await access(new URL("engine.json", site)).catch(() => {
    throw new Error("no built site: run `uv run python tools/build_site.py build` first");
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
}

test("the flow's calls under Pyodide download the file of the flow's SHA-256", async () => {
  const { call, steps } = await engine();
  const data = new Uint8Array(await readFile(fileURLToPath(new URL(flow.song, site))));
  let session = null;
  let digest = null;
  for (const { call: name, args } of flow.calls) {
    const given = JSON.parse(JSON.stringify(args).replaceAll('"$session"', JSON.stringify(session)));
    const out = call({ call: name, args: given }, name === "open_session" ? data : undefined);
    if (out instanceof Uint8Array) {
      digest = createHash("sha256").update(out).digest("hex");
      continue;
    }
    const reply = JSON.parse(out);
    assert.equal(reply.error, undefined, `${name}: ${reply.error}`);
    session = reply.session_id ?? session;
  }

  assert.equal(digest, flow.sha256);
  assert.deepEqual(
    steps.map(([, step]) => step),
    ["runtime", "packages", "wheels", "app"],
  );
  assert.equal(steps.at(-1)[0], 1);
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

test("a call off the allowlist is an error in plain words under Pyodide", async () => {
  const { call } = await engine();

  const reply = JSON.parse(call({ call: "export", args: {} }));

  assert.match(reply.error, /^the request: call: Input should be/);
});
