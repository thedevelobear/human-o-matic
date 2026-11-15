// Draws the fields of forms.js as the platform's own controls, each with its label and any hint
// tied to it by `aria-describedby`, and reads their values back by name. It sets no style: the
// CSP allows none but site.css's.

import { words } from "./forms.js";

/** An element named `name`, with `attributes`, true for one without a value, and `children`. */
export function element(name, attributes = {}, ...children) {
  const made = document.createElement(name);
  for (const [attribute, value] of Object.entries(attributes)) {
    if (value === true) {
      made.setAttribute(attribute, "");
    } else if (value !== false && value !== undefined && value !== null && value !== "") {
      made.setAttribute(attribute, String(value));
    }
  }
  made.append(...children);
  return made;
}

/** Draw `fields` at the end of `parent`, their ids under `prefix`. */
export function drawFields(parent, fields, prefix) {
  parent.append(...fields.map((field) => drawField(field, prefix)));
}

/**
 * The value of each named control under `parent`: a checkbox's as true or false, the checked
 * radio's of a group, and any other's as its text.
 */
export function readFields(parent) {
  const values = {};
  for (const control of parent.querySelectorAll("input[name], select[name]")) {
    if (control.type === "checkbox") {
      values[control.name] = control.checked;
    } else if (control.type !== "radio" || control.checked) {
      values[control.name] = control.value;
    }
  }
  return values;
}

/** Set each named control under `parent` to its value in `values`, but those in `skip`, as a
 * change from the page rather than the user: a slider's shown value and words follow it. */
export function writeFields(parent, values, skip = new Set()) {
  for (const control of parent.querySelectorAll("input[name], select[name]")) {
    if (skip.has(control.name) || !(control.name in values)) {
      continue;
    }
    if (control.type === "checkbox") {
      control.checked = values[control.name] === true;
    } else {
      control.value = String(values[control.name]);
    }
    if (control.type === "range") {
      parent.querySelector(`output[for="${control.id}"]`).value = control.value;
      control.setAttribute("aria-valuetext", words(control.name, control.value));
    }
  }
}

function drawField(field, prefix) {
  const id = `${prefix}-${field.name ?? field.legend ?? field.label}`.replace(/[^\w-]/g, "_");
  const hint = field.hint ? element("p", { id: `${id}-hint`, class: "hint" }, field.hint) : "";
  const described = hint && `${id}-hint`;
  const label = () => element("label", { for: id }, field.label);
  switch (field.type) {
    case "group": {
      const group = element("fieldset", { "aria-describedby": described });
      group.append(element("legend", {}, field.legend), hint);
      drawFields(group, field.fields, id);
      return group;
    }
    case "radio":
      return element(
        "fieldset",
        { "aria-describedby": described },
        element("legend", {}, field.label),
        hint,
        ...field.options.map((option, index) =>
          element(
            "div",
            { class: "choice" },
            element("input", {
              type: "radio",
              id: `${id}-${index}`,
              name: field.name,
              value: option.value,
              checked: option.value === field.value,
              required: field.required,
            }),
            element("label", { for: `${id}-${index}` }, option.label),
          ),
        ),
      );
    case "checkbox":
      return element(
        "div",
        { class: "field check" },
        element("input", {
          type: "checkbox",
          id,
          name: field.name,
          checked: field.checked,
          "aria-describedby": described,
        }),
        label(),
        hint,
      );
    case "select": {
      const select = element("select", {
        id,
        name: field.name,
        required: field.required,
        "aria-describedby": described,
      });
      select.append(...field.options.map(({ value, label }) => new Option(label, value)));
      select.value = field.value ?? field.options[0]?.value ?? "";
      return element("div", { class: "field" }, label(), select, hint);
    }
    case "range": {
      const slider = element("input", {
        type: "range",
        id,
        name: field.name,
        min: field.min,
        max: field.max,
        step: field.step,
        value: field.value,
        "aria-valuetext": words(field.name, field.value),
        "aria-describedby": described,
      });
      const shown = element("output", { for: id }, field.value);
      slider.addEventListener("input", () => {
        shown.value = slider.value;
        slider.setAttribute("aria-valuetext", words(field.name, slider.value));
      });
      return element("div", { class: "field range" }, label(), slider, shown, hint);
    }
    case "button":
      return element("button", { type: "button", name: field.name }, field.label);
    case "list":
      return element(
        "div",
        {},
        element("p", {}, field.label),
        element("ul", {}, ...field.items.map((item) => element("li", {}, item))),
      );
    default:
      return element(
        "div",
        { class: "field" },
        label(),
        element("input", {
          type: field.type,
          id,
          name: field.name,
          value: field.value,
          min: field.min,
          max: field.max,
          step: field.step,
          required: field.required,
          "aria-describedby": described,
        }),
        hint,
      );
  }
}
