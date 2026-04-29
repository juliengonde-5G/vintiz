import type { Config } from "tailwindcss";
import vintizPreset from "../../design-package/tailwind.preset";

// Charte graphique Vintiz v3 « Sauge Néo » (2026-04)
//   bg     #F6F5F1 (off-white frais)
//   teal   #0B7A6A (signature, plus vif qu'en v2)
//   accent #E84E8B (magenta éditorial — célébration uniquement)
//   ink    #0E0E0C
// Typographie : Fraunces (display) + Manrope (body) + JetBrains Mono — chargées via globals.css.
const config: Config = {
  presets: [vintizPreset],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      minHeight: {
        touch: "44px",
      },
      minWidth: {
        touch: "44px",
      },
      keyframes: {
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "slide-up": "slide-up 220ms ease-out both",
        "slide-in-right": "slide-in-right 220ms ease-out both",
        shimmer: "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
