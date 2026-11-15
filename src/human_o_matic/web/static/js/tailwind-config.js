// Tailwind's Play CDN reads its configuration from `window.tailwind.config`, which this file sets
// right after the CDN's script, so the page needs no inline script (ADR 0125): the owner's
// palette and fonts. A classic script, not a module, so it runs before the CDN reads the page.
if ("tailwind" in window) {
  tailwind.config = {
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
}
