import type { Config } from "tailwindcss";

// Charte graphique Vintiz v3 « Sauge Néo » (2026-04) — alignée avec apps/web.
// Tokens inlinés (pas d'import cross-folder pour rester compatible Docker build,
// le contexte ne contient que apps/site/). Source de vérité :
// design-package/tailwind.preset.ts + design-package/tokens/colors.json.
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        vz: {
          bg: "#F6F5F1",
          "bg-alt": "#ECEAE3",
          surface: "#FFFFFF",
          ink: "#0E0E0C",
          "ink-soft": "#4A4A47",
          "ink-mute": "#8B8B86",
          line: "#D5D3CC",
          teal: {
            DEFAULT: "#0B7A6A",
            deep: "#054238",
            soft: "#CDE5DF",
          },
          accent: {
            DEFAULT: "#E84E8B",
            soft: "#FFD5E5",
          },
          gold: "#8E7B57",
        },
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: { DEFAULT: "var(--card)", foreground: "var(--card-foreground)" },
        popover: { DEFAULT: "var(--popover)", foreground: "var(--popover-foreground)" },
        primary: { DEFAULT: "var(--primary)", foreground: "var(--primary-foreground)" },
        secondary: { DEFAULT: "var(--secondary)", foreground: "var(--secondary-foreground)" },
        muted: { DEFAULT: "var(--muted)", foreground: "var(--muted-foreground)" },
        accent: { DEFAULT: "var(--accent)", foreground: "var(--accent-foreground)" },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
      },
      fontFamily: {
        display: ["Fraunces", "Söhne Breit", "Cormorant Garamond", "serif"],
        body: ["Manrope", "Söhne", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        sans: ["Manrope", "system-ui", "sans-serif"],
        // Mockup preview (DM Serif Display chargé sur /dev/*)
        mockSerif: ["var(--font-mock-serif)", "DM Serif Display", "Georgia", "serif"],
      },
      fontSize: {
        "vz-hero": ["64px", { lineHeight: "1", letterSpacing: "-0.015em", fontWeight: "450" }],
        "vz-h1": ["40px", { lineHeight: "1.05", letterSpacing: "-0.01em", fontWeight: "500" }],
        "vz-h2": ["28px", { lineHeight: "1.15", fontWeight: "500" }],
        "vz-body": ["16px", { lineHeight: "1.55" }],
        "vz-meta": ["11px", { lineHeight: "1.4", letterSpacing: "0.12em" }],
      },
      borderRadius: {
        vz: "8px",
        "vz-lg": "16px",
        DEFAULT: "var(--radius)",
      },
      boxShadow: {
        "vz-soft": "0 1px 0 rgba(14,14,12,0.04), 0 16px 40px -20px rgba(14,14,12,0.16)",
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
