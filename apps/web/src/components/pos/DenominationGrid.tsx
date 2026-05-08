'use client';

import React, { useMemo } from 'react';

import { formatCurrency } from '@/lib/format';

/** One row of the denomination grid (50 € × 5 = 250 €). */
export interface DenominationLine {
  denom: number; // EUR (5, 10, 20, 50, 100, 200, 500 — or 0.01, 0.02, … for coins)
  count: number;
}

export const BANKNOTES = [500, 200, 100, 50, 20, 10, 5];
export const COINS = [2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01];

interface Props {
  /** Current breakdown indexed by denom for editing. */
  value: DenominationLine[];
  onChange: (next: DenominationLine[]) => void;
  /** Hide the coins half — handy for the small drawer mode. */
  banknotesOnly?: boolean;
  /** Read-only render (Z report preview, locked drawer). */
  readOnly?: boolean;
}

function indexBy(rows: DenominationLine[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of rows) out[String(r.denom)] = r.count;
  return out;
}

function buildRows(idx: Record<string, number>): DenominationLine[] {
  return Object.entries(idx)
    .filter(([, count]) => count > 0)
    .map(([denom, count]) => ({ denom: Number(denom), count }))
    .sort((a, b) => b.denom - a.denom);
}

/**
 * Edit a denomination breakdown side-by-side with running subtotals.
 *
 * Used by:
 *  - ``CashDrawerOpenModal`` (mode "Détail")
 *  - ``CashDrawerCloseModal`` (aide au décompte + comparaison)
 *
 * Displays two columns (billets / pièces) and a footer with the live total
 * so the cashier can see "you have entered 287,50 €" while typing.
 */
export default function DenominationGrid({
  value,
  onChange,
  banknotesOnly = false,
  readOnly = false,
}: Props) {
  const idx = useMemo(() => indexBy(value), [value]);

  const update = (denom: number, count: number): void => {
    if (readOnly) return;
    const next = { ...idx };
    if (count > 0) {
      next[String(denom)] = count;
    } else {
      delete next[String(denom)];
    }
    onChange(buildRows(next));
  };

  const total = value.reduce((sum, r) => sum + r.denom * r.count, 0);

  const renderRow = (denom: number) => {
    const count = idx[String(denom)] ?? 0;
    const subtotal = denom * count;
    const label =
      denom >= 1
        ? `${denom} €`
        : `${Math.round(denom * 100)} cts`;
    return (
      <div
        key={denom}
        className="flex items-center gap-3 py-2 border-b border-vz-line last:border-b-0"
      >
        <div className="w-16 font-mono text-sm text-vz-ink-soft">{label}</div>
        <input
          type="number"
          min={0}
          step={1}
          inputMode="numeric"
          disabled={readOnly}
          value={count || ''}
          onChange={(e) =>
            update(denom, Math.max(0, parseInt(e.target.value || '0', 10) || 0))
          }
          className="flex-1 min-w-0 rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-right font-mono text-base text-vz-ink focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal disabled:bg-vz-bg-alt"
          placeholder="0"
          aria-label={`Nombre de coupures de ${label}`}
        />
        <div className="w-24 text-right font-mono text-sm tabular-nums text-vz-ink">
          {subtotal > 0 ? formatCurrency(subtotal) : '—'}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-4 md:grid-cols-2">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-vz-ink-mute">
            Billets
          </h3>
          <div className="rounded-lg border border-vz-line bg-vz-surface px-3 py-1">
            {BANKNOTES.map(renderRow)}
          </div>
        </section>
        {!banknotesOnly && (
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-vz-ink-mute">
              Pièces
            </h3>
            <div className="rounded-lg border border-vz-line bg-vz-surface px-3 py-1">
              {COINS.map(renderRow)}
            </div>
          </section>
        )}
      </div>

      <div className="flex items-center justify-between rounded-xl bg-vz-teal-soft px-4 py-3">
        <span className="text-sm font-medium text-vz-teal-deep">
          Total compté
        </span>
        <span className="font-mono text-2xl font-bold tabular-nums text-vz-teal-deep">
          {formatCurrency(total)}
        </span>
      </div>
    </div>
  );
}

/** Read-only sum from a breakdown, useful in parents that don't render the
 * editable grid (Z report preview, drawer summary card). */
export function totalFromBreakdown(rows: DenominationLine[]): number {
  return rows.reduce((sum, r) => sum + r.denom * r.count, 0);
}
