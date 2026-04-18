import type { Config } from "tailwindcss";

// Charte graphique Vintiz v2 (2026-04)
//   Teal   #008678   (signature)
//   Rose   #FFC5DF   (accent)
//   Noir   #000000
//   Crème  #FFF3ED   (fond chaud)
//   Blanc  #FFFFFF
// Typographie : Lexend Mega (titres), Poppins (texte) — injectées par next/font.
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
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
          800: "#003530",
          900: "#001B17",
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
        black: "#000000",
        background: "#FFF3ED",
        foreground: "#000000",
      },
      fontFamily: {
        display: ["var(--font-display)", "Lexend Mega", "Poppins", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "Poppins", "system-ui", "sans-serif"],
      },
      minHeight: {
        touch: "44px",
      },
      minWidth: {
        touch: "44px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(0, 134, 120, 0.04), 0 4px 16px rgba(0, 134, 120, 0.06)",
        depth: "0 2px 4px rgba(0, 0, 0, 0.04), 0 12px 32px rgba(0, 134, 120, 0.10)",
        glow: "0 0 0 3px rgba(0, 134, 120, 0.12)",
        card: "0 1px 3px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.04)",
      },
      backgroundImage: {
        "gradient-teal": "linear-gradient(135deg, #008678 0%, #26A695 100%)",
        "gradient-warm": "linear-gradient(135deg, #FFF3ED 0%, #FFEAF3 100%)",
        "gradient-signature": "linear-gradient(135deg, #008678 0%, #FFC5DF 100%)",
        "gradient-card": "linear-gradient(180deg, #FFFFFF 0%, #FFF9F5 100%)",
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
