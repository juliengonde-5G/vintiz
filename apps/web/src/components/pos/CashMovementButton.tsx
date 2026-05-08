'use client';

import React, { useState } from 'react';

import Modal from '@/components/ui/Modal';
import NumPad from '@/components/ui/NumPad';
import { formatCurrency } from '@/lib/format';

type Direction = 'in' | 'out';
type Reason =
  | 'bank_deposit'
  | 'supplier_payment'
  | 'personal_withdrawal'
  | 'float_top_up'
  | 'other';

const REASONS_OUT: { id: Reason; label: string }[] = [
  { id: 'bank_deposit', label: 'Dépôt banque' },
  { id: 'supplier_payment', label: 'Paiement fournisseur' },
  { id: 'personal_withdrawal', label: 'Prélèvement personnel' },
  { id: 'other', label: 'Autre sortie' },
];

const REASONS_IN: { id: Reason; label: string }[] = [
  { id: 'float_top_up', label: 'Réappro. fond de caisse' },
  { id: 'other', label: 'Autre entrée' },
];

interface Props {
  /** Disable when no drawer is currently open. */
  disabled?: boolean;
  /** Submit handler — POST /api/pos/cash-movements. */
  onSubmit: (payload: {
    direction: Direction;
    amount: number;
    reason: Reason;
    note: string | null;
  }) => Promise<void> | void;
}

/**
 * Toolbar button that opens the "Mouvement de caisse" modal.
 *
 * Records a mid-day cash flow (entrée/sortie) on the currently open drawer
 * — used for bank deposits, supplier cash-payments, owner withdrawals and
 * float top-ups. The Z report later subtracts these from the expected total
 * so a 200 € morning deposit doesn't surface as a discrepancy at closing.
 *
 * No PUT/DELETE — the API enforces append-only for NF525 audit. To correct
 * a typo, log the inverse movement with a clarifying note.
 */
export default function CashMovementButton({ disabled, onSubmit }: Props) {
  const [open, setOpen] = useState(false);
  const [direction, setDirection] = useState<Direction>('out');
  const [amount, setAmount] = useState<number>(0);
  const [reason, setReason] = useState<Reason>('bank_deposit');
  const [note, setNote] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  const reasons = direction === 'in' ? REASONS_IN : REASONS_OUT;
  const valid = amount > 0;

  const handleClose = (): void => {
    if (submitting) return;
    setOpen(false);
    setAmount(0);
    setNote('');
    setDirection('out');
    setReason('bank_deposit');
  };

  const handleSubmit = async (): Promise<void> => {
    if (!valid) return;
    setSubmitting(true);
    try {
      await onSubmit({
        direction,
        amount,
        reason,
        note: note.trim() || null,
      });
      handleClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        title={disabled ? 'Ouvre la caisse pour saisir un mouvement.' : undefined}
        className="min-h-[44px] rounded-xl border border-vz-line bg-vz-surface px-4 py-2 text-sm font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-50"
      >
        Mouvement caisse
      </button>

      <Modal
        open={open}
        onClose={handleClose}
        title="Mouvement de caisse"
        closeOnBackdrop={false}
        actions={
          <>
            <button
              type="button"
              onClick={handleClose}
              disabled={submitting}
              className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-5 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-60"
            >
              Annuler
            </button>
            <button
              type="button"
              disabled={!valid || submitting}
              onClick={() => void handleSubmit()}
              className="min-h-[48px] rounded-xl bg-vz-teal px-5 py-3 text-base font-semibold text-white transition-colors hover:bg-vz-teal-deep disabled:opacity-60"
            >
              {submitting ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          {/* Direction toggle */}
          <div className="flex items-center justify-between rounded-xl bg-vz-bg-alt p-1">
            {(['out', 'in'] as Direction[]).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => {
                  setDirection(d);
                  setReason(d === 'in' ? 'float_top_up' : 'bank_deposit');
                }}
                aria-pressed={direction === d}
                className={[
                  'flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  direction === d
                    ? 'bg-vz-surface text-vz-teal-deep shadow-sm'
                    : 'text-vz-ink-soft hover:text-vz-ink',
                ].join(' ')}
              >
                {d === 'out' ? 'Sortie' : 'Entrée'}
              </button>
            ))}
          </div>

          {/* Reason picker */}
          <fieldset>
            <legend className="mb-2 text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Motif
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {reasons.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setReason(r.id)}
                  aria-pressed={reason === r.id}
                  className={[
                    'min-h-[48px] rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
                    reason === r.id
                      ? 'border-vz-teal bg-vz-teal-soft text-vz-teal-deep'
                      : 'border-vz-line bg-vz-surface text-vz-ink hover:bg-vz-bg-alt',
                  ].join(' ')}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </fieldset>

          {/* Amount */}
          <div>
            <span className="mb-2 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Montant
            </span>
            <NumPad value={amount} onChange={setAmount} presets={[20, 50, 100, 200]} />
            <div className="mt-2 rounded-xl bg-vz-teal-soft px-4 py-2 text-right">
              <span className="font-mono text-xl font-bold tabular-nums text-vz-teal-deep">
                {direction === 'out' ? '-' : '+'}
                {formatCurrency(amount)}
              </span>
            </div>
          </div>

          {/* Note */}
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-vz-ink-soft">
              Commentaire (optionnel)
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="Détail libre — référence facture, raison du retrait…"
              className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm text-vz-ink focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
            />
          </label>
        </div>
      </Modal>
    </>
  );
}
