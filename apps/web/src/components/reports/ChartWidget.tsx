'use client';

/**
 * Lightweight, dependency-free chart renderer for the « Rapports sur-mesure ».
 *
 * Renders a query result ({format, rows:[{key,value}]}) as one of:
 *   kpi   — single big number
 *   bar   — horizontal bars (categorical)
 *   line  — SVG line (time series)
 *   pie   — SVG donut
 *   table — key / value table
 *
 * Kept in pure SVG/CSS (no chart lib) to match the rest of the codebase.
 */

import React from 'react';

export type ChartType = 'kpi' | 'bar' | 'line' | 'pie' | 'table';
export interface Row { key: string; value: number }
export interface QueryResult {
  rows: Row[];
  format?: 'currency' | 'number' | string;
  measure_label?: string;
  dimension?: string | null;
}

const PALETTE = ['#0B7A6A', '#E84E8B', '#8E7B57', '#054238', '#CDE5DF', '#4A4A47', '#0E8A76', '#B5638A'];

export function fmtValue(v: number, format?: string): string {
  if (format === 'currency') {
    return `${v.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
  }
  return v.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
}

export default function ChartWidget({ type, data }: { type: ChartType; data: QueryResult | null }) {
  if (!data) return <div className="text-sm text-vz-ink-mute py-6 text-center">…</div>;
  const rows = data.rows || [];
  if (rows.length === 0) return <div className="text-sm text-vz-ink-mute py-6 text-center">Aucune donnée sur la période.</div>;

  if (type === 'kpi') {
    const total = rows.reduce((s, r) => s + r.value, 0);
    return (
      <div className="py-4 text-center">
        <div className="text-4xl font-bold text-vz-teal font-mono">{fmtValue(total, data.format)}</div>
        <div className="text-xs text-vz-ink-mute mt-1">{data.measure_label}</div>
      </div>
    );
  }

  if (type === 'table') {
    return (
      <div className="overflow-x-auto max-h-72">
        <table className="w-full text-sm">
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-vz-line/60">
                <td className="py-1.5 pr-3 text-vz-ink-soft">{r.key}</td>
                <td className="py-1.5 text-right font-mono text-vz-ink">{fmtValue(r.value, data.format)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (type === 'bar') {
    const max = Math.max(...rows.map((r) => r.value), 1);
    return (
      <div className="space-y-1.5 py-1 max-h-72 overflow-y-auto">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-28 truncate text-vz-ink-soft" title={r.key}>{r.key}</span>
            <div className="flex-1 bg-vz-bg-alt rounded h-5 relative overflow-hidden">
              <div className="h-full rounded" style={{ width: `${(r.value / max) * 100}%`, background: PALETTE[i % PALETTE.length] }} />
            </div>
            <span className="w-20 text-right font-mono text-vz-ink">{fmtValue(r.value, data.format)}</span>
          </div>
        ))}
      </div>
    );
  }

  if (type === 'line') {
    const w = 320, h = 140, pad = 24;
    const max = Math.max(...rows.map((r) => r.value), 1);
    const n = rows.length;
    const x = (i: number) => pad + (n <= 1 ? (w - 2 * pad) / 2 : (i * (w - 2 * pad)) / (n - 1));
    const y = (v: number) => h - pad - (v / max) * (h - 2 * pad);
    const pts = rows.map((r, i) => `${x(i)},${y(r.value)}`).join(' ');
    return (
      <div className="py-1">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 180 }}>
          <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#D5D3CC" strokeWidth="1" />
          {n > 1 && <polyline points={pts} fill="none" stroke="#0B7A6A" strokeWidth="2" />}
          {rows.map((r, i) => (
            <circle key={i} cx={x(i)} cy={y(r.value)} r="2.5" fill="#0B7A6A" />
          ))}
        </svg>
        <div className="flex justify-between text-[10px] text-vz-ink-mute mt-1 px-1">
          <span>{rows[0]?.key}</span>
          <span>{rows[rows.length - 1]?.key}</span>
        </div>
      </div>
    );
  }

  // pie / donut
  const total = rows.reduce((s, r) => s + r.value, 0) || 1;
  let acc = 0;
  const R = 60, C = 70, stroke = 26;
  const circ = 2 * Math.PI * R;
  return (
    <div className="flex items-center gap-4 py-2 flex-wrap">
      <svg viewBox="0 0 140 140" width="130" height="130">
        {rows.slice(0, 8).map((r, i) => {
          const frac = r.value / total;
          const dash = frac * circ;
          const el = (
            <circle key={i} cx={C} cy={C} r={R} fill="none"
              stroke={PALETTE[i % PALETTE.length]} strokeWidth={stroke}
              strokeDasharray={`${dash} ${circ - dash}`}
              strokeDashoffset={-acc * circ}
              transform={`rotate(-90 ${C} ${C})`} />
          );
          acc += frac;
          return el;
        })}
      </svg>
      <div className="text-xs space-y-1">
        {rows.slice(0, 8).map((r, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: PALETTE[i % PALETTE.length] }} />
            <span className="text-vz-ink-soft truncate max-w-[120px]" title={r.key}>{r.key}</span>
            <span className="font-mono text-vz-ink-mute">{Math.round((r.value / total) * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
