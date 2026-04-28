// Vintiz — Charte v3
// 3 directions visuelles + tokens partagés

const VINTIZ_DIRECTIONS = {
  atelier: {
    id: 'atelier',
    name: 'Atelier',
    tagline: 'Éditorial premium · magazine couture',
    description: "Maison de mode autour du monogramme VZ. Crème chaud, teal de signature profond, encre noire. Mise en page asymétrique magazine, beaucoup d'air, sérif éditorial pour les titres. Pour la femme 35-55 sensible aux marques qui veut un retail seconde-main qui n'a pas honte de soi.",
    palette: {
      bg: '#F4ECE2',           // crème ivoire chaud
      bgAlt: '#EAE0D2',        // crème plus profond
      surface: '#FFFFFF',
      ink: '#1A1714',          // noir encre
      inkSoft: '#5C544A',      // gris chaud
      inkMute: '#9A8F80',      // taupe doux
      line: '#D9CDB9',         // ligne crème foncée
      teal: '#1F5D54',         // teal forêt sombre
      tealDeep: '#143F39',
      tealSoft: '#D8E4DF',
      accent: '#C2603B',       // brique terracotta
      accentSoft: '#F0DAC9',
      gold: '#A8895A',         // hint or sépia (pour détails fins, jamais grand)
    },
    type: {
      display: '"Cormorant Garamond", "EB Garamond", Georgia, serif',
      displayWeight: '500',
      displayItalic: 'italic',
      body: '"Inter Tight", "Söhne", system-ui, sans-serif',
      label: '"Inter Tight", system-ui, sans-serif',
      mono: '"JetBrains Mono", ui-monospace, monospace',
    },
    radius: '4px',
    radiusLg: '10px',
    shadow: '0 1px 0 rgba(26,23,20,0.04), 0 12px 32px -16px rgba(26,23,20,0.18)',
    feel: 'editorial',
  },
  sauge: {
    id: 'sauge',
    name: 'Sauge',
    tagline: 'Premium naturel · seconde main raisonnée',
    description: "Tonalité plus calme, plus durable. Reprend la palette chaude d'Atelier (crème ivoire, teal forêt, terracotta) mais en appose un traitement contemporain géométrique : Fraunces + Manrope, gros chiffres, mises en page de documentation. L'engagement écoresponsable est porté par les choix de matière, pas par un message militant.",
    palette: {
      bg: '#F4ECE2',
      bgAlt: '#EAE0D2',
      surface: '#FFFFFF',
      ink: '#1A1714',
      inkSoft: '#5C544A',
      inkMute: '#9A8F80',
      line: '#D9CDB9',
      teal: '#1F5D54',
      tealDeep: '#143F39',
      tealSoft: '#D8E4DF',
      accent: '#C2603B',
      accentSoft: '#F0DAC9',
      gold: '#A8895A',
    },
    type: {
      display: '"Fraunces", "Söhne Breit", "Cormorant Garamond", serif',
      displayWeight: '450',
      displayItalic: 'normal',
      body: '"Manrope", "Söhne", system-ui, sans-serif',
      label: '"Manrope", system-ui, sans-serif',
      mono: '"JetBrains Mono", ui-monospace, monospace',
    },
    radius: '8px',
    radiusLg: '16px',
    shadow: '0 1px 0 rgba(28,31,27,0.03), 0 16px 40px -20px rgba(28,31,27,0.16)',
    feel: 'natural',
  },
  neo: {
    id: 'neo',
    name: 'Néo',
    tagline: 'Contemporain · Vinted-natif élevé',
    description: "Plus jeune, plus tendu. Off-white froid, teal vif intense, flash rose intentionnel comme accent éditorial (jamais comme remplissage). Display grotesque haute (Anton-like) jouant les contrastes d'échelle, body neo-grotesque précis. Photo grande, mises en page denses-mais-ordonnées. Pour gagner les 18-30 sans perdre les 35-55.",
    palette: {
      bg: '#F6F5F1',
      bgAlt: '#ECEAE3',
      surface: '#FFFFFF',
      ink: '#0E0E0C',
      inkSoft: '#4A4A47',
      inkMute: '#8B8B86',
      line: '#D5D3CC',
      teal: '#0B7A6A',
      tealDeep: '#054238',
      tealSoft: '#CDE5DF',
      accent: '#E84E8B',       // rose magenta franc
      accentSoft: '#FFD5E5',
      gold: '#8E7B57',
    },
    type: {
      display: '"Archivo", "Antonio", "Söhne Schmal", system-ui, sans-serif',
      displayWeight: '700',
      displayItalic: 'normal',
      body: '"Geist", "Söhne", system-ui, sans-serif',
      label: '"Geist Mono", ui-monospace, monospace',
      mono: '"Geist Mono", "JetBrains Mono", ui-monospace, monospace',
    },
    radius: '2px',
    radiusLg: '6px',
    shadow: '0 1px 0 rgba(14,14,12,0.06), 0 8px 24px -12px rgba(14,14,12,0.2)',
    feel: 'contemporary',
  },
};

window.VINTIZ_DIRECTIONS = VINTIZ_DIRECTIONS;

// Inject all directions as CSS custom property scopes
function injectDirectionStyles() {
  const css = Object.values(VINTIZ_DIRECTIONS).map(d => `
    [data-dir="${d.id}"] {
      --bg: ${d.palette.bg};
      --bg-alt: ${d.palette.bgAlt};
      --surface: ${d.palette.surface};
      --ink: ${d.palette.ink};
      --ink-soft: ${d.palette.inkSoft};
      --ink-mute: ${d.palette.inkMute};
      --line: ${d.palette.line};
      --teal: ${d.palette.teal};
      --teal-deep: ${d.palette.tealDeep};
      --teal-soft: ${d.palette.tealSoft};
      --accent: ${d.palette.accent};
      --accent-soft: ${d.palette.accentSoft};
      --gold: ${d.palette.gold};
      --font-display: ${d.type.display};
      --font-display-weight: ${d.type.displayWeight};
      --font-display-style: ${d.type.displayItalic};
      --font-body: ${d.type.body};
      --font-label: ${d.type.label};
      --font-mono: ${d.type.mono};
      --radius: ${d.radius};
      --radius-lg: ${d.radiusLg};
      --shadow: ${d.shadow};
    }
  `).join('\n');
  const style = document.createElement('style');
  style.id = 'vintiz-directions';
  style.textContent = css;
  document.head.appendChild(style);
}
injectDirectionStyles();
