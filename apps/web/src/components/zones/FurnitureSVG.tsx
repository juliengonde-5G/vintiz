'use client';

import React from 'react';

/**
 * 10 isometric SVG furniture assets, drawn inline so we ship no extra
 * static files. Each piece is centered at (0,0) inside its 60×60 viewBox
 * and uses a teal/grey palette consistent with the design system.
 *
 * For "iso 2.5D" we use a simple skew(-30deg) + rotate(30deg) on the
 * whole canvas in the parent component — these SVGs themselves are
 * normal 2D vectors that look isometric once placed on the skewed plane.
 */

type Props = {
  type: string;
  variant?: string | null;
  size?: number;
};

const COLORS = {
  wood: '#A47551',
  metal: '#9CA3AF',
  teal: '#1A7A6A',
  pink: '#E8B4D0',
  black: '#1A1A1A',
  cream: '#F6F5F1',
};

export default function FurnitureSVG({ type, variant, size = 60 }: Props) {
  const props = { width: size, height: size, viewBox: '0 0 60 60', xmlns: 'http://www.w3.org/2000/svg' };
  switch (type) {
    case 'portant':
      // Variants: S (60cm), M (120cm), L (200cm) → width
      const wRatio = variant === 'L' ? 50 : variant === 'S' ? 24 : 36;
      return (
        <svg {...props}>
          <line x1={30 - wRatio / 2} y1="20" x2={30 + wRatio / 2} y2="20" stroke={COLORS.metal} strokeWidth="2" />
          <line x1="30" y1="20" x2="30" y2="50" stroke={COLORS.metal} strokeWidth="2" />
          <line x1="22" y1="50" x2="38" y2="50" stroke={COLORS.metal} strokeWidth="3" />
          {/* hangers */}
          <rect x={30 - wRatio / 2 + 2} y="22" width="4" height="14" fill={COLORS.pink} rx="1" />
          <rect x={30 - wRatio / 2 + 8} y="22" width="4" height="14" fill={COLORS.teal} rx="1" />
          <rect x={30 - wRatio / 2 + 14} y="22" width="4" height="14" fill={COLORS.cream} rx="1" />
        </svg>
      );

    case 'mannequin':
      const skin = variant === 'enfant' ? '#FBD5BD' : COLORS.cream;
      return (
        <svg {...props}>
          <circle cx="30" cy="14" r="6" fill={skin} stroke={COLORS.black} />
          <path d="M22 22 L24 36 L36 36 L38 22 Z" fill={skin} stroke={COLORS.black} />
          <rect x="24" y="36" width="4" height="14" fill={COLORS.black} />
          <rect x="32" y="36" width="4" height="14" fill={COLORS.black} />
          {variant === 'femme' && <ellipse cx="30" cy="40" rx="10" ry="2" fill={COLORS.pink} opacity="0.4" />}
        </svg>
      );

    case 'etagere':
      const shelves = variant === '5n' ? 5 : 4;
      return (
        <svg {...props}>
          <rect x="12" y="10" width="36" height="40" fill={COLORS.wood} stroke={COLORS.black} />
          {Array.from({ length: shelves }, (_, i) => (
            <line
              key={i}
              x1="12" x2="48"
              y1={10 + (i + 1) * (40 / (shelves + 1))}
              y2={10 + (i + 1) * (40 / (shelves + 1))}
              stroke={COLORS.black} strokeWidth="1.5"
            />
          ))}
        </svg>
      );

    case 'table_presentation':
      return (
        <svg {...props}>
          <ellipse cx="30" cy="35" rx="20" ry="6" fill={COLORS.wood} stroke={COLORS.black} />
          <line x1="20" y1="36" x2="20" y2="50" stroke={COLORS.black} strokeWidth="2" />
          <line x1="40" y1="36" x2="40" y2="50" stroke={COLORS.black} strokeWidth="2" />
          {/* Folded clothes on top */}
          <rect x="24" y="22" width="6" height="6" fill={COLORS.pink} />
          <rect x="32" y="24" width="6" height="6" fill={COLORS.teal} />
        </svg>
      );

    case 'comptoir_caisse':
      return (
        <svg {...props}>
          <rect x="6" y="20" width="48" height="20" fill={COLORS.wood} stroke={COLORS.black} />
          <rect x="20" y="10" width="20" height="14" fill={COLORS.black} />
          <rect x="22" y="12" width="16" height="10" fill={COLORS.teal} />
          <text x="30" y="20" textAnchor="middle" fontSize="6" fill={COLORS.cream}>POS</text>
        </svg>
      );

    case 'cabine_essayage':
      return (
        <svg {...props}>
          <rect x="10" y="6" width="40" height="48" fill={COLORS.cream} stroke={COLORS.black} strokeWidth="1.5" />
          <path d="M10 10 Q30 18 50 10" fill={COLORS.pink} stroke={COLORS.black} strokeWidth="1" />
          <text x="30" y="50" textAnchor="middle" fontSize="6" fill={COLORS.black}>Essayage</text>
        </svg>
      );

    case 'vitrine':
      return (
        <svg {...props}>
          <rect x="4" y="10" width="52" height="35" fill="rgba(168,218,220,0.4)" stroke={COLORS.black} strokeWidth="1.5" />
          <line x1="20" y1="10" x2="20" y2="45" stroke={COLORS.black} strokeWidth="0.5" />
          <line x1="40" y1="10" x2="40" y2="45" stroke={COLORS.black} strokeWidth="0.5" />
          {/* mannequins behind */}
          <circle cx="14" cy="28" r="2" fill={COLORS.cream} />
          <circle cx="30" cy="28" r="2" fill={COLORS.cream} />
          <circle cx="46" cy="28" r="2" fill={COLORS.cream} />
          <text x="30" y="54" textAnchor="middle" fontSize="6" fill={COLORS.black}>Vitrine</text>
        </svg>
      );

    case 'mur':
      return (
        <svg {...props}>
          <rect x="0" y="26" width="60" height="8" fill={COLORS.black} />
        </svg>
      );

    case 'porte_entree':
      return (
        <svg {...props}>
          <rect x="20" y="8" width="20" height="44" fill="none" stroke={COLORS.black} strokeWidth="1.5" />
          <path d="M20 8 Q30 4 40 8" fill="none" stroke={COLORS.teal} strokeWidth="1.5" strokeDasharray="2,2" />
          <circle cx="36" cy="30" r="1.2" fill={COLORS.teal} />
          <text x="30" y="58" textAnchor="middle" fontSize="6" fill={COLORS.black}>Entrée</text>
        </svg>
      );

    case 'tete_gondole':
      return (
        <svg {...props}>
          <rect x="6" y="14" width="48" height="34" fill={COLORS.cream} stroke={COLORS.black} />
          <rect x="6" y="14" width="48" height="6" fill={COLORS.teal} />
          <text x="30" y="19" textAnchor="middle" fontSize="5" fill={COLORS.cream}>TOP DEAL</text>
          <line x1="6" y1="28" x2="54" y2="28" stroke={COLORS.black} strokeWidth="0.5" />
          <line x1="6" y1="38" x2="54" y2="38" stroke={COLORS.black} strokeWidth="0.5" />
        </svg>
      );

    default:
      return (
        <svg {...props}>
          <rect x="10" y="10" width="40" height="40" fill={COLORS.metal} stroke={COLORS.black} />
          <text x="30" y="32" textAnchor="middle" fontSize="6" fill={COLORS.black}>{type}</text>
        </svg>
      );
  }
}

export const FURNITURE_TYPES: { type: string; label: string; variants?: string[] }[] = [
  { type: 'portant', label: 'Portant', variants: ['S', 'M', 'L'] },
  { type: 'mannequin', label: 'Mannequin', variants: ['femme', 'homme', 'enfant'] },
  { type: 'etagere', label: 'Étagère', variants: ['4n', '5n'] },
  { type: 'table_presentation', label: 'Table' },
  { type: 'comptoir_caisse', label: 'Comptoir caisse' },
  { type: 'cabine_essayage', label: 'Cabine essayage' },
  { type: 'vitrine', label: 'Vitrine' },
  { type: 'mur', label: 'Mur' },
  { type: 'porte_entree', label: 'Porte d\'entrée' },
  { type: 'tete_gondole', label: 'Tête de gondole' },
];

export const ZONE_TAG_OPTIONS: { tag: string; label: string; color: string }[] = [
  { tag: 'femme', label: 'Femme', color: '#E8B4D0' },
  { tag: 'homme', label: 'Homme', color: '#3B82F6' },
  { tag: 'enfant', label: 'Enfant', color: '#FBBF24' },
  { tag: 'accessoire', label: 'Accessoire', color: '#A78BFA' },
  { tag: 'derniere_demarque', label: 'Dernière démarque', color: '#EF4444' },
  { tag: 'nouveaute', label: 'Nouveauté', color: '#10B981' },
  { tag: 'premium', label: 'Premium', color: '#F59E0B' },
  { tag: 'saisonnier', label: 'Saisonnier', color: '#06B6D4' },
  { tag: 'vitrine', label: 'Vitrine', color: '#1A7A6A' },
  { tag: 'tete_gondole', label: 'Tête de gondole', color: '#0EA5E9' },
];
