// The vocabulary's two tables read on their own, in the form of the worker's `presets` reply:
// each answer and its controls at their starting points. The Node tests use it as the page's
// presets, and the engine test holds the worker's `presets` call to it, so the two readers of
// `vocabulary.md` agree.

import { readFile } from "node:fs/promises";

const COLUMNS = ["energy", "groove", "dynamic_range", "tightness", "feel", "ghost_level"];
const path = new URL("../../skills/human-o-matic/references/vocabulary.md", import.meta.url);

function value(text) {
  const point = text.split(" [")[0];
  return { true: true, false: false }[point] ?? (Number.isNaN(Number(point)) ? point : Number(point));
}

function rows(lines, heading) {
  const after = lines.slice(lines.indexOf(heading) + 1);
  const end = after.findIndex((line) => line.startsWith("## "));
  const table = after.slice(0, end === -1 ? undefined : end).filter((line) => line.startsWith('| "'));
  return table.map((line) => {
    const [answer, ...cells] = line.split("|").slice(1, -1).map((cell) => cell.trim());
    const also = cells.pop();
    const controls = {};
    cells.forEach((cell, index) => cell && (controls[COLUMNS[index]] = value(cell)));
    for (const entry of also ? also.split("; ") : []) {
      const [name, text] = entry.split(": ");
      controls[name] = value(text);
    }
    return { answer: answer.slice(1, -1), controls };
  });
}

/** The vocabulary's rows as the `presets` call gives them. */
export async function vocabulary() {
  const lines = (await readFile(path, "utf8")).split("\n");
  return { answers: rows(lines, "## Answers"), refinements: rows(lines, "## Refinements") };
}
