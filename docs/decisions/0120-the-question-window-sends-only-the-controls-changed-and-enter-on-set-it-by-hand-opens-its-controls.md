# 0120. The question window sends only the controls changed, and Enter on "Set it by hand" opens its controls

- **Status:** Accepted
- **Date:** 2026-11-15

- **Enter on "Set it by hand"** answers it and moves focus to the first of its controls, in the same tab, where Enter on any other answer opens the next tab. Enter in one of those controls opens the next tab, or Submit after the last question, as Enter on an answer does. A click on it answers it and stays, as any click does. Its controls show while the choice or the answer is on it, and the number keys stay ignored in them.
- **Fine-tune starts at the resolved values and sends only what was changed.** Each control on the Submit tab starts at its value as it will render: for a group, its first section's own over the song's over the style's defaults, read from `get_sections` and `set_style`; for the song-wide round, the song's over the defaults. Submit sends the controls moved since the round was drawn, beside what its answers set, and the song-wide round its style as it stands. A control left alone isn't sent, so it stays unset where it was unset. A round drawn again starts afresh from the session.
- **A group's round** sets every section of the group, and its ramp slider reaches the most any of them allows, `min(8, bars // 2)`. A section that allows fewer is clamped by the engine, which lists it in `clamped`.
- **A slider says its value in words** in its `aria-valuetext`, beside the number: a control from 0 to 1 as very low, low, medium, high or very high, by fifths; `feel` as pushed, on the beat or laid back; and `ramp` as its bars, or "no ramp".

**Why:** Enter can't both open "Set it by hand"'s controls and leave the tab, and its controls are why it is chosen. Sending only what was moved keeps an untouched slider from pinning a section to the value it showed, so a later song-wide answer still reaches it, and sending the round again changes nothing more.

**Consequences:** `feat/web-questions` adds each answer's controls to what Submit sends, and the echo. The page can't unset a control once it is sent; setting it to the default is the nearest.
