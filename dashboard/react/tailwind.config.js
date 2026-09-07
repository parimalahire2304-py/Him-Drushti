/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        hds: {
          bg:    "#070c14",
          panel: "#0f1724",
          border:"#1e2d44",
          navy:  "#0b1220",
          blue:  "#2e7dff",
          cyan:  "#00d4ff",
          green: "#00e676",
          amber: "#ffb300",
          red:   "#ff3d4e",
          text:  "#c8d6e5",
          dim:   "#6b7f99",
        },
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', "Consolas", "ui-monospace", "monospace"],
        sans: ['"Source Sans 3"', "Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
