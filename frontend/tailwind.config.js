/** @type {import('tailwindcss').Config} */
// Semantic tokens (kept from the first design so every component follows the theme):
// porcelain = page, paper = panel, pine = ink, mist = hairline; state colours: eucalyptus ok, saffron warning,
// raspberry critical, plum prediction, lake "touched by the fix".
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        porcelain: "#0A0F1C", paper: "#121A2B", pine: { DEFAULT: "#E6EBF2", soft: "#94A3B8" }, mist: "#26324A",
        eucalyptus: "#10B981", saffron: "#F59E0B", raspberry: "#F43F5E", plum: "#A78BFA", lake: "#38BDF8",
      },
      fontFamily: {
        display: ["Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
