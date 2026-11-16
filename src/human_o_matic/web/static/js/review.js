// What the Review and Download steps say, what a remap says to listen for, and the download's
// name (the website plan's section 6). It touches no DOM, so `node --test` loads it.

import { count } from "./forms.js";

const MOST = 80;
const WHY = {
  missing: "the kit to play it has no sound for them",
  unplayed: "the section doesn't play that drum",
  played: "a note is there already",
  crowded: "another section's notes leave no room",
};

/**
 * The download's name, `<name>-<made>-<n>.mid`, `humanized` for a re-performance and `remapped`
 * for a remap: the chosen file's name without its extension and anything but letters, digits,
 * spaces, `-`, `_` and parentheses, cut to 80 characters, so the original stays recognisable and
 * is never overwritten. `n` counts this visit's downloads from 1.
 */
export function downloadName(name, n, made = "humanized") {
  const kept = name.replace(/\.midi?$/i, "").replace(/[^\p{L}\p{N} \-_()]/gu, "");
  return `${Array.from(kept).slice(0, MOST).join("") || "song"}-${made}-${n}.mid`;
}

/** A run of bars counted from 1, as a DAW shows them: "bar 9" or "bars 9 to 24". */
export function barsLabel(start, bars) {
  return bars === 1 ? `bar ${start + 1}` : `bars ${start + 1} to ${start + bars}`;
}

/** What `render`'s `conversion` reports, a line each, to listen for: the articulations written as
 * others or left out, the drums that land on one pitch, and the names read or written that
 * aren't checked yet. */
export function conversionLines({ changed, collisions, low_confidence }) {
  return [
    ...changed.map(({ source, target, notes }) =>
      target === "drop"
        ? `${count(notes, "note")} of ${source} left out`
        : `${count(notes, "note")} of ${source} written as ${target}`,
    ),
    ...collisions.map(
      ({ pitch, notes, sources, positions }) =>
        `${count(notes, "note")} of ${sources.join(" and ")} land together on note ${pitch}, ` +
        `first in bar ${positions[0][0] + 1}`,
    ),
    ...Object.entries(low_confidence.read).map(
      ([name, notes]) => `${count(notes, "note")} read as ${name}, a name not checked yet`,
    ),
    ...Object.entries(low_confidence.written).map(
      ([name, notes]) => `${count(notes, "note")} written as ${name}, a name not checked yet`,
    ),
  ];
}

/** What a remap's summary says to listen for, a line each: what its conversion reports, and the
 * notes that keep a velocity outside the range their sound takes in the kit (ADR 0130). */
export function remapLines({ conversion, outside_range }) {
  return [
    ...conversionLines(conversion),
    ...Object.entries(outside_range).map(
      ([name, notes]) => `${count(notes, "note")} of ${name} keep a velocity outside its range in the kit`,
    ),
  ];
}

/** What the creative sections added and couldn't, a line each, or none when none is creative. */
export function creativeLines(report) {
  if (!report) {
    return [];
  }
  const listed = (found) => Object.entries(found).map(([kind, n]) => `${n} ${kind}`);
  const added = listed(report.added);
  return [
    `Added: ${added.length ? added.join(", ") : "nothing"}`,
    ...Object.entries(report.skipped).map(
      ([why, kinds]) => `Not added, as ${WHY[why] ?? why}: ${listed(kinds).join(", ")}`,
    ),
  ];
}
