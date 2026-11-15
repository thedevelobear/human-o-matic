// The feedback form's settings and its request (the website plan's section 6, ADRs 0099, 0127 and
// 0128): Netlify Forms keeps what the page posts, URL-encoded to the site's own `/`, in the six
// fields of the form's static copy in index.html. The settings are the render's, read from the
// session, never the file, its name, a note or a section's words. It touches no DOM, so
// `node --test` loads it.

import { GROUP_CONTROLS } from "./forms.js";

/** The form's fields, the same in the page's request and in index.html's static copy. */
export const FIELDS = ["form-name", "bot-field", "rating", "comment", "contact", "settings"];
/** The most characters a comment and a contact hold, as the form's `maxlength` holds them. */
export const LIMITS = { comment: 2000, contact: 200 };

/** Of `controls`, only `ControlVector`'s, which a group's Fine-tune holds every one of. */
function own(controls) {
  return Object.fromEntries(GROUP_CONTROLS.filter((name) => name in controls).map((name) => [name, controls[name]]));
}

/** The settings feedback keeps, from the kits the song was opened with and a `get_sections`
 * reply: the style, seed and bars, how many sections, the song's own controls, and each section's
 * own controls and take, in song order. */
export function settingsOf({ from_map, to_map }, { style, seed, bars, controls, sections }) {
  return {
    from_map,
    to_map,
    style,
    seed,
    bars,
    sections: sections.length,
    song_controls: own(controls),
    section_controls: sections.map((section) => own(section.controls)),
    takes: sections.map((section) => section.take),
  };
}

/** The request that posts the form, `values` its fields by name, as `fetch("/", ...)` takes it:
 * the six fields URL-encoded, the comment and the contact cut to their limits, and the settings
 * as one field of JSON. The honeypot is sent as it was found, so a bot that fills it is caught. */
export function feedbackRequest(values, settings) {
  const body = new URLSearchParams({
    "form-name": "feedback",
    "bot-field": values["bot-field"] ?? "",
    rating: values.rating ?? "",
    comment: (values.comment ?? "").slice(0, LIMITS.comment),
    contact: (values.contact ?? "").slice(0, LIMITS.contact),
    settings: JSON.stringify(settings),
  });
  return {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  };
}
