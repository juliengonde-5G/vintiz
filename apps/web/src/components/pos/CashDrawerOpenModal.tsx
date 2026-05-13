'use client';

import React, { useState } from 'react';

import NumPad from '@/components/ui/NumPad';
import { formatCurrency } from '@/lib/format';

import DenominationGrid, {
  type DenominationLine,
  totalFromBreakdown,
} from './DenominationGrid';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Default to detail mode (true) or quick mode (false). PR 5 surfaces
   * the toggle in CashManagementSettingsPanel. */
  defaultDetailMode?: boolean;
  /** Handler — sends ``POST /api/pos/drawer/open`` with breakdown when
   * detail mode is on. The cashier ID, when relevant, is injected by
   * the parent (drives ``cashier_id`` field). */
  onSubmit: (payload: {
    opening_amount: number;
    opening_breakdown: DenominationLine[] | null;
  }) => Promise<void> | void;
}

/**
 * Cash drawer open — Odoo 17 fullscreen pattern. 2 columns: left side
 * carries the explanation + mode toggle + running total ; right side
 * carries the input (DenominationGrid or NumPad). Bottom bar with
 * cancel + confirm.
 *
 * Same two modes as before — détail (denomination breakdown) or rapide
 * (single total). The API payload is unchanged.
 */
export default function CashDrawerOpenModal({
  open,
  onClose,
  defaultDetailMode = true,
  onSubmit,
}: Props) {
  const [detailMode, setDetailMode] = useState<boolean>(defaultDetailMode);
  const [breakdown, setBreakdown] = useState<DenominationLine[]>([]);
  const [quickAmount, setQuickAmount] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);

  const total = detailMode ? totalFromBreakdown(breakdown) : quickAmount;
  const valid = total > 0;

  const handleSubmit = async (): Promise<void> => {
    if (!valid) return;
    setSubmitting(true);
    try {
      await onSubmit({
        opening_amount: total,
        opening_breakdown: detailMode ? breakdown : null,
      });
      setBreakdown([]);
      setQuickAmount(0);
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[58] bg-vz-bg flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg">
        <button
          onClick={onClose}
          disabled={submitting}
          className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px] disabled:opacity-50"
          aria-label="Annuler"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span className="text-sm font-medium">Retour</span>
        </button>
        <div className="h-7 w-px bg-white/15" />
        <h1 className="font-display text-lg">Ouverture de caisse</h1>
        <div className="flex-1" />
        <div className="flex flex-col items-end leading-tight">
          <span className="text-[10px] opacity-70 uppercase tracking-wider">Fond de caisse</span>
          <span className="font-display text-2xl font-bold font-mono">{formatCurrency(total)}</span>
        </div>
      </header>

      {/* Body — 2 columns */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT — context + mode toggle */}
        <div className="w-[360px] xl:w-[400px] flex flex-col bg-white border-r border-vz-line p-5 gap-4">
          <section>
            <h2 className="font-display text-base text-vz-ink mb-2">Mode de saisie</h2>
            <div className="flex items-center justify-between rounded-xl bg-vz-bg-alt p-1">
              <button
                type="button"
                onClick={() => setDetailMode(true)}
                aria-pressed={detailMode}
                className={`flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors min-h-[44px] ${
                  detailMode
                    ? 'bg-vz-surface text-vz-teal-deep shadow-sm'
                    : 'text-vz-ink-soft hover:text-vz-ink'
                }`}
              >
                Détail
              </button>
              <button
                type="button"
                onClick={() => setDetailMode(false)}
                aria-pressed={!detailMode}
                className={`flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors min-h-[44px] ${
                  !detailMode
                    ? 'bg-vz-surface text-vz-teal-deep shadow-sm'
                    : 'text-vz-ink-soft hover:text-vz-ink'
                }`}
              >
                Rapide
              </button>
            </div>
          </section>

          <section className="bg-vz-bg-alt rounded-xl p-3 text-sm text-vz-ink-soft">
            {detailMode ? (
              <>
                Compte le fond de caisse au démarrage. Le détail est conservé
                pour la réconciliation et imprimé sur le rapport Z.
              </>
            ) : (
              <>
                Saisis directement le total. Pratique quand le fond de caisse
                n&apos;a pas changé depuis la dernière clôture.
              </>
            )}
          </section>

          <section className="mt-auto p-4 bg-vz-teal-soft rounded-xl text-center">
            <p className="text-xs uppercase tracking-wider text-vz-teal-deep mb-1">Total fond de caisse</p>
            <p className="font-mono text-3xl font-bold text-vz-teal-deep tabular-nums">
              {formatCurrency(total)}
            </p>
          </section>
        </div>

        {/* RIGHT — input */}
        <div className="flex-1 overflow-y-auto bg-vz-bg p-5">
          {detailMode ? (
            <DenominationGrid value={breakdown} onChange={setBreakdown} />
          ) : (
            <div className="max-w-md mx-auto">
              <NumPad
                value={quickAmount}
                onChange={setQuickAmount}
                presets={[50, 100, 150, 200]}
              />
            </div>
          )}
        </div>
      </div>

      {/* Bottom action bar */}
      <footer className="flex-shrink-0 bg-white border-t border-vz-line px-4 md:px-6 py-3 flex items-center gap-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
        <button
          onClick={onClose}
          disabled={submitting}
          className="px-5 py-3 rounded-xl text-sm font-medium text-vz-ink-soft bg-vz-bg-alt hover:bg-vz-line transition-colors min-h-[52px] disabled:opacity-50"
        >
          Annuler
        </button>
        <button
          type="button"
          disabled={!valid || submitting}
          onClick={() => void handleSubmit()}
          className={`flex-1 py-3 rounded-xl text-lg font-bold transition-colors min-h-[52px] flex items-center justify-center gap-3 ${
            !valid || submitting
              ? 'bg-vz-line text-vz-ink-mute cursor-not-allowed'
              : 'bg-vz-teal text-white hover:bg-vz-teal-deep active:bg-vz-teal-deep shadow-lg'
          }`}
        >
          {submitting ? (
            <>
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Ouverture…
            </>
          ) : (
            <>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="10" width="18" height="10" rx="1" />
                <path d="M3 10V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4" />
                <line x1="10" y1="15" x2="14" y2="15" />
              </svg>
              Ouvrir la caisse — {formatCurrency(total)}
            </>
          )}
        </button>
      </footer>
    </div>
  );
}
