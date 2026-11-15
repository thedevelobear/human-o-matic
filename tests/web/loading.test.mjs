// The loading view's state (ADR 0125), from the worker's messages as engine.js posts them.

import assert from "node:assert/strict";
import { test } from "node:test";

import { engineState } from "../../src/human_o_matic/web/static/js/loading.js";

test("before the first step the bar is empty, and each step shows its real share", () => {
  assert.deepEqual(engineState({}), { phase: "loading", text: "Loading the engine", value: 0 });
  assert.deepEqual(engineState({ progress: 0.7164, step: "runtime" }), {
    phase: "loading",
    text: "Loading the engine: the Python runtime loaded, 71%",
    value: 0.7164,
  });
  assert.equal(engineState({ progress: 0.999, step: "wheels" }).text, "Loading the engine: the engine's libraries loaded, 99%");
});

test("the engine is ready only at the whole of its bytes, and a failure says why", () => {
  assert.deepEqual(engineState({ progress: 1, step: "app" }), {
    phase: "ready",
    text: "The engine is ready.",
    value: 1,
  });
  assert.deepEqual(engineState({ failed: "this browser couldn't start it" }), {
    phase: "failed",
    text: "The engine couldn't load: this browser couldn't start it.",
    value: 0,
  });
});
