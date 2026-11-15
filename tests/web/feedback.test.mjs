// The feedback form's pure module (the website plan's PR 6): the request posts exactly section 6's
// six fields, URL-encoded, with the comment and the contact held to their limits and the honeypot
// as found, and the settings hold exactly their allowed keys, controls only by `ControlVector`'s
// names, and nothing of the file, its name, a note or a section's words. The settings of a song
// opened in the engine are in engine.test.mjs.

import assert from "node:assert/strict";
import { test } from "node:test";

import { FIELDS, LIMITS, feedbackRequest, settingsOf } from "../../src/human_o_matic/web/static/js/feedback.js";

const SETTINGS_KEYS = [
  "from_map",
  "to_map",
  "style",
  "seed",
  "bars",
  "sections",
  "song_controls",
  "section_controls",
  "takes",
];
const KITS = { from_map: "gm/default", to_map: "gm/default" };
// A `get_sections` reply, cut to what the settings could read, with what they must leave out: the
// session, the sections' words, their patterns and a control the engine doesn't have.
const READ = {
  session_id: "123456789012",
  bars: 12,
  source: "markers",
  style: "medium",
  seed: 8,
  controls: { tightness: 0.7, feel: 0.2 },
  note: "the user's words on the song",
  sections: [
    {
      start: 0,
      bars: 8,
      group: "A",
      label: "bars 1 to 8",
      name: "My verse",
      plays: "kick, snare, hi-hat",
      pattern: { lines: ["hh  x.x.x.x."] },
      questions: ["What's the energy in bars 1 to 8?"],
      controls: { energy: 0.8, arc: "build", creative: true, unknown: 1 },
      note: "the user's words on a section",
      take: 0,
    },
    {
      start: 8,
      bars: 4,
      group: "B",
      label: "bars 9 to 12",
      name: "",
      plays: "kick, snare, ride",
      controls: { skip: true, ramp: 2 },
      note: null,
      take: 3,
    },
  ],
  decisions: [],
};

test("the settings hold exactly their allowed keys, with each section's take, in song order", () => {
  const settings = settingsOf(KITS, READ);

  assert.deepEqual(Object.keys(settings), SETTINGS_KEYS);
  assert.deepEqual(settings, {
    ...KITS,
    style: "medium",
    seed: 8,
    bars: 12,
    sections: 2,
    song_controls: { tightness: 0.7, feel: 0.2 },
    section_controls: [{ energy: 0.8, arc: "build", creative: true }, { skip: true, ramp: 2 }],
    takes: [0, 3],
  });
  const text = JSON.stringify(settings);
  for (const left of ["123456789012", "My verse", "user's words", "kick", "hh", "bars 1 to 8", "unknown"]) {
    assert.ok(!text.includes(left), left);
  }
});

/** A request's body, read back into its fields in order. */
function fields(request) {
  return [...new URLSearchParams(request.body)];
}

test("the form posts exactly section 6's six fields, URL-encoded, with the settings as JSON", () => {
  const settings = settingsOf(KITS, READ);
  const request = feedbackRequest(
    { rating: "4", comment: "Snappy & loose = good", contact: "me@example.org", "bot-field": "" },
    settings,
  );

  assert.deepEqual(FIELDS, ["form-name", "bot-field", "rating", "comment", "contact", "settings"]);
  assert.equal(request.method, "POST");
  assert.deepEqual(request.headers, { "Content-Type": "application/x-www-form-urlencoded" });
  assert.equal(typeof request.body, "string");
  assert.match(request.body, /^form-name=feedback&bot-field=&rating=4&comment=Snappy\+%26\+loose\+%3D\+good&/);
  assert.deepEqual(
    fields(request).map(([name]) => name),
    FIELDS,
  );
  assert.deepEqual(JSON.parse(new URLSearchParams(request.body).get("settings")), settings);
});

test("only the form's own fields are sent, whatever else the form holds", () => {
  const request = feedbackRequest(
    { rating: "5", comment: "", contact: "", "bot-field": "", "form-name": "other", settings: "{}", file: "x.mid" },
    { seed: 1 },
  );

  assert.deepEqual(Object.fromEntries(fields(request)), {
    "form-name": "feedback",
    "bot-field": "",
    rating: "5",
    comment: "",
    contact: "",
    settings: '{"seed":1}',
  });
});

test("a comment and a contact are held to 2,000 and 200 characters", () => {
  const request = feedbackRequest(
    { rating: "3", comment: "a".repeat(2500), contact: "b".repeat(300), "bot-field": "" },
    {},
  );
  const sent = Object.fromEntries(fields(request));

  assert.deepEqual(LIMITS, { comment: 2000, contact: 200 });
  assert.equal(sent.comment, "a".repeat(2000));
  assert.equal(sent.contact, "b".repeat(200));
});

test("the honeypot is sent empty for a person, and as a bot filled it, for Netlify to catch", () => {
  const person = Object.fromEntries(fields(feedbackRequest({ rating: "2" }, {})));
  const bot = Object.fromEntries(fields(feedbackRequest({ rating: "2", "bot-field": "spam" }, {})));

  assert.equal(person["bot-field"], "");
  assert.equal(person.comment, "");
  assert.equal(bot["bot-field"], "spam");
});
