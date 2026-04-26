'use client';

import React from 'react';

export type FashionSignal = {
  term: string;
  category: 'color' | 'cut' | 'brand';
  velocity: number; // 0..100
  source: string;
};

type Props = {
  signals: FashionSignal[];
};

const BUCKETS = [
  { kind: 'color', title: 'Couleurs en hausse', icon: '🎨' },
  { kind: 'cut', title: 'Coupes émergentes', icon: '✂️' },
  { kind: 'brand', title: 'Marques en hausse', icon: '🏷️' },
] as const;

function colorSwatch(name: string): string {
  const map: Record<string, string> = {
    bordeaux: '#722F37', moutarde: '#FFDB58', kaki: '#806B2A',
    marine: '#1B2845', rose: '#F4A4B5', noir: '#1A1A1A',
    blanc: '#FFFFFF', beige: '#E8DBC4', gris: '#9CA3AF',
    bleu: '#3B82F6', écru: '#F2EAD3', ecru: '#F2EAD3',
  };
  return map[name.toLowerCase()] || '#999';
}

export default function FashionTrendsWidget({ signals }: Props) {
  if (!signals.length) {
    return (
      <p className="text-sm text-gray-400">
        Aucun signal fashion-watch disponible. Le service récolte automatiquement
        Google Trends + Vinted public chaque nuit (à activer en L4 v2.5).
      </p>
    );
  }

  const grouped = BUCKETS.map((b) => ({
    ...b,
    items: signals.filter((s) => s.category === b.kind).sort((a, b) => b.velocity - a.velocity).slice(0, 3),
  }));

  return (
    <div className="grid md:grid-cols-3 gap-4">
      {grouped.map((bucket) => (
        <div key={bucket.kind} className="bg-white rounded-2xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xl">{bucket.icon}</span>
            <h3 className="font-medium text-black text-sm">{bucket.title}</h3>
          </div>
          {bucket.items.length === 0 ? (
            <p className="text-xs text-gray-400">Aucun signal cette semaine.</p>
          ) : (
            <ul className="space-y-2">
              {bucket.items.map((s) => (
                <li key={s.term} className="flex items-center gap-2">
                  {bucket.kind === 'color' ? (
                    <span
                      className="h-6 w-6 rounded-full border border-gray-200 flex-shrink-0"
                      style={{ backgroundColor: colorSwatch(s.term) }}
                    />
                  ) : (
                    <span className="h-6 w-6 rounded bg-teal-50 text-teal flex items-center justify-center text-[10px] font-bold flex-shrink-0">
                      {bucket.kind === 'cut' ? '✂' : 'B'}
                    </span>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-black capitalize truncate">{s.term}</div>
                    <div className="text-[10px] text-gray-500">{s.source}</div>
                  </div>
                  <span
                    className={`text-xs font-medium tabular-nums ${
                      s.velocity >= 50 ? 'text-green-600' : 'text-gray-500'
                    }`}
                  >
                    +{s.velocity.toFixed(0)}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
