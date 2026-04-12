import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        pink: {
          DEFAULT: "#E8B4D0",
          50: "#FFF5F8",
          100: "#FDEEF4",
          200: "#F5D4E5",
          300: "#E8B4D0",
          400: "#D98FBA",
          500: "#C96AA3",
          600: "#B24A8A",
        },
        teal: {
          DEFAULT: "#2A8B8B",
          50: "#E6F5F5",
          100: "#CCE8E8",
          200: "#99D1D1",
          300: "#66BABA",
          400: "#33A3A3",
          500: "#2A8B8B",
          600: "#1F6868",
          700: "#154545",
        },
        black: "#1A1A1A",
        background: "#FFF5F8",
        foreground: "#1A1A1A",
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "Times New Roman", "Times", "serif"],
        sans: [
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      minHeight: {
        touch: "44px",
      },
      minWidth: {
        touch: "44px",
      },
    },
  },
  plugins: [],
};
export default config;
