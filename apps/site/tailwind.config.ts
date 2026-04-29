import type { Config } from "tailwindcss";
import vintizPreset from "../../design-package/tailwind.preset";

// Charte graphique Vintiz v3 « Sauge Néo » (2026-04) — alignée avec apps/web.
const config: Config = {
  presets: [vintizPreset],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Mockup preview (DM Serif Display chargé sur /dev/*)
        mockSerif: ["var(--font-mock-serif)", "DM Serif Display", "Georgia", "serif"],
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.8s ease-out forwards",
      },
    },
  },
  plugins: [],
};
export default config;
