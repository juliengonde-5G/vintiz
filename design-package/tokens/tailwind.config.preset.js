/**
 * Vintiz Tailwind preset (charte v2 — 2026-04).
 *
 * Use:
 *   // tailwind.config.ts of the consumer project
 *   import vintiz from '@/design-package/tokens/tailwind.config.preset.js';
 *   export default {
 *     presets: [vintiz],
 *     content: [...],
 *   };
 *
 * Pair with:
 *   <link rel="stylesheet" href="/design-package/fonts/google-fonts.css">
 *   // or use next/font with families "Lexend Mega" + "Poppins" and set
 *   // --font-display / --font-body CSS variables.
 */
module.exports = {
  theme: {
    extend: {
      colors: {
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
      },
      fontFamily: {
        display: ["var(--font-display)", "Lexend Mega", "Poppins", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "Poppins", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "gradient-warm": "linear-gradient(135deg, #FFF3ED 0%, #FFEAF3 100%)",
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
};
