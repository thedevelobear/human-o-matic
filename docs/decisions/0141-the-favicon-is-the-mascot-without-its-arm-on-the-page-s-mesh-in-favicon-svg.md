# 0141. The favicon is the mascot without its arm, on the page's mesh, in `favicon.svg`

- **Status:** Proposed
- **Date:** 2026-11-17

- The site's favicon is `favicon.svg`, beside the page, linked from `index.html` and `check.html` as `<link rel="icon" href="favicon.svg" type="image/svg+xml">`. The CSP's `img-src 'self'` allows it.
- It is the page's mascot, `index.html`'s `mascot` symbol, without its arm: the rubber-hose arm, the floppy disk it holds and the hand's circle are left out. The rest, the CRT with its screen, eyes and smile, its two dots and the disk drive with its slot and green light, keeps the symbol's shapes and colours, drawn 1.4 times larger to fill about four fifths of the icon. Its strokes are thicker than the page's, its dots a little larger, and the CRT's thin vent line is left out, since it blurs the CRT's chin into grey at 16 px.
- Its background is a square with rounded corners in the page's iridescent mesh: `.iridescent-mesh`'s four gradients, sunset `#F28D35`, magenta `#E2587A` and amber `#F6C270` over the dusk base, written in the SVG for a square, since an SVG file can't use the page's classes. The screen is the page's `crt-screen` gradient. The file holds no script or style and refers to nothing outside itself.
- Only the SVG is given: no PNG or ICO, and no Apple touch icon.

**Why:** A tab shows the icon at 16 px, or at 32 on a high-density screen. With the arm and the floppy disk above its top right, the CRT takes about half the icon's width and the disk blurs into a smudge at 16 px; without them the CRT fills four fifths of it and its face reads. Checked by eye in renders at 256, 32 and 16 px: at 32 every part kept reads, and at 16 the CRT, its screen, its eyes and the drive.

**Consequences:** [ADR 0110](0110-the-site-looks-vaporwave-from-original-artwork-shaped-by-apple-s-design-principles.md)'s favicon of a striped sun, superseded with the rest of that ADR by [ADR 0125](0125-the-page-takes-the-owner-s-design-in-tailwind-from-its-play-cdn-with-google-fonts-the-mascot-as-its-logo-and-a-loading-view.md), is not made. A browser that takes no SVG favicon shows its own default icon; a PNG or ICO beside the SVG would need a tool that rasterizes it, which the build doesn't have. A change to the mascot is made again in `favicon.svg` by hand.
