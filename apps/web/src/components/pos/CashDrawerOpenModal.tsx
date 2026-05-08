'use client';

import React, { useState } from 'react';

import Modal from '@/components/ui/Modal';
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
 * Cash drawer open modal — two modes:
 *  - **Détail** (default): denomination grid → total auto-calculated
 *  - **Rapide** (toggle): single numpad for the total amount
 *
 * Both modes POST the same shape to the API; ``opening_breakdown`` is null
 * in quick mode so the Z report later renders just the running total
 * without a side-by-side comparison row.
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
      // Reset for next session.
      setBreakdown([]);
      setQuickAmount(0);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ouvrir la caisse"
      closeOnBackdrop={false}
      actions={
        <>
          <button
            type="button"
            onClick={onClose}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-5 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
          >
            Annuler
          </button>
          <button
            type="button"
            disabled={!valid || submitting}
            onClick={() => void handleSubmit()}
            className="min-h-[48px] rounded-xl bg-vz-teal px-5 py-3 text-base font-semibold text-white transition-colors hover:bg-vz-teal-deep disabled:opacity-60"
          >
            {submitting ? 'Ouverture…' : 'Ouvrir la caisse'}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-xl bg-vz-bg-alt p-1">
          <button
            type="button"
            onClick={() => setDetailMode(true)}
            aria-pressed={detailMode}
            className={[
              'flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              detailMode
                ? 'bg-vz-surface text-vz-teal-deep shadow-sm'
                : 'text-vz-ink-soft hover:text-vz-ink',
            ].join(' ')}
          >
            Mode détail
          </button>
          <button
            type="button"
            onClick={() => setDetailMode(false)}
            aria-pressed={!detailMode}
            className={[
              'flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              !detailMode
                ? 'bg-vz-surface text-vz-teal-deep shadow-sm'
                : 'text-vz-ink-soft hover:text-vz-ink',
            ].join(' ')}
          >
            Mode rapide
          </button>
        </div>

        {detailMode ? (
          <>
            <p className="text-sm text-vz-ink-soft">
              Compte le fond de caisse au démarrage. Le détail est conservé
              pour la réconciliation et imprimé sur le rapport Z.
            </p>
            <DenominationGrid
              value={breakdown}
              onChange={setBreakdown}
            />
          </>
        ) : (
          <>
            <p className="text-sm text-vz-ink-soft">
              Saisis directement le total. Pratique quand le fond de caisse
              n'a pas changé depuis la dernière clôture.
            </p>
            <NumPad
              value={quickAmount}
              onChange={setQuickAmount}
              presets={[50, 100, 150, 200]}
            />
            <div className="rounded-xl bg-vz-teal-soft px-4 py-3 text-right">
              <span className="font-mono text-2xl font-bold tabular-nums text-vz-teal-deep">
                {formatCurrency(quickAmount)}
              </span>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
