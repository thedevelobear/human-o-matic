// The engine check: load the engine in a Web Worker with a progress bar, run the calls of
// check-flow.json on check-song.mid, a 304-bar song built in code, and show how long each took
// and whether the download is the file a native render gives (the website plan's PR 1). It
// stores nothing and asks nothing of another origin.

const bar = document.querySelector("progress");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const started = performance.now();

const worker = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
const waiting = new Map();
let next = 0;
let loaded;
const engineLoaded = new Promise((resolve) => {
  loaded = resolve;
});

worker.onmessage = ({ data }) => {
  if ("progress" in data) {
    bar.value = data.progress;
    status.textContent = `Loading the engine: ${data.step} loaded`;
    if (data.progress === 1) {
      loaded(performance.now());
    }
  } else if ("failed" in data) {
    status.textContent = data.failed;
  } else {
    waiting.get(data.id)(data);
    waiting.delete(data.id);
  }
};

function ask(request, file) {
  return new Promise((resolve) => {
    const id = next++;
    waiting.set(id, resolve);
    worker.postMessage({ id, request, file });
  });
}

function show(text) {
  const line = document.createElement("li");
  line.textContent = text;
  results.append(line);
}

function seconds(from, to) {
  return `${((to - from) / 1000).toFixed(2)} s`;
}

async function sha256(bytes) {
  if (!globalThis.crypto?.subtle) {
    return null;
  }
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function check() {
  const flow = await (await fetch("check-flow.json")).json();
  const song = new Uint8Array(await (await fetch(flow.song)).arrayBuffer());
  show(`Engine loaded in ${seconds(started, await engineLoaded)}`);
  status.textContent = "Rendering the test song";
  let session = null;
  const renderStarted = performance.now();
  for (const { call, args } of flow.calls) {
    const given = JSON.parse(JSON.stringify(args).replaceAll('"$session"', JSON.stringify(session)));
    const before = performance.now();
    const answer = await ask({ call, args: given }, call === "open_session" ? song : undefined);
    const took = seconds(before, performance.now());
    if (answer.error) {
      show(`${call}: ${answer.error}`);
      status.textContent = "The check failed";
      return;
    }
    if (answer.out instanceof Uint8Array) {
      const digest = await sha256(answer.out);
      const same = digest === null ? "not checked here" : digest === flow.sha256 ? "yes" : "NO";
      show(`${call}: ${took}, ${answer.out.length.toLocaleString()} bytes`);
      show(`The same file as a native render: ${same}`);
      continue;
    }
    const reply = JSON.parse(answer.out);
    if (reply.error) {
      show(`${call}: ${reply.error}`);
      status.textContent = "The check failed";
      return;
    }
    session = reply.session_id ?? session;
    const bars = reply.summary?.bars ? `, ${reply.summary.bars} bars` : "";
    show(`${call}: ${took}${bars}`);
  }
  show(`Every call on the test song: ${seconds(renderStarted, performance.now())}`);
  await ask({ call: "reset", args: {} });
  status.textContent = "Done. Nothing was stored or sent.";
}

check().catch(() => {
  status.textContent = "The check failed";
});
