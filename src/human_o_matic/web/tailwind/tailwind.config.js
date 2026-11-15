// Tailwind's configuration for `uv run python tools/build_site.py css`, which builds
// static/tailwind.css with Tailwind's standalone CLI (ADR 0126): the owner's palette and fonts,
// and the page's files whose classes it keeps, read relative to this file. A class must be
// written whole in them, never put together from parts, or the CLI can't find it.
module.exports = {
  content: {
    relative: true,
    files: ["../static/index.html", "../static/js/*.js"],
  },
  theme: {
    extend: {
      colors: {
        parchment: "#E8E2D5",
        cream: "#F7F3EB",
        ink: "#141218",
        cosmic: "#1C2340",
        sunset: "#F28D35",
        magenta: "#E2587A",
        lavender: "#C9B8E8",
        stoneMuted: "#D6CFC0",
      },
      fontFamily: {
        display: ["Fredoka", "sans-serif"],
        sans: ["Space Grotesk", "sans-serif"],
        mono: ["Space Mono", "monospace"],
      },
    },
  },
};
