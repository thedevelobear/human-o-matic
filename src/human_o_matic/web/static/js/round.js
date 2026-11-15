// A round of questions on one card (ADR 0124): each question a fieldset of numbered native
// radios with their one-line descriptions, "your call" chosen until another answer is, and "Set
// it by hand" opening that question's own controls under it; then the round's Fine-tune and a
// line that says whether the round is applied. A round's questions are data, from questions.js,
// whose words it shows starting with a capital.
// It sends nothing: its answers are a draft, which `keep` hands the page on every change, and the
// page applies the round when the user moves on.

import { drawFields, element, readFields, writeFields } from "./fields.js";
import { capital, touchedControls } from "./forms.js";

export const BY_HAND = {
  label: "Set it by hand",
  description: "this question's controls, from where the section is now",
};

/**
 * Draw a round in `parent`, replacing what it held, with the answers of `draft`.
 *
 * @param {HTMLElement} parent
 * @param {object} options
 * @param {string} options.id What its elements' ids start with.
 * @param {Array<object>} options.questions questions.js's tabs, each with its `question`, its
 *   `answers` but "Set it by hand", and what its section `plays`, its `pattern`'s lines, and
 *   `hand`, the fields of its own controls, where it has them.
 * @param {Array<object>} options.fineTune The round's Fine-tune fields.
 * @param {object} [options.draft] `{answered, hand, fine}`, as `keep` was last handed it.
 * @param {(tabs: Array<object>, draft: object) => object} [options.follow] What Fine-tune shows
 *   for the round as it stands, in each control not moved yet.
 * @param {(tabs: Array<object>, draft: object) => string} options.keep Takes the draft, with its
 *   Ramp tabs as `ramps`, and gives the line to show.
 * @returns {{tabs: () => Array<object>, join: (question: object) => boolean,
 *   say: (text: string) => void}} The questions shown; `join` adds a question, unless the round
 *   has it, with focus on its answer, and says whether it did; `say` shows a line.
 */
export function drawRound(parent, { id, questions, fineTune, draft = {}, follow, keep }) {
  const tabs = [];
  const cards = element("div");
  const fine = element("div", { class: "fine-tune" });
  drawFields(fine, fineTune, `${id}-fine`);
  const moved = Object.keys(draft.fine ?? {});
  const tune = element(
    "details",
    { open: moved.length > 0 },
    element("summary", {}, "Fine-tune: every control of this round"),
    fine,
  );
  const said = element("p", { class: "state", role: "status" });
  parent.replaceChildren(cards, tune, said);
  // The controls moved, of Fine-tune and of each question's own: only those are sent (ADR 0120).
  const touched = new Set(moved);
  const handTouched = {};
  writeFields(fine, draft.fine ?? {});

  function add(tab) {
    const answers = [...tab.answers, BY_HAND];
    // The draft's answer, or else "your call", the last answer before "Set it by hand".
    const kept = draft.answered?.[tab.id];
    const given = answers[kept] ? kept : answers.length - 2;
    const name = `${id}-${tab.id}`;
    const box = element("fieldset", { class: "answers", "data-tab": tab.id });
    box.append(element("legend", {}, capital(tab.question)));
    if (tab.plays) {
      box.append(element("p", {}, capital(tab.plays)));
    }
    if (tab.pattern) {
      box.append(element("pre", {}, tab.pattern.join("\n")));
    }
    for (const [index, { label, description }] of answers.entries()) {
      const radio = `${name}-${index}`;
      box.append(
        element(
          "div",
          { class: "choice" },
          element("input", {
            type: "radio",
            id: radio,
            name,
            value: index,
            checked: index === given,
            "aria-describedby": `${radio}-about`,
          }),
          element("label", { for: radio }, `${index + 1}. ${capital(label)}`),
          element("p", { id: `${radio}-about`, class: "hint" }, capital(description)),
        ),
      );
    }
    const hand = element("div", { class: "hand", "data-tab": tab.id });
    drawFields(hand, tab.hand ?? [], name);
    writeFields(hand, draft.hand?.[tab.id] ?? {});
    handTouched[tab.id] = new Set(Object.keys(draft.hand?.[tab.id] ?? {}));
    box.append(hand);
    cards.append(box);
    tabs.push(tab);
  }

  /** The draft as it stands: each question's answer, the controls moved in field order, so the
   * same values give the same draft, and the Ramp tabs shown. */
  function current() {
    const answered = {};
    const hand = {};
    for (const tab of tabs) {
      const box = cards.querySelector(`fieldset[data-tab="${tab.id}"]`);
      answered[tab.id] = Number(box.querySelector("input[type=radio]:checked").value);
      const names = (tab.hand ?? []).map((field) => field.name).filter((each) => handTouched[tab.id].has(each));
      if (names.length) {
        hand[tab.id] = touchedControls(readFields(box.querySelector(".hand")), names);
      }
    }
    const names = fineTune.map((field) => field.name).filter((each) => touched.has(each));
    const ramps = tabs.filter((tab) => tab.kind === "ramp");
    return { answered, hand, fine: touchedControls(readFields(fine), names), ramps };
  }

  function update() {
    const now = current();
    for (const tab of tabs) {
      const box = cards.querySelector(`fieldset[data-tab="${tab.id}"]`);
      box.querySelector(".hand").hidden = now.answered[tab.id] !== tab.answers.length;
    }
    if (follow) {
      writeFields(fine, follow(tabs, now), touched);
    }
    const line = keep(tabs, now);
    if (said.textContent !== line) {
      said.textContent = line;
    }
  }

  for (const question of questions) {
    add(question);
  }
  for (const type of ["input", "change"]) {
    cards.addEventListener(type, (event) => {
      const hand = event.target.closest(".hand");
      if (hand) {
        handTouched[hand.dataset.tab].add(event.target.name);
      }
      update();
    });
    fine.addEventListener(type, (event) => {
      touched.add(event.target.name);
      update();
    });
  }
  update();
  return {
    tabs: () => [...tabs],
    join: (question) => {
      const joins = !tabs.some((tab) => tab.id === question.id);
      if (joins) {
        add(question);
        update();
        cards.querySelector(`fieldset[data-tab="${question.id}"] input:checked`).focus();
      }
      return joins;
    },
    say: (text) => {
      said.textContent = text;
    },
  };
}
