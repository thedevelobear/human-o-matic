// The question window (ADR 0111): a round's strip of tabs between two arrow buttons, each
// question's panel with its numbered answers and "Set it by hand", and the Submit tab with
// Fine-tune, drawn over the pure state of tabs.js. A round's questions are data: the page's own
// come in feat/web-questions. The tabs and Next send nothing; only Submit's button does, through
// `send`. Elements are made once and then updated in place, so focus stays where it is unless
// the state says to move it.

import { drawFields, element, readFields } from "./fields.js";
import {
  SUBMIT,
  answer,
  aria,
  byHand,
  choose,
  join,
  key,
  round,
  select,
  setByHand,
  step,
} from "./tabs.js";

/**
 * Draw a round in `parent`, replacing what it held.
 *
 * @param {HTMLElement} parent
 * @param {object} options
 * @param {string} options.id What its elements' ids start with.
 * @param {string} options.name The round's name, which labels its strip.
 * @param {Array<object>} options.questions As tabs.js's `round` takes them, each with its
 *   `question`, and what its section `plays`, its `pattern`'s lines, and `hand`, the fields of
 *   its own controls, where it has them.
 * @param {Array<object>} options.fineTune The Submit tab's fields.
 * @param {(round: {answered: object, hand: object, values: object, touched: Set<string>}) =>
 *   Promise<string>} options.send Sends the round as it stands, and gives what to say.
 * @returns {{join: (question: object) => void}} `join` adds a question before Submit.
 */
export function drawRound(parent, { id, name, questions, fineTune, send }) {
  let state = round(name, questions);
  let byPointer = false;
  let sending = false;
  const touched = new Set();
  const drawn = new Map();
  const strip = element("div");
  const panels = element("div");
  const previous = arrow("Previous question", "←");
  const following = arrow("Next question", "→");
  // The round's own element, which takes its keys, so a round drawn again leaves none behind.
  const frame = element("div", {}, element("div", { class: "tabbar" }, previous, strip, following));
  frame.append(panels);
  parent.replaceChildren(frame);

  function questionPanel(tab) {
    const answers = element("fieldset", { class: "answers" }, element("legend", {}, tab.question));
    if (tab.plays) {
      answers.append(element("p", {}, tab.plays));
    }
    if (tab.pattern) {
      answers.append(element("pre", {}, tab.pattern.join("\n")));
    }
    for (const [index, { label, description }] of tab.answers.entries()) {
      const radio = `${id}-${tab.id}-${index}`;
      answers.append(
        element(
          "div",
          { class: "choice" },
          element("input", {
            type: "radio",
            id: radio,
            name: `${id}-${tab.id}`,
            value: index,
            "aria-describedby": `${radio}-about`,
          }),
          element("label", { for: radio }, `${index + 1}. ${label}`),
          element("p", { id: `${radio}-about`, class: "hint" }, description),
        ),
      );
    }
    const hand = element("div", { class: "hand" });
    drawFields(hand, tab.hand ?? [], `${id}-${tab.id}`);
    return element("div", { "data-tab": tab.id }, answers, hand);
  }

  function submitPanel() {
    const fine = element("div", { class: "fine-tune" });
    drawFields(fine, fineTune, `${id}-fine`);
    const button = element("button", { type: "button", class: "send" }, "Submit");
    const said = element("p", { role: "status" });
    button.addEventListener("click", async () => {
      if (sending) {
        return;
      }
      sending = true;
      said.textContent = "Sending";
      const hand = Object.fromEntries(
        state.tabs
          .filter((tab) => tab.id !== SUBMIT)
          .map((tab) => [tab.id, readFields(drawn.get(tab.id).panel.querySelector(".hand"))]),
      );
      try {
        said.textContent = await send({
          answered: state.answered,
          hand,
          values: readFields(fine),
          touched,
        });
      } finally {
        sending = false;
      }
    });
    const summary = element("ul", { class: "summary" });
    const heading = element("h3", {}, "Fine-tune");
    return element("div", { "data-tab": SUBMIT }, summary, heading, fine, button, said);
  }

  function update(next) {
    state = next;
    for (const [index, tab] of state.tabs.entries()) {
      if (drawn.has(tab.id)) {
        continue;
      }
      const glyph = element("span", { class: "glyph", "aria-hidden": "true" });
      const made = {
        button: element("button", { type: "button" }, glyph, tab.label),
        panel: tab.id === SUBMIT ? submitPanel() : questionPanel(tab),
      };
      // A tab that joins goes before the first tab already drawn after it: Submit.
      const after = state.tabs.slice(index + 1).find((later) => drawn.has(later.id));
      strip.insertBefore(made.button, after ? drawn.get(after.id).button : null);
      panels.insertBefore(made.panel, after ? drawn.get(after.id).panel : null);
      drawn.set(tab.id, made);
    }
    const attributes = aria(state, id);
    setAttributes(strip, attributes.tablist);
    for (const [index, { answered, tab, panel }] of attributes.tabs.entries()) {
      const shown = state.tabs[index];
      const { button, panel: box } = drawn.get(shown.id);
      setAttributes(button, tab);
      setAttributes(box, panel);
      button.querySelector(".glyph").textContent =
        shown.id === SUBMIT ? "" : answered ? "✓" : "□";
      if (shown.id !== SUBMIT) {
        const choice = state.choice[shown.id];
        box.querySelectorAll(".answers input")[choice].checked = true;
        const opened = byHand(shown, choice) || byHand(shown, state.answered[shown.id]);
        box.querySelector(".hand").hidden = !opened;
      }
    }
    drawSummary();
    moveFocus();
  }

  function drawSummary() {
    const asked = state.tabs.filter((tab) => tab.id !== SUBMIT);
    drawn
      .get(SUBMIT)
      .panel.querySelector(".summary")
      .replaceChildren(
        ...asked.map((tab) => {
          const given = state.answered[tab.id];
          const said = given === undefined ? "your call" : tab.answers[given].label;
          return element("li", {}, `${tab.label}: ${said}`);
        }),
      );
  }

  function moveFocus() {
    const tab = state.tabs[state.current];
    const { button, panel } = drawn.get(tab.id);
    const controls = "input, select, button";
    const target = {
      tab: button,
      answer: panel.querySelector(".answers input:checked"),
      hand: panel.querySelector(`.hand :is(${controls})`),
      submit: panel.querySelector(controls),
    }[state.focus];
    target?.focus();
  }

  function where(target) {
    if (target.getAttribute("role") === "tab") {
      return "tab";
    }
    if (target.closest(".hand")) {
      return "hand";
    }
    if (target.type === "radio" && target.closest(".answers")) {
      return "answer";
    }
    return target.closest(`[data-tab="${SUBMIT}"]`) ? "submit" : null;
  }

  previous.addEventListener("click", () => update(step(state, -1)));
  following.addEventListener("click", () => update(step(state, 1)));
  strip.addEventListener("click", (event) => {
    const button = event.target.closest('[role="tab"]');
    if (button) {
      update(select(state, [...strip.children].indexOf(button)));
    }
  });
  // A click answers and the keyboard's own clicks on a radio don't: a click follows a press of
  // the pointer, and any key since cancels it.
  panels.addEventListener("pointerdown", () => {
    byPointer = true;
  });
  frame.addEventListener("keydown", (event) => {
    byPointer = false;
    const found = where(event.target);
    if (!found || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
      return;
    }
    const next = key(state, event.key, found);
    if (next !== state) {
      event.preventDefault();
      update(next);
    }
  });
  panels.addEventListener("click", (event) => {
    if (where(event.target) === "answer" && byPointer) {
      byPointer = false;
      update(answer(state, Number(event.target.value)));
    }
  });
  for (const type of ["input", "change"]) {
    panels.addEventListener(type, (event) => {
      const found = where(event.target);
      if (found === "answer" && type === "change") {
        update(choose(state, Number(event.target.value)));
      } else if (found === "hand") {
        update(setByHand(state));
      } else if (event.target.closest(".fine-tune")) {
        touched.add(event.target.name);
      }
    });
  }
  update(state);
  return { join: (question) => update(join(state, question)) };
}

function arrow(label, glyph) {
  return element(
    "button",
    { type: "button", class: "arrow", "aria-label": label },
    element("span", { "aria-hidden": "true" }, glyph),
  );
}

/** Set each attribute, `hidden` as the attribute it is. */
function setAttributes(target, attributes) {
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "hidden") {
      target.hidden = value;
    } else {
      target.setAttribute(name, value);
    }
  }
}
