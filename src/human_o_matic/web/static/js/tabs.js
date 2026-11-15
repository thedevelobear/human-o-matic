// A round of questions in tabs, as Claude Code asks them (ADR 0111): its state, the keyboard as a
// pure function from a key and the state to the next state, and each tab's ARIA attributes as a
// pure function of the state. It touches no DOM, so `node --test` loads it; round.js draws it.
//
// A round's tabs are its questions, then Submit. A question's answers end with "Set it by hand",
// which opens that question's own controls. Each question keeps a choice, where its pointer is,
// and an answer once one is given: a click or Enter answers, and the arrow and number keys only
// move the choice. `focus` says where the page moves focus after a change: "tab", the current
// tab; "answer", its chosen answer; "hand", the first of its own controls; "submit", the Submit
// tab's first control; or null, to leave focus where it is.

export const SUBMIT = "submit";
export const BY_HAND = {
  label: "Set it by hand",
  description: "this question's controls, from where the section is now",
};

/**
 * A round's first state, on its first tab.
 *
 * @param {string} name The round's name, which labels its strip of tabs.
 * @param {Array<{id: string, label: string, answers: Array<{label: string, description: string}>,
 *   given?: number}>} questions Each question's tab, with its answers but "Set it by hand", and
 *   the answer given before, if any, where its pointer starts.
 */
export function round(name, questions) {
  const tabs = questions.map((question) => ({
    ...question,
    answers: [...question.answers, BY_HAND],
  }));
  const given = questions.filter((question) => question.given !== undefined);
  return {
    name,
    tabs: [...tabs, { id: SUBMIT, label: "Submit", answers: [] }],
    current: 0,
    choice: Object.fromEntries(tabs.map((tab) => [tab.id, tab.given ?? 0])),
    answered: Object.fromEntries(given.map((question) => [question.id, question.given])),
    focus: null,
  };
}

/** Whether answer `index` of `tab` is "Set it by hand". */
export function byHand(tab, index) {
  return tab.id !== SUBMIT && index === tab.answers.length - 1;
}

/**
 * The state after `key` is pressed where focus is: on a tab of the strip ("tab"), on an answer
 * ("answer"), in a control of "Set it by hand" ("hand"), or in the Submit tab ("submit"). A key
 * the round doesn't use gives the same state, so the page leaves the key to the platform.
 */
export function key(state, key, where) {
  const count = state.tabs.length;
  const tab = state.tabs[state.current];
  if (where === "tab") {
    const left = state.current - 1 + count;
    const to = { ArrowLeft: left, ArrowRight: state.current + 1, Home: 0, End: count - 1 };
    return key in to ? { ...state, current: to[key] % count, focus: "tab" } : state;
  }
  if (where === "answer") {
    if (/^[1-9]$/.test(key) && Number(key) <= tab.answers.length) {
      return { ...state, choice: { ...state.choice, [tab.id]: Number(key) - 1 }, focus: "answer" };
    }
    if (key === "Enter") {
      const index = state.choice[tab.id];
      const given = answer(state, index);
      return byHand(tab, index) ? { ...given, focus: "hand" } : onward(given);
    }
  }
  if (where === "hand" && key === "Enter") {
    return onward(state);
  }
  return state;
}

/** The current question answered with answer `index`, as a click gives it: focus stays. */
export function answer(state, index) {
  const { id } = state.tabs[state.current];
  return {
    ...state,
    choice: { ...state.choice, [id]: index },
    answered: { ...state.answered, [id]: index },
    focus: null,
  };
}

/** The current question's choice moved to answer `index` by the platform's own radio keys. */
export function choose(state, index) {
  const { id } = state.tabs[state.current];
  return { ...state, choice: { ...state.choice, [id]: index }, focus: null };
}

/** The current question answered "Set it by hand", as changing one of its controls does. */
export function setByHand(state) {
  return answer(state, state.tabs[state.current].answers.length - 1);
}

/** Tab `index` shown, as a click on it gives it: focus stays. */
export function select(state, index) {
  return { ...state, current: index, focus: null };
}

/** The tab `by` places on, wrapping at the ends, as the strip's arrow buttons move: focus stays
 * on the button. */
export function step(state, by) {
  const count = state.tabs.length;
  return select(state, (state.current + by + count) % count);
}

/** A question that joins the round before Submit, as a Ramp tab does: the current tab stays
 * current and focus stays where it is. */
export function join(state, question) {
  const current = state.tabs[state.current].id;
  const joined = { ...question, answers: [...question.answers, BY_HAND] };
  const tabs = [...state.tabs.slice(0, -1), joined, state.tabs.at(-1)];
  return {
    ...state,
    tabs,
    current: tabs.findIndex((tab) => tab.id === current),
    choice: { ...state.choice, [question.id]: question.given ?? 0 },
    focus: null,
  };
}

/** The next tab, after an answer by Enter: the next question with focus on its choice, or after
 * the last question Submit with focus on its first control. */
function onward(state) {
  const current = Math.min(state.current + 1, state.tabs.length - 1);
  return { ...state, current, focus: state.tabs[current].id === SUBMIT ? "submit" : "answer" };
}

/**
 * The ARIA attributes of the strip, each tab and each panel, as the WAI-ARIA Authoring
 * Practices' tabs pattern sets them, with ids under `prefix`. A question answered says so in
 * its tab's name.
 */
export function aria(state, prefix) {
  return {
    tablist: { role: "tablist", "aria-label": state.name },
    tabs: state.tabs.map((tab, index) => {
      const selected = index === state.current;
      const answered = tab.id in state.answered;
      return {
        id: tab.id,
        answered,
        tab: {
          id: `${prefix}-tab-${tab.id}`,
          role: "tab",
          "aria-selected": String(selected),
          tabindex: selected ? "0" : "-1",
          "aria-controls": `${prefix}-panel-${tab.id}`,
          "aria-label": answered ? `${tab.label}, answered` : tab.label,
        },
        panel: {
          id: `${prefix}-panel-${tab.id}`,
          role: "tabpanel",
          "aria-labelledby": `${prefix}-tab-${tab.id}`,
          hidden: !selected,
        },
      };
    }),
  };
}
