import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
          "Apple Color Emoji",
          "Segoe UI Emoji",
          "Segoe UI Symbol",
          "Noto Color Emoji",
        ],
      },
      colors: {
        surface: "hsl(var(--surface) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",
      },
      boxShadow: {
        glass: "0 20px 70px -32px rgba(15, 23, 42, 0.45)",
      },
    },
  },
  plugins: [],
} satisfies Config;
