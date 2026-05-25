'use client';

import React, { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import NumPad from '@/components/ui/NumPad';
import { formatCurrency } from '@/lib/format';

import type { PosPaymentMethod } from './PaymentMethodSelector';

interface Props {
  open: boolean;
  /** Closing should always be explicit (cancel button). Backdrop clicks
   * are blocked so the cashier can't lose a half-typed amount. */
  onClose: () => void;
  /** Selected payment method (drives the title + presets). */
  method: PosPaymentMethod;
  /** Amount remaining to collect — used to compute change for cash. */
  remainingAmount: number;
  /** Validate and forward the typed amount to the wizard. */
  onConfirm: (amount: number) => void;
  /** Optional preset bumpers (defaults to 5/10/20/50 + remaining). */
  presets?: number[];
}

const METHOD_LABEL: Record<PosPaymentMethod, string> = {
  cash: 'Espèces',
  card: 'Carte bancaire',
  cheque: 'Chèque',
  cheque_cdc: 'Chèque CDC',
  avoir: 'Avoir',
};

/**
 * Full-screen NumPad modal — wraps the existing ``NumPad`` primitive with
 * a header showing the payment method + amount to collect, and (for cash)
 * a live "Monnaie à rendre" strip below.
 *
 * ``closeOnBackdrop`` is forced false: a stray tap on the backdrop should
 * never wipe the typed amount.
 */
export default function NumPadModal({
  open,
  onClose,
  method,
  remainingAmount,
  onConfirm,
  presets,
}: Props) {
  const [amount, setAmount] = useState<number>(0);

  // Reset on open so a re-entry doesn't carry an old value
  useEffect(() => {
    if (open) {
      setAmount(method === 'card' ? remainingAmount : 0);
    }
  }, [open, method, remainingAmount]);

  const change = method === 'cash' ? amount - remainingAmount : 0;
  const isCovering = amount >= remainingAmount - 0.001;

  const defaultPresets = [
    remainingAmount,
    Math.ceil(remainingAmount / 5) * 5,
    Math.ceil(remainingAmount / 10) * 10,
    Math.ceil(remainingAmount / 20) * 20,
  ]
    .filter((n, i, arr) => n > 0 && arr.indexOf(n) === i)
    .slice(0, 4);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${METHOD_LABEL[method]} — ${formatCurrency(remainingAmount)}`}
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
            disabled={!isCovering}
            onClick={() => onConfirm(amount)}
            className="min-h-[48px] rounded-xl bg-vz-teal px-5 py-3 text-base font-semibold text-white transition-colors hover:bg-vz-teal-deep disabled:cursor-not-allowed disabled:opacity-50"
          >
            Valider
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <NumPad
          value={amount}
          onChange={setAmount}
          presets={presets ?? defaultPresets}
        />

        {method === 'cash' && amount > 0 && (
          <div
            className={[
              'rounded-xl px-4 py-3 transition-colors',
              isCovering ? 'bg-vz-teal-soft' : 'bg-vz-accent-soft',
            ].join(' ')}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-vz-ink-soft">
                {isCovering ? 'Monnaie à rendre' : 'Manque à encaisser'}
              </span>
              <span
                className={[
                  'font-mono text-2xl font-bold tabular-nums',
                  isCovering ? 'text-vz-teal-deep' : 'text-vz-ink',
                ].join(' ')}
              >
                {formatCurrency(Math.abs(change))}
              </span>
            </div>
          </div>
        )}

        {method !== 'cash' && amount > 0 && !isCovering && (
          <p className="rounded-xl bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink-soft">
            Le montant saisi est inférieur au reste à encaisser. Vérifie ou
            complète avec un autre moyen de paiement.
          </p>
        )}
      </div>
    </Modal>
  );
}
