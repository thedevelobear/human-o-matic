// The tabs' keyboard and ARIA (ADR 0111), as the website plan's PR 3 lists them, on the pure
// module the page draws, with questions made up here: the page's own come in feat/web-questions.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BY_HAND,
  SUBMIT,
  answer,
  aria,
  choose,
  join,
  key,
  round,
  select,
  setByHand,
  step,
} from "../../src/human_o_matic/web/static/js/tabs.js";

const answers = (count) =>
  Array.from({ length: count }, (_, n) => ({ label: `answer ${n + 1}`, description: `sets ${n}` }));
const QUESTIONS = [
  { id: "energy", label: "Energy", answers: answers(12) },
  { id: "soft", label: "Soft notes", answers: answers(3) },
  { id: "fill", label: "Fill", answers: answers(3), given: 1 },
];
const RAMP = { id: "ramp", label: "Ramp", answers: answers(3) };

const first = () => round("B: bars 9 to 24", QUESTIONS);
const ids = (state) => state.tabs.map((tab) => tab.id);
const on = (state, current) => select(state, current);

test("a round's tabs are its questions, then Submit, each question ending with Set it by hand", () => {
  const state = first();

  assert.deepEqual(ids(state), ["energy", "soft", "fill", SUBMIT]);
  assert.deepEqual(state.tabs[1].answers.at(-1), BY_HAND);
  assert.equal(state.tabs[1].answers.length, 4);
  assert.deepEqual(state.tabs.at(-1).answers, []);
});

test("the pointer starts on the answer given before, or else on the first", () => {
  const state = first();

  assert.deepEqual(state.choice, { energy: 0, soft: 0, fill: 1 });
  assert.deepEqual(state.answered, { fill: 1 });
});

test("Left and Right move between tabs on the strip and wrap at the ends", () => {
  const state = first();

  assert.equal(key(state, "ArrowRight", "tab").current, 1);
  assert.equal(key(on(state, 3), "ArrowRight", "tab").current, 0);
  assert.equal(key(state, "ArrowLeft", "tab").current, 3);
  assert.equal(key(on(state, 2), "ArrowLeft", "tab").current, 1);
  assert.equal(key(state, "ArrowRight", "tab").focus, "tab");
});

test("Home and End go to the first and last tab", () => {
  const state = on(first(), 1);

  assert.equal(key(state, "Home", "tab").current, 0);
  assert.equal(key(state, "End", "tab").current, 3);
  assert.equal(key(state, "End", "tab").focus, "tab");
});

test("the number keys move the choice to the answer with that number and no other", () => {
  const state = first();

  const moved = key(state, "4", "answer");

  assert.deepEqual(moved.choice, { ...state.choice, energy: 3 });
  assert.equal(moved.focus, "answer");
  assert.equal(key(state, "9", "answer").choice.energy, 8);
  const soft = on(state, 1);
  assert.equal(key(soft, "4", "answer").choice.soft, 3);
  assert.equal(key(soft, "5", "answer"), soft);
  assert.equal(key(state, "0", "answer"), state);
});

test("the number keys do nothing in a slider or field of Set it by hand, or on the strip", () => {
  const state = first();

  for (const digit of ["1", "2", "5", "9"]) {
    assert.equal(key(state, digit, "hand"), state);
    assert.equal(key(state, digit, "tab"), state);
  }
});

test("a click or Enter answers, and the arrow and number keys don't", () => {
  const state = first();

  assert.deepEqual(answer(state, 2).answered, { ...state.answered, energy: 2 });
  assert.deepEqual(key(choose(state, 5), "Enter", "answer").answered, {
    ...state.answered,
    energy: 5,
  });
  for (const pressed of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "3", "7"]) {
    assert.deepEqual(key(state, pressed, "answer").answered, state.answered, pressed);
  }
  assert.deepEqual(choose(state, 4).answered, state.answered);
});

test("the arrow keys in the answers are the platform's radio group's, so the round leaves them", () => {
  const state = first();

  for (const pressed of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"]) {
    assert.equal(key(state, pressed, "answer"), state, pressed);
  }
  assert.deepEqual(choose(state, 4).choice, { ...state.choice, energy: 4 });
});

test("a click stays on the tab, with focus where it is", () => {
  const clicked = answer(first(), 2);

  assert.equal(clicked.current, 0);
  assert.equal(clicked.focus, null);
});

test("Enter opens the next tab with focus on its current answer", () => {
  const state = first();

  const next = key(state, "Enter", "answer");

  assert.equal(next.current, 1);
  assert.equal(next.focus, "answer");
  assert.equal(key(on(state, 1), "Enter", "answer").current, 2);
});

test("after the last question, Enter opens Submit with focus on its first control", () => {
  const next = key(on(first(), 2), "Enter", "answer");

  assert.equal(next.tabs[next.current].id, SUBMIT);
  assert.equal(next.focus, "submit");
  assert.deepEqual(next.answered, { fill: 1 });
});

test("Enter on Set it by hand answers it and opens its controls, and Enter in them goes on", () => {
  const state = first();
  const hand = state.tabs[0].answers.length - 1;

  const opened = key(choose(state, hand), "Enter", "answer");

  assert.equal(opened.current, 0);
  assert.equal(opened.focus, "hand");
  assert.equal(opened.answered.energy, hand);
  const onward = key(opened, "Enter", "hand");
  assert.equal(onward.current, 1);
  assert.equal(onward.focus, "answer");
});

test("changing a control of Set it by hand answers the question with it", () => {
  const state = on(first(), 1);

  const set = setByHand(state);

  assert.equal(set.answered.soft, 3);
  assert.equal(set.choice.soft, 3);
  assert.equal(set.focus, null);
});

test("the strip's arrow buttons move between tabs, wrapping, and leave focus on the button", () => {
  const state = first();

  assert.equal(step(state, -1).current, 3);
  assert.equal(step(on(state, 3), 1).current, 0);
  assert.equal(step(state, 1).focus, null);
});

test("a Ramp tab joining goes before Submit and leaves the current tab and focus where they are", () => {
  for (const current of [0, 2, 3]) {
    const state = on(first(), current);

    const joined = join(state, RAMP);

    assert.deepEqual(ids(joined), ["energy", "soft", "fill", "ramp", SUBMIT]);
    assert.equal(joined.tabs[joined.current].id, state.tabs[current].id);
    assert.equal(joined.focus, null);
    assert.equal(joined.choice.ramp, 0);
    assert.deepEqual(joined.answered, state.answered);
  }
  const typed = key(join(on(first(), 3), RAMP), "ArrowRight", "tab");
  assert.equal(typed.tabs[typed.current].id, "energy");
});

/** States the keyboard and clicks reach from the first, by a fixed sequence of random steps. */
function* states() {
  let seed = 7;
  const next = (below) => {
    seed = (seed * 1103515245 + 12345) % 2 ** 31;
    return seed % below;
  };
  const keys = ["ArrowLeft", "ArrowRight", "Home", "End", "Enter", "1", "3", "9", "Tab"];
  const wheres = ["tab", "answer", "hand", "submit"];
  for (let walk = 0; walk < 50; walk += 1) {
    let state = first();
    yield state;
    for (let move = 0; move < 30; move += 1) {
      const tab = state.tabs[state.current];
      const roll = next(10);
      if (roll === 0) {
        state = select(state, next(state.tabs.length));
      } else if (roll === 1 && tab.answers.length) {
        state = answer(state, next(tab.answers.length));
      } else if (roll === 2 && !state.tabs.some((found) => found.id === RAMP.id)) {
        state = join(state, RAMP);
      } else {
        state = key(state, keys[next(keys.length)], wheres[next(wheres.length)]);
      }
      yield state;
    }
  }
}

test("in every state exactly one tab is selected and in the tab order, with its panel shown", () => {
  for (const state of states()) {
    const { tablist, tabs } = aria(state, "round");
    const selected = tabs.filter(({ tab }) => tab["aria-selected"] === "true");

    assert.equal(tablist.role, "tablist");
    assert.equal(tablist["aria-label"], "B: bars 9 to 24");
    assert.equal(selected.length, 1);
    assert.deepEqual(
      tabs.filter(({ tab }) => tab.tabindex === "0"),
      selected,
    );
    assert.deepEqual(
      tabs.filter(({ panel }) => !panel.hidden),
      selected,
    );
    for (const { tab } of tabs) {
      assert.equal(tab.role, "tab");
      assert.ok(["true", "false"].includes(tab["aria-selected"]));
      assert.equal(tab.tabindex, tab["aria-selected"] === "true" ? "0" : "-1");
    }
  }
});

test("each tab's aria-controls names its panel, and each panel's aria-labelledby its tab", () => {
  for (const state of states()) {
    const { tabs } = aria(state, "round");
    const panels = new Set(tabs.map(({ panel }) => panel.id));

    assert.equal(panels.size, tabs.length);
    for (const { tab, panel } of tabs) {
      assert.equal(tab["aria-controls"], panel.id);
      assert.equal(panel["aria-labelledby"], tab.id);
      assert.equal(panel.role, "tabpanel");
    }
  }
});

test("an answered tab says so in its name, and an unanswered one doesn't", () => {
  for (const state of states()) {
    for (const [index, { tab, answered }] of aria(state, "round").tabs.entries()) {
      const { id, label } = state.tabs[index];
      assert.equal(answered, id in state.answered);
      assert.equal(tab["aria-label"], answered ? `${label}, answered` : label);
    }
  }
});
