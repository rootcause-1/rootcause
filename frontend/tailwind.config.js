/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        porcelain: "#F2F3EE", paper: "#FBFBF7", pine: { DEFAULT: "#17312A", soft: "#4C6158" }, mist: "#DCE3DA",
        eucalyptus: "#5FA37F", saffron: "#F0A830", raspberry: "#D6265C", plum: "#7B4B94",
      },
      fontFamily: {
        display: ["'Bricolage Grotesque'", "system-ui", "sans-serif"],
        sans: ["'Instrument Sans'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
