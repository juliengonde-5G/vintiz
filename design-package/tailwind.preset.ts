// Vintiz — Sauge Néo · Tailwind preset
// Importer dans apps/web/tailwind.config.ts et apps/site/tailwind.config.ts :
//   import vintizPreset from '../../design-package/tailwind.preset';
//   export default { presets: [vintizPreset], content: [...], }

import type { Config } from 'tailwindcss';

const preset: Partial<Config> = {
  theme: {
    extend: {
      colors: {
        vz: {
          bg: '#F6F5F1',
          'bg-alt': '#ECEAE3',
          surface: '#FFFFFF',
          ink: '#0E0E0C',
          'ink-soft': '#4A4A47',
          'ink-mute': '#8B8B86',
          line: '#D5D3CC',
          teal: {
            DEFAULT: '#0B7A6A',
            deep: '#054238',
            soft: '#CDE5DF',
          },
          accent: {
            DEFAULT: '#E84E8B',
            soft: '#FFD5E5',
          },
          gold: '#8E7B57',
        },
        // shadcn aliases via CSS variables (defined in tokens.css)
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        card: { DEFAULT: 'var(--card)', foreground: 'var(--card-foreground)' },
        popover: { DEFAULT: 'var(--popover)', foreground: 'var(--popover-foreground)' },
        primary: { DEFAULT: 'var(--primary)', foreground: 'var(--primary-foreground)' },
        secondary: { DEFAULT: 'var(--secondary)', foreground: 'var(--secondary-foreground)' },
        muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
        accent: { DEFAULT: 'var(--accent)', foreground: 'var(--accent-foreground)' },
        border: 'var(--border)',
        input: 'var(--input)',
        ring: 'var(--ring)',
      },
      fontFamily: {
        display: ['Fraunces', 'Söhne Breit', 'Cormorant Garamond', 'serif'],
        body: ['Manrope', 'Söhne', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
        sans: ['Manrope', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        // Mobile / desktop pairs handled at component level via responsive prefixes
        'vz-hero': ['64px', { lineHeight: '1', letterSpacing: '-0.015em', fontWeight: '450' }],
        'vz-h1': ['40px', { lineHeight: '1.05', letterSpacing: '-0.01em', fontWeight: '500' }],
        'vz-h2': ['28px', { lineHeight: '1.15', fontWeight: '500' }],
        'vz-body': ['16px', { lineHeight: '1.55' }],
        'vz-meta': ['11px', { lineHeight: '1.4', letterSpacing: '0.12em' }],
      },
      borderRadius: {
        vz: '8px',
        'vz-lg': '16px',
        DEFAULT: 'var(--radius)',
      },
      boxShadow: {
        'vz-soft': '0 1px 0 rgba(14,14,12,0.04), 0 16px 40px -20px rgba(14,14,12,0.16)',
      },
    },
  },
};

export default preset;
