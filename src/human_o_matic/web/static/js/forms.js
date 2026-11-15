// The page's forms as data, and the worker call their values make. It touches no DOM, so
// `node --test` loads it; fields.js draws the fields and reads their values back as text, or
// true and false for a checkbox, by name.
//
// A field is `{type, name, label, ...}`: "number", "text", "select", "radio" and "segments", a
// row of option buttons, with `options` of `{value, label}`, "checkbox", "range", "button", a
// "list" of `items` to show, or a "group"
// of `fields` under a `legend`. Each may have a `hint`, shown under it and tied to it.

/** How many of `noun`, as "1 note" or "12 notes". */
export function count(number, noun) {
  return `${number} ${noun}${number === 1 ? "" : "s"}`;
}

/** `text` with a capital first letter, as the page shows every sentence and option, while the
 * vocabulary and every value keep their own case. */
export function capital(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Each decision request kind's form (the website plan's section 6), from the request's
// `message`, `options` and `details`: its fields, and the answer their values give, under the
// argument `answer_with` names. `open` is open_session's, asked again; the rest are set_hit_types'.
export const REQUESTS = {
  tempo: {
    fields: () => [
      { type: "number", name: "bpm", label: "The song's tempo, in BPM", required: true, step: "any" },
    ],
    answer: (request, values) => ({ open: { bpm: Number(values.bpm) } }),
  },
  drum_track: {
    fields: (request) => [
      {
        type: "radio",
        name: "track",
        label: "The track that holds the drums",
        required: true,
        options: request.options.map(({ value, label }) => ({ value: String(value), label })),
      },
    ],
    answer: (request, values) => ({ open: { track: Number(values.track) } }),
  },
  hit_types: {
    fields: (request) =>
      request.details.families.map(({ family, counts, velocities }) => ({
        type: "group",
        legend: family,
        hint: Object.entries(counts)
          .map(([type, found]) => `${found} ${type}, velocity ${span(velocities[type])}`)
          .join("; "),
        fields: [
          {
            type: "number",
            name: `hit_types.${family}.soft_below`,
            label: "Soft below velocity",
            min: 1,
            max: 128,
            value: velocities.soft ? String(velocities.soft[1] + 1) : "",
          },
          {
            type: "number",
            name: `hit_types.${family}.accent_from`,
            label: "Accent from velocity",
            min: 1,
            max: 128,
            value: velocities.accent ? String(velocities.accent[0]) : "",
          },
          { type: "checkbox", name: `hit_types.${family}.normal`, label: "All normal" },
        ],
      })),
    answer: (request, values) => ({
      hit_types: Object.fromEntries(
        request.details.families.map(({ family }) => {
          const given = (bound) => values[`hit_types.${family}.${bound}`];
          if (given("normal") === true) {
            return [family, {}];
          }
          const bounds = ["soft_below", "accent_from"].filter((bound) => given(bound));
          return [family, Object.fromEntries(bounds.map((bound) => [bound, Number(given(bound))]))];
        }),
      ),
    }),
  },
  ambiguous_bars: {
    fields: (request) =>
      request.details.bars.map(({ bar, beats }) => ({
        type: "group",
        legend: `Bar ${bar + 1}`,
        fields: beats.map(({ beat, grid, alternatives, largest_offset_ms }) => ({
          type: "select",
          name: `grids.${bar},${beat}`,
          label: `Beat ${beat + 1}`,
          options: [grid, ...alternatives].map((value) => ({ value, label: spoken(value) })),
          value: grid,
          hint: alternatives.length ? "" : `a note ${Math.round(largest_offset_ms)} ms off its grid`,
        })),
      })),
    answer: (request, values) => ({
      grids: Object.fromEntries(
        request.details.bars.flatMap(({ bar, beats }) =>
          beats.map(({ beat }) => [`${bar},${beat}`, values[`grids.${bar},${beat}`]]),
        ),
      ),
    }),
  },
  unmapped_notes: {
    fields: (request, { articulations = [] } = {}) => [
      ...request.details.notes.map((notes) => ({
        type: "select",
        name: `unmapped.${notes.pitch}`,
        label: `Note ${notes.pitch}`,
        hint: `${count(notes.count, "note")} from bar ${notes.positions[0][0] + 1}`,
        required: true,
        options: [
          { value: "", label: "Choose what it plays" },
          ...articulations.map((name) => ({ value: name, label: name })),
          { value: "drop", label: "Leave them out" },
        ],
      })),
      { type: "button", name: "kits", label: "Read the file with another kit" },
    ],
    answer: (request, values) => ({
      unmapped: Object.fromEntries(
        request.details.notes.map(({ pitch }) => [String(pitch), values[`unmapped.${pitch}`]]),
      ),
    }),
  },
  conversion: {
    fields: (request) => [
      {
        type: "radio",
        name: `substitutions.${request.details.source}`,
        label: `${count(request.details.count, "note")} of ${request.details.source}`,
        required: true,
        value: String(request.options[0]?.value ?? ""),
        options: request.options.map(({ value, label }) => ({ value: String(value), label })),
      },
    ],
    answer: (request, values) => ({
      substitutions: { [request.details.source]: values[`substitutions.${request.details.source}`] },
    }),
  },
};

/** A request's form: its kind's fields, or for a kind the page doesn't know, its options to
 * read, since nothing can answer it. `extra` is what the form needs from another call: the
 * source kit's `articulations` for unmapped notes. */
export function form(request, extra = {}) {
  const known = REQUESTS[request.kind];
  if (known) {
    return known.fields(request, extra);
  }
  const items = request.options.map(({ label }) => label);
  return items.length ? [{ type: "list", label: "Its options", items }] : [];
}

/** The one call that answers the check batch's requests from its forms' values: open_session
 * again for a tempo or a drum track, which come alone, or else set_hit_types with every answer. */
export function batch(requests, values) {
  const answers = requests
    .filter((request) => request.kind in REQUESTS)
    .map((request) => REQUESTS[request.kind].answer(request, values));
  const open = Object.assign({}, ...answers.map((answer) => answer.open ?? {}));
  if (Object.keys(open).length) {
    return { call: "open_session", args: open };
  }
  const args = {};
  for (const answer of answers) {
    for (const [argument, given] of Object.entries(answer)) {
      args[argument] = { ...args[argument], ...given };
    }
  }
  return { call: "set_hit_types", args };
}

function span([low, high]) {
  return low === high ? String(low) : `${low} to ${high}`;
}

function spoken(grid) {
  return grid.replace("_", " ");
}

// Fine-tune: the controls as sliders, selects and checkboxes, with their ranges from the
// controls' models, and set_style's style. A ramp's most bars depend on the section.
const UNIT = { kind: "range", min: 0, max: 1, step: 0.01 };
export const ADD_NOTES =
  "Add notes: lets this section add ghost notes, cymbals where it has few, a fill into the next " +
  "section, flams, rimshots and chokes, only on drums it already plays. Your own notes stay.";
export const FINE_TUNE = {
  style: { kind: "select", label: "Drummer", options: ["tight", "medium", "loose"] },
  energy: { ...UNIT, label: "Energy" },
  groove: { ...UNIT, label: "Groove" },
  dynamic_range: { ...UNIT, label: "Dynamic range" },
  tightness: { ...UNIT, label: "Tightness" },
  feel: { ...UNIT, label: "Feel, from pushed to laid back", min: -1 },
  arc: { kind: "select", label: "Arc", options: ["steady", "build", "drop"] },
  fill_intensity: { ...UNIT, label: "Fills" },
  ghost_level: { ...UNIT, label: "Soft notes" },
  ramp: { ...UNIT, label: "Ramp, in bars", step: 1 },
  skip: { kind: "switch", label: "Leave this section as it is" },
  creative: { kind: "switch", label: ADD_NOTES },
};
export const SONG_CONTROLS = ["style", "tightness", "feel"];
export const GROUP_CONTROLS = [
  "energy",
  "groove",
  "dynamic_range",
  "tightness",
  "feel",
  "arc",
  "fill_intensity",
  "ghost_level",
  "ramp",
  "skip",
  "creative",
];
export const MAX_RAMP = 8;

/** The most bars a ramp climbs over in a section of `bars`: at most half of them. */
export function mostRamp(bars) {
  return Math.min(MAX_RAMP, Math.floor(bars / 2));
}

/** The fields of the controls `names`, each starting at its value in `resolved`, the ramp's
 * slider reaching `ramp` bars. */
export function fineTune(names, resolved, ramp = MAX_RAMP) {
  return names.map((name) => {
    const { kind, label, options, min, max, step } = FINE_TUNE[name];
    if (kind === "select") {
      const choices = options.map((value) => ({ value, label: value }));
      return { type: "segments", name, label, options: choices, value: resolved[name] };
    }
    if (kind === "switch") {
      return { type: "checkbox", name, label, checked: resolved[name] === true };
    }
    const most = name === "ramp" ? ramp : max;
    const value = String(Math.min(resolved[name], most));
    return { type: "range", name, label, min, max: most, step, value };
  });
}

/** What the controls `touched` were set to, from Fine-tune's values: each number as a number. */
export function touchedControls(values, touched) {
  return Object.fromEntries(
    [...touched].map((name) => [
      name,
      FINE_TUNE[name].kind === "range" ? Number(values[name]) : values[name],
    ]),
  );
}

const LEVELS = ["very low", "low", "medium", "high", "very high"];

/** A control's number as the page shows it: with two decimals, "0.50" or "-1.00", but a ramp's
 * bars, a whole number, as they are. */
export function fixed(name, value) {
  return name === "ramp" ? String(value) : Number(value).toFixed(2);
}

/** A slider's value in words, for its `aria-valuetext`, such as "0.80, very high". */
export function words(name, value) {
  const number = Number(value);
  if (name === "ramp") {
    return number ? count(number, "bar") : "no ramp";
  }
  const shown = fixed(name, number);
  if (name === "feel") {
    return `${shown}, ${number < 0 ? "pushed" : number > 0 ? "laid back" : "on the beat"}`;
  }
  return `${shown}, ${LEVELS[Math.min(Math.floor(number * LEVELS.length), LEVELS.length - 1)]}`;
}

/** The section edit `op` on `section`, with bars as the page shows them, from 1, given as the
 * ops take them, from 0 (ADR 0081). */
export function sectionEdit(op, section, values) {
  const bar = (text) => Number(text) - 1;
  if (op === "split") {
    return { op, at: bar(values.at) };
  }
  if (op === "move") {
    return { op, start: section.start, to: bar(values.to) };
  }
  if (op === "rename") {
    const group = values.group.trim();
    return { op, start: section.start, name: values.name.trim(), ...(group && { group }) };
  }
  return { op, start: section.start };
}

/** The bars, from 1, a split of section `index` can start at, and that its start can move to:
 * inside it, and for a move, after the start of the section before it. */
export function editBars(sections, index) {
  const { start, bars } = sections[index];
  const before = sections[index - 1];
  return {
    split: [start + 2, start + bars],
    move: before ? [before.start + 2, start + bars] : null,
  };
}

const GM = "gm";

/** The kits of `list_maps` as choices, General MIDI first, as "General MIDI, or I don't know"
 * for where a file came from, a library's kit named when it has several, and a kit whose names
 * are mostly inferred saying so. */
export function kitOptions({ libraries }, source) {
  const ordered = [...libraries].sort((a, b) => (b.id === GM) - (a.id === GM));
  return ordered.flatMap((library) =>
    library.kits.map((kit) => {
      const name = library.id === GM && source ? "General MIDI, or I don't know" : library.name;
      const which = library.kits.length > 1 ? `, ${kit.name}` : "";
      const unchecked = 2 * kit.low_confidence > kit.articulations ? " (mapping not yet checked)" : "";
      return { value: kit.map, label: `${name}${which}${unchecked}` };
    }),
  );
}
