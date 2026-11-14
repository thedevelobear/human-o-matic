// The engine under Pyodide in Node: the calls of flow.json on the built site's test song give
// the download whose SHA-256 the flow holds, as they do natively (ADRs 0100 and 0112). It loads
// what `uv run python tools/build_site.py build` wrote into dist/site/, so the build runs first.

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

test("a call off the allowlist is an error in plain words under Pyodide", async () => {
  const { call } = await engine();

  const reply = JSON.parse(call({ call: "export", args: {} }));

  assert.match(reply.error, /^the request: call: Input should be/);
});
