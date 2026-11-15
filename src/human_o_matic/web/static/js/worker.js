// The page's Web Worker: it loads the engine from the site and answers the page's calls one at a
// time, in the order they came, as the MCP server's lock does. A message is `{id, request, file}`,
// and its answer `{id, out}`, compact JSON text or a file's bytes, or `{id, error}`. While the
// engine loads it posts `{progress, step}`, and `{failed}` if it can't.

import { startEngine } from "./engine.js";

const ready = startEngine({
  base: new URL("../", import.meta.url),
  read: async (url) => {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`${url.pathname}: ${response.status}`);
    }
    return new Uint8Array(await response.arrayBuffer());
  },
  place: (url) => url.href,
  progress: (progress, step) => postMessage({ progress, step }),
});
ready.catch(() =>
  postMessage({ failed: "its files stopped loading, which a lost connection can cause, so check it and reload the page" }),
);

let queue = Promise.resolve();

onmessage = ({ data: { id, request, file } }) => {
  queue = queue.then(async () => {
    try {
      const { call } = await ready;
      const out = call(request, file);
      postMessage({ id, out }, out instanceof Uint8Array ? [out.buffer] : []);
    } catch {
      postMessage({ id, error: "the engine failed; start over" });
    }
  });
};
