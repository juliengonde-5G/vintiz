import type { Config } from "tailwindcss";

// Charte graphique Vintiz v2 (2026-04) — alignée avec apps/web.
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tokens sémantiques (recommandés)
        teal: {
          DEFAULT: "#008678",
          50: "#E6F3F1",
          100: "#B3DDD8",
          200: "#80C7BF",
          300: "#4DB0A6",
          400: "#269A8F",
          500: "#008678",
          600: "#006B61",
          700: "#005049",
        },
        pink: {
          DEFAULT: "#FFC5DF",
          50: "#FFF5FA",
          100: "#FFEAF3",
          200: "#FFDCEB",
          300: "#FFC5DF",
          400: "#FFAED0",
          500: "#FF97C0",
          600: "#E66FA5",
          700: "#CC4889",
        },
        cream: "#FFF3ED",
        // Aliases historiques (compat — pointent vers les nouveaux tokens)
        "vintiz-teal": "#008678",
        "vintiz-pink": "#FFC5DF",
        "vintiz-black": "#000000",
        "vintiz-white": "#FFFFFF",
        "vintiz-bg": "#FFF3ED",
      },
      fontFamily: {
        display: ["var(--font-display)", "Lexend Mega", "Poppins", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "Poppins", "system-ui", "sans-serif"],
        // Alias historique
        serif: ["var(--font-display)", "Lexend Mega", "serif"],
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
