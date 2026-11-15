// What the loading view shows while the engine loads in the page's worker (ADR 0125): the
// worker's messages, `{progress, step}` after each step with the share of the engine's bytes
// loaded, or `{failed}`, as the view's state. Before the first step nothing is loaded, so the bar
// starts empty. It touches no DOM, so `node --test` loads it.

const STEPS = {
  runtime: "the Python runtime",
  packages: "numpy",
  wheels: "the engine's libraries",
  app: "the app",
};

/**
 * The loading view's state for a message of the worker, or `{}` before any.
 *
 * @returns {{phase: "loading" | "ready" | "failed", text: string, value: number}} Whether the
 *   engine loads, is ready or failed, what to say, and the bar's value.
 */
export function engineState(message) {
  if ("failed" in message) {
    return { phase: "failed", text: `The engine couldn't load: ${message.failed}.`, value: 0 };
  }
  if (!("progress" in message)) {
    return { phase: "loading", text: "Loading the engine", value: 0 };
  }
  if (message.progress >= 1) {
    return { phase: "ready", text: "The engine is ready.", value: 1 };
  }
  const loaded = STEPS[message.step] ?? message.step;
  const share = Math.floor(message.progress * 100);
  return { phase: "loading", text: `Loading the engine: ${loaded} loaded, ${share}%`, value: message.progress };
}
