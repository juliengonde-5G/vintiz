'use client';

/**
 * Read-only store map used in the intake flow to pick a sale zone visually.
 *
 * Renders each zone as an absolutely-positioned coloured block using the
 * boutique's % layout coordinates (pos_x/pos_y/width/height, 0-100). The
 * selected zone is ringed; the AI-suggested zone is outlined and badged.
 * Purely presentational — the parent owns the zone list and selection.
 */

import React from 'react';

export interface PlanZone {
  id: string;
  name: string;
  color_code: string | null;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  shape?: string | null;
  capacity?: number;
  product_count?: number;
}

interface Props {
  zones: PlanZone[];
  selectedZoneId: string;
  suggestedZoneId?: string | null;
  onSelect: (zoneId: string) => void;
}

export default function StorePlanPicker({ zones, selectedZoneId, suggestedZoneId, onSelect }: Props) {
  return (
    <div
      className="relative w-full rounded-xl border border-vz-line bg-vz-bg-alt overflow-hidden"
      style={{ aspectRatio: '16 / 10' }}
    >
      {zones.map((z) => {
        const isSelected = z.id === selectedZoneId;
        const isSuggested = z.id === suggestedZoneId && !isSelected;
        const color = z.color_code || '#0B7A6A';
        const occupancy =
          z.capacity && z.capacity > 0 && z.product_count != null
            ? Math.round((z.product_count / z.capacity) * 100)
            : null;
        return (
          <button
            key={z.id}
            type="button"
            onClick={() => onSelect(z.id)}
            title={z.name}
            aria-pressed={isSelected}
            className={`absolute flex flex-col items-center justify-center text-center overflow-hidden transition-all focus:outline-none ${
              isSelected
                ? 'ring-4 ring-vz-ink z-10 shadow-lg'
                : isSuggested
                ? 'ring-2 ring-vz-ink/60 z-[5]'
                : 'hover:brightness-110'
            }`}
            style={{
              left: `${z.pos_x}%`,
              top: `${z.pos_y}%`,
              width: `${z.width}%`,
              height: `${z.height}%`,
              background: color,
              opacity: isSelected ? 1 : 0.82,
              borderRadius: z.shape === 'circle' ? '9999px' : '8px',
            }}
          >
            <span
              className="text-[10px] sm:text-xs font-semibold text-white leading-tight px-1"
              style={{ textShadow: '0 1px 2px rgba(0,0,0,0.55)' }}
            >
              {z.name}
            </span>
            {occupancy != null && (
              <span className="text-[8px] text-white/90" style={{ textShadow: '0 1px 2px rgba(0,0,0,0.55)' }}>
                {occupancy}%
              </span>
            )}
            {isSuggested && (
              <span className="absolute top-0.5 right-0.5 text-[7px] font-bold uppercase bg-white/90 text-vz-ink rounded px-1 py-0.5">
                Suggéré
              </span>
            )}
            {isSelected && (
              <span className="absolute top-0.5 right-0.5 text-[7px] font-bold uppercase bg-vz-ink text-white rounded px-1 py-0.5">
                ✓
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
