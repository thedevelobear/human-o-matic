// The engine as the page's Web Worker and the Pyodide test in Node both load it: Pyodide, the
// wheels and the app's source, read from the site by `engine.json`, then the worker API's one
// entry, `human_o_matic.web.worker.handle` (ADRs 0100 and 0112). It touches no DOM, and reads
// files only through `read`, so the same code runs in a browser and in Node.

/**
 * Load the engine and return its `call`.
 *
 * @param {object} options
 * @param {URL} options.base The site's root.
 * @param {(url: URL) => Promise<Uint8Array>} options.read Reads one of the site's files.
 * @param {(url: URL) => string} options.place What Pyodide's `indexURL` is for a folder of the
 *   site: its URL in a browser, its path in Node.
 * @param {(done: number, step: string) => void} [options.progress] Called after each step with
 *   the share of the engine's bytes loaded so far, from 0 to 1.
 */
export async function startEngine({ base, read, place, progress = () => {} }) {
  const manifest = JSON.parse(new TextDecoder().decode(await read(new URL("engine.json", base))));
  const sizes = manifest.bytes;
  const total = sizes.runtime + sizes.packages + sizes.wheels + sizes.app;
  let loaded = 0;
  const step = (bytes, name) => {
    loaded += bytes;
    progress(loaded / total, name);
  };

  const runtime = new URL(manifest.pyodide, base);
  const { loadPyodide } = await import(new URL("pyodide.mjs", runtime).href);
  const pyodide = await loadPyodide({ indexURL: place(runtime) });
  step(sizes.runtime, "runtime");

  await pyodide.loadPackage(manifest.packages, { messageCallback: () => {} });
  step(sizes.packages, "packages");

  for (const wheel of manifest.wheels) {
    pyodide.unpackArchive(await read(new URL(wheel, base)), "wheel");
  }
  step(sizes.wheels, "wheels");

  pyodide.unpackArchive(await read(new URL(manifest.app, base)), "zip", { extractDir: "/app" });
  pyodide.runPython("import sys; sys.path.insert(0, '/app/src')");
  const handle = pyodide.pyimport("human_o_matic.web.worker").handle;
  step(sizes.app, "app");

  /**
   * One call of the worker API: compact JSON text, or for a `download`, the file's bytes.
   *
   * @param {{call: string, args?: object}} request
   * @param {Uint8Array} [data] The chosen file's bytes, beside an `open_session`.
   * @returns {string | Uint8Array}
   */
  function call(request, data) {
    const bytes = data === undefined ? undefined : pyodide.toPy(data);
    try {
      const out = handle(JSON.stringify(request), bytes);
      if (typeof out === "string") {
        return out;
      }
      try {
        return out.toJs();
      } finally {
        out.destroy();
      }
    } finally {
      bytes?.destroy?.();
    }
  }

  return { call };
}
