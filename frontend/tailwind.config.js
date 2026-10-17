/** @type {import('tailwindcss').Config} */
// Semantic tokens (kept since the first design so every component follows the theme):
// porcelain = page, paper = panel, pine = ink, mist = hairline; state colours: eucalyptus = healthy / brand green,
// saffron = warning, raspberry = failing / root cause, plum = prediction, lake = actions ("touched by the fix").
// Look: warm cream paper, serif display type, monospace for technical detail, hairlines instead of boxes.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        porcelain: "#F5F3EA", paper: "#FBFAF5", pine: { DEFAULT: "#1E2621", soft: "#6E726A" }, mist: "#E2DED0",
        eucalyptus: "#1F5C45", saffron: "#D98E2F", raspberry: "#D2513F", plum: "#7C66C7", lake: "#C9BBF2",
      },
      fontFamily: {
        display: ["'Instrument Serif'", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
