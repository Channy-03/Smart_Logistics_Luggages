import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#0B1513", ink2: "#4B5B57", ink3: "#8A9894", canvas: "#F6F8F7", mint: "#D9F5EA", brand: { DEFAULT: "#0E9F6E", light: "#34D399" } },
      fontFamily: { sans: ["var(--font-sans)", "system-ui", "sans-serif"], mono: ["var(--font-mono)", "ui-monospace", "monospace"] },
      boxShadow: { glass: "0 1px 0 rgba(11,21,19,.08), 0 20px 40px -24px rgba(11,40,30,.18)" },
    },
  },
  plugins: [],
} satisfies Config;
