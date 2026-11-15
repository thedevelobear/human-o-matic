// The rounds' questions (the website plan's section 6, ADR 0111): the Drummer step's round and
// each repeat group's, their tabs from the questions `get_sections` gives, each tab's answers the
// vocabulary's rows by their answer text, then "your call", and the controls a round's answers
// set. The rows' controls come from the worker's `presets` call, so no number of the vocabulary
// is written here. It touches no DOM, so `node --test` loads it; app.js draws the rounds.

import { count, fineTune, mostRamp, touchedControls } from "./forms.js";

export const YOUR_CALL = "your call";
/** The section kinds the Energy tab offers, in the vocabulary's order. */
export const SECTION_KINDS = [
  "breakdown, full power",
  "bridge, low energy, high groove",
  "big last chorus",
  "verse, holding back, building",
  "quiet intro",
  "verse, steady and solid",
  "pre-chorus, lifting into the chorus",
  "chorus, big and open",
  "halftime, heavy",
  "the drop, everything hits",
  "outro, winding down",
];
const BIGGER = "a bit harder";

// Each tab's label, the rows it offers, the controls "Set it by hand" opens, and for a group's
// tab, how `get_sections` words its question. The song-wide round's questions are the page's own.
export const TABS = {
  drummer: {
    label: "Drummer",
    question: "What kind of drummer plays this song?",
    rows: [
      "tight, modern metal",
      "somewhere in between",
      "loose, like a live drummer",
      "machine tight, nearly quantized",
    ],
    hand: ["style", "tightness"],
  },
  feel: {
    label: "Feel",
    question: "Where does the whole song sit against the beat?",
    rows: ["laid back", "way behind the beat, lazy", "pushing, on top of the beat"],
    hand: ["feel"],
  },
  energy: {
    label: "Energy",
    rows: SECTION_KINDS,
    hand: ["energy", "arc"],
    asks: /^What's the energy in /,
  },
  soft: {
    label: "Soft notes",
    rows: ["soft notes more present", "soft notes tucked away"],
    hand: ["ghost_level"],
    asks: /^Should its soft notes be more present/,
  },
  groove: {
    label: "Groove",
    rows: ["steady and even", "more groove, more light and shade"],
    hand: ["groove", "dynamic_range"],
    asks: /^Steady and even, or more groove/,
  },
  fill: {
    label: "Fill",
    rows: ["fill, big into the chorus", "small fill, just a turnaround"],
    hand: ["fill_intensity"],
    asks: /^How hard should the fill/,
  },
  last: {
    label: "Last repeat",
    rows: [BIGGER, "big last chorus"],
    hand: ["energy"],
    asks: / the same, or bigger, as the last time\?$/,
  },
  ramp: {
    label: "Ramp",
    rows: ["build into it over 2 bars", "a 4-bar ramp", "no ramp, straight in"],
    hand: ["ramp"],
    asks: /^Build up into /,
  },
};
// The tabs whose answers every section of the group takes; Last repeat's and Ramp's go to their
// own sections.
const GROUP_WIDE = ["energy", "soft", "groove", "fill"];
const WORDS = {
  dynamic_range: "dynamic range",
  fill_intensity: "fills",
  ghost_level: "soft notes",
};

/** The tab kind a question of `get_sections` asks, or null for one the page doesn't know. */
export function kindOf(question) {
  return Object.keys(TABS).find((kind) => TABS[kind].asks?.test(question)) ?? null;
}

/** Each row of the `presets` reply by its answer text: its controls at their starting points. */
export function rowsOf(presets) {
  return Object.fromEntries(
    [...presets.answers, ...presets.refinements].map(({ answer, controls }) => [answer, controls]),
  );
}

/** The rows a tab offers, the Energy tab's from the loudest to the quietest, ties in order. */
export function offered(kind, rows) {
  const names = TABS[kind].rows;
  return kind === "energy" ? [...names].sort((a, b) => rows[b].energy - rows[a].energy) : names;
}

/** The one section kind a section's name gives: the name, trimmed and in any case, equal to a
 * kind's answer up to its first comma, for exactly one kind. */
export function kindByName(name) {
  const wanted = name.trim().toLowerCase();
  const found = SECTION_KINDS.filter((kind) => kind.split(",")[0] === wanted);
  return found.length === 1 ? found[0] : null;
}

/** A row's controls in plain words, each name and value, a change with its sign. */
export function described(controls, change = false) {
  return Object.entries(controls)
    .map(([name, value]) => {
      const shown = change && value > 0 ? `+${value}` : String(value);
      return `${WORDS[name] ?? name} ${shown}`;
    })
    .join(", ");
}

function tab(kind, rows, { id, question, sections, resolved, most, about, plays, pattern }) {
  const names = offered(kind, rows).filter((name) => kind !== "ramp" || rows[name].ramp <= most);
  const call = {
    drummer: "nothing new: the drummer stays as it is",
    feel: "nothing new: the song's feel stays",
    last: "the same as the group",
    ramp: "no ramp: straight in",
  }[kind];
  const named = kind === "energy" && kindByName(about ?? "");
  return {
    id,
    kind,
    label: TABS[kind].label,
    question: question ?? TABS[kind].question,
    plays,
    pattern,
    sections,
    rows: names,
    answers: [
      ...names.map((name) => ({
        label: name,
        description:
          name === BIGGER
            ? `${described(rows[name], true)}, over the group's`
            : described(rows[name]),
      })),
      {
        label: YOUR_CALL,
        description: named
          ? `"${named}", as the section is named`
          : (call ?? "nothing new: the song's controls stay"),
      },
    ],
    hand: fineTune(TABS[kind].hand, resolved, most),
  };
}

/** The song-wide round's tabs, Drummer and Feel, their own controls from `resolved`. */
export function songTabs(presets, resolved) {
  const rows = rowsOf(presets);
  return ["drummer", "feel"].map((kind) => tab(kind, rows, { id: kind, resolved }));
}

/** A section's values as they render, but for the controls named in `left`, which the round
 * set before and may set no longer: its own over the song's over the style's defaults. */
export function resolvedOf(section, song, defaults, left = []) {
  const own = Object.fromEntries(
    Object.entries(section.controls).filter(([name]) => !left.includes(name)),
  );
  return { ...defaults, ...song, ...own };
}

/** The sections of `group`, in song order, from a `get_sections` reply. */
export function membersOf(reply, group) {
  return reply.sections.filter((section) => section.group === group);
}

/**
 * A group's round: a tab for each question its sections ask in `get_sections`, in song order,
 * but the ramp question, which joins a round once sent. A question the page doesn't know gets
 * a tab of "your call" alone.
 */
export function groupTabs(reply, group, presets, defaults) {
  const rows = rowsOf(presets);
  const members = membersOf(reply, group);
  const starts = members.map((section) => section.start);
  return members.flatMap((section) =>
    section.questions
      .map((question) => [question, kindOf(question)])
      .filter(([, kind]) => kind !== "ramp")
      .map(([question, kind]) => {
        const known = kind ?? "unknown";
        const shape = {
          id: `${known}-${section.start}`,
          question,
          plays: section.plays,
          pattern: section.pattern?.lines,
          sections: kind === "last" ? [section.start] : starts,
          resolved: resolvedOf(section, reply.controls, defaults),
          most: mostRamp(section.bars),
          about: section.name,
        };
        return kind ? tab(kind, rows, shape) : unknown(shape);
      }),
  );
}

function unknown({ id, question, plays, pattern, sections }) {
  const answers = [{ label: YOUR_CALL, description: "nothing new: the song's controls stay" }];
  const shown = { id, kind: null, label: "Question", question, plays, pattern, sections };
  return { ...shown, rows: [], answers, hand: [] };
}

/**
 * The Ramp tabs a round sent can take, one for each group whose sections `get_sections` now
 * asks the ramp question of, for the sections whose own group and the louder one after them
 * have both been asked about (ADR 0108): `asked` holds the groups whose rounds were sent.
 */
export function rampTabs(reply, asked, presets, defaults) {
  const rows = rowsOf(presets);
  const { sections } = reply;
  const ready = sections.filter((section, index) => {
    const after = sections[index + 1];
    const ramps = section.questions.some((question) => kindOf(question) === "ramp");
    // The engine never asks it of the last section, which has none after it to build into.
    return ramps && after !== undefined && asked.has(section.group) && asked.has(after.group);
  });
  const groups = [...new Set(ready.map((section) => section.group))];
  return groups.map((group) => {
    const leading = ready.filter((section) => section.group === group);
    const [first] = leading;
    const labels = leading.map((section) => section.label).join(", ");
    return tab("ramp", rows, {
      // By its first section, so a later Ramp tab of the group is a question of its own.
      id: `ramp-${first.start}`,
      question: first.questions.find((question) => kindOf(question) === "ramp"),
      plays: `Set on ${count(leading.length, "section")} of ${group}: ${labels}`,
      sections: leading.map((section) => section.start),
      resolved: resolvedOf(first, reply.controls, defaults),
      most: Math.max(...leading.map((section) => mostRamp(section.bars))),
    });
  });
}

const rounded = (number) => Math.round(number * 1e6) / 1e6;

/** A row's controls over the song's own (the vocabulary's "How to read a row"): where the song
 * has a value of its own, a number moves it by the row's difference from the style's default,
 * and is left unset where the row gives the default. */
export function overSong(controls, song, defaults) {
  const moved = {};
  for (const [name, value] of Object.entries(controls)) {
    if (typeof value !== "number" || typeof song[name] !== "number") {
      moved[name] = value;
    } else if (value !== defaults[name]) {
      moved[name] = rounded(song[name] + value - defaults[name]);
    }
  }
  return moved;
}

/** What a question's answer sets: a row's controls, "Set it by hand"'s controls moved, or for
 * "your call", or no answer, nothing new: on the Energy tab the kind its section's name gives,
 * and on the Ramp tab no ramp. */
function given(tab, round, rows) {
  const index = round.answered[tab.id];
  if (index !== undefined && index < tab.rows.length) {
    return rows[tab.rows[index]];
  }
  if (index !== undefined && index > tab.rows.length) {
    return touchedControls(round.hand[tab.id] ?? {}, round.handTouched[tab.id] ?? new Set());
  }
  if (tab.kind === "ramp") {
    return { ramp: 0 };
  }
  const named = tab.kind === "energy" && kindByName(round.about ?? "");
  return named ? rows[named] : {};
}

/**
 * What a group's round sends, by section: every section of the group takes the group-wide tabs'
 * answers, over the song's controls, and Fine-tune's moved controls over them; the last repeat
 * its own answer over those, "a bit harder" added to the group's energy; and each Ramp tab's
 * sections its ramp. A control the round's answers set at its last send, in `before`, and no
 * longer set is null, so the round as it stands replaces what it set.
 *
 * @param {Array<object>} tabs The round's question tabs.
 * @param {object} round `{answered, hand, handTouched, fine}`: the answers by tab, "Set it by
 *   hand"'s values and the names moved by tab, and Fine-tune's moved controls.
 * @param {object} context `{presets, song, defaults, members, before}`: the song's own controls,
 *   the style's defaults, the group's sections, and `{start: names}` the answers set last.
 * @returns {{controls: object, set: object}} Each section's controls, and the names its
 *   answers set, to keep as `before`.
 */
export function groupControls(tabs, round, { presets, song, defaults, members, before = {} }) {
  const rows = rowsOf(presets);
  const [first] = members;
  const about = { ...round, about: first?.name };
  const wide = Object.assign(
    {},
    ...tabs
      .filter((found) => GROUP_WIDE.includes(found.kind))
      .map((found) => overSong(given(found, about, rows), song, defaults)),
  );
  const group = { ...wide, ...round.fine };
  const controls = {};
  const set = {};
  for (const section of members) {
    controls[section.start] = { ...group };
    set[section.start] = Object.keys(wide);
  }
  for (const found of tabs.filter((each) => each.kind === "last")) {
    const [start] = found.sections;
    const index = round.answered[found.id];
    const asked = found.rows[index];
    let own = given(found, round, rows);
    if (asked === BIGGER) {
      const base = resolvedOf(first, song, defaults, before[first.start]);
      own = { energy: rounded((group.energy ?? base.energy) + own.energy) };
    } else if (asked !== undefined) {
      own = overSong(own, song, defaults);
    }
    Object.assign(controls[start], own);
    set[start] = [...new Set([...set[start], ...Object.keys(own)])];
  }
  for (const found of tabs.filter((each) => each.kind === "ramp")) {
    for (const start of found.sections) {
      controls[start] = { ...controls[start], ...given(found, round, rows) };
    }
  }
  for (const [start, names] of Object.entries(before)) {
    for (const name of names) {
      if (controls[start] && !(name in controls[start])) {
        controls[start][name] = null;
      }
    }
  }
  return { controls, set };
}

/** The song-wide round's controls: Drummer's and Feel's answers, and Fine-tune's moved controls
 * over them, with a control the answers set at the last send, in `before`, null where they no
 * longer set it. Returns them with the names the answers set. */
export function songControls(tabs, round, { presets, before = [] }) {
  const rows = rowsOf(presets);
  const answers = Object.assign({}, ...tabs.map((found) => given(found, round, rows)));
  const controls = { ...answers, ...round.fine };
  for (const name of before) {
    if (!(name in controls)) {
      controls[name] = null;
    }
  }
  return { controls, set: Object.keys(answers).filter((name) => name !== "style") };
}

/** What the rounds' answers set, by round and section, kept after a section edit only for the
 * sections the edit leaves as they were, `before` against `after`: the same first bar, bars and
 * group. A split, merge, move or new group forgets the rest, so taking back what a round set
 * never reaches a section that now means something else (ADR 0122). The song's stays. */
export function keptAfterEdit(sent, before, after) {
  const shape = ({ start, bars, group }) => `${start} ${bars} ${group}`;
  const same = new Set(after.map(shape));
  const unchanged = before.filter((section) => same.has(shape(section)));
  const kept = new Set(unchanged.map(({ start }) => String(start)));
  return Object.fromEntries(
    Object.entries(sent).map(([key, set]) => [
      key,
      key === "song" ? set : Object.fromEntries(Object.entries(set).filter(([start]) => kept.has(start))),
    ]),
  );
}

/** The calls that send a group's round: set_section_controls once for each set of controls,
 * with the sections that take it, in song order. */
export function groupCalls(controls) {
  const calls = new Map();
  for (const [start, given] of Object.entries(controls)) {
    const key = JSON.stringify(given);
    calls.set(key, [...(calls.get(key) ?? []), Number(start)]);
  }
  return [...calls].map(([key, section_ids]) => ({
    call: "set_section_controls",
    args: { controls: JSON.parse(key), section_ids },
  }));
}

/** The calls that send the song-wide round: set_style with its style and a tightness given, then
 * set_section_controls for the song, with its feel and any control taken back, whose reply
 * gives what each section plays. */
export function songCalls({ style, tightness, ...rest }, current) {
  const styled = { style: style ?? current, ...(typeof tightness === "number" && { tightness }) };
  const back = tightness === null ? { tightness } : {};
  return [
    { call: "set_style", args: styled },
    { call: "set_section_controls", args: { controls: { ...rest, ...back } } },
  ];
}

/** What a round's answers show on Fine-tune: the controls the group-wide answers set over the
 * first section's values without the ones the round set before. */
export function shownGroup(tabs, round, context) {
  const { song, defaults, members, before = {} } = context;
  const [first] = members;
  const { controls } = groupControls(
    tabs.filter((found) => GROUP_WIDE.includes(found.kind)),
    round,
    { ...context, members: [first], before: {} },
  );
  return { ...resolvedOf(first, song, defaults, before[first.start]), ...controls[first.start] };
}

/** What the song-wide answers show on Fine-tune, over the song's values without the ones they
 * set before. */
export function shownSong(tabs, round, { presets, song, defaults, style, before = [] }) {
  const base = resolvedOf({ controls: song }, {}, defaults, before);
  return { ...base, style, ...songControls(tabs, round, { presets }).controls };
}

const capital = (text) => text[0].toUpperCase() + text.slice(1);

/** The words of a round's echo: each section's `expected` from the replies, or only those of the
 * sections `only` names, any control the engine clamped and the value it used, and the count of
 * questions so far. */
export function echo(replies, asked, only = null) {
  const sections = replies.flatMap((reply) => reply.sections ?? []);
  const labels = Object.fromEntries(sections.map(({ start, label }) => [start, label]));
  const lines = sections
    .filter(({ start, expected }) => expected && (only === null || only.includes(start)))
    .map(({ label, expected }) => `${capital(label)}: ${expected}.`);
  const clamped = replies
    .flatMap((reply) => reply.clamped ?? [])
    .map(({ control, given: was, used, section }) => {
      const where = section === undefined ? "" : ` in ${labels[section]}`;
      return `${capital(WORDS[control] ?? control)} ${was} was taken as ${used}${where}.`;
    });
  return [...lines, ...clamped, `Questions so far: ${asked}.`].join(" ");
}
