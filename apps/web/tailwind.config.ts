import type { Config } from "tailwindcss";

// Professional real-estate/finance palette: navy, teal, warm accent (Section 12.5).
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#12294a",
          50: "#eef2f7",
          700: "#1b2f52",
          900: "#0d1b33",
        },
        teal: {
          DEFAULT: "#127e7a",
          light: "#2aa79b",
        },
        warm: {
          DEFAULT: "#c98a2b",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica", "Arial"],
      },
    },
  },
  plugins: [],
};

export default config;
