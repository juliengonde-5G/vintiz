'use client';

import React, { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { formatCurrency } from '@/lib/format';

import NumPadModal from './NumPadModal';
import PaymentMethodSelector, {
  type PosPaymentMethod,
} from './PaymentMethodSelector';
import PaymentStatusBanner, {
  type PaymentStatus,
} from './PaymentStatusBanner';

interface Tendered {
  method: PosPaymentMethod;
  amount: number;
}

interface Props {
  open: boolean;
  /** Total to collect (TTC, after discounts + coupon). */
  totalTtc: number;
  /** Whether the cart selected a client (gates the avoir method). */
  hasClient: boolean;
  /** Live remaining avoir balance for the selected client (gates avoir). */
  avoirBalance?: number;
  /** Cancel the entire wizard — wipes local tenders, doesn't commit. */
  onClose: () => void;
  /** Called when the cashier confirms — array of tenders summing to total. */
  onCommit: (tenders: Tendered[]) => Promise<void> | void;
  /** Polling-aware bridge for CB checkouts. The wizard transitions through
   * pending → paid/failed using the status returned here. */
  onCardCheckout?: (
    amount: number,
    onStatus: (s: PaymentStatus, detail?: string) => void,
  ) => Promise<{ status: PaymentStatus; detail?: string }>;
}

type Step =
  | { kind: 'select' }
  | { kind: 'amount'; method: PosPaymentMethod }
  | {
      kind: 'card-pending';
      amount: number;
      status: PaymentStatus;
      detail?: string;
    }
  | { kind: 'confirm' };

/**
 * Orchestrator for the SumUp-style payment flow.
 *
 * State machine:
 *   select  → amount  → confirm   (cash / cheque / avoir)
 *   select  → card-pending → confirm   (CB via SumUp polling)
 *   confirm → select         (split: still some left to collect)
 *
 * The wizard owns the state of the wizard itself — tenders, current step,
 * card status. It does NOT commit the transaction; the parent receives the
 * tenders and is responsible for sending ``CreateTransactionRequest`` and
 * showing the ``ReceiptPreviewCard``.
 */
export default function MultiStepPaymentWizard({
  open,
  totalTtc,
  hasClient,
  avoirBalance,
  onClose,
  onCommit,
  onCardCheckout,
}: Props) {
  const [tenders, setTenders] = useState<Tendered[]>([]);
  const [step, setStep] = useState<Step>({ kind: 'select' });
  const [committing, setCommitting] = useState(false);

  // Reset when the modal closes so the next open starts clean.
  const handleClose = (): void => {
    setTenders([]);
    setStep({ kind: 'select' });
    setCommitting(false);
    onClose();
  };

  // Tenders may exceed the total when the cashier overpays in cash —
  // the surplus becomes change to give back. We split each tender into
  // ``cover`` (counted toward the total) and ``surplus`` (change).
  const totalTendered = tenders.reduce((sum, t) => sum + t.amount, 0);
  let runningCovered = 0;
  for (const t of tenders) {
    const stillDue = Math.max(0, totalTtc - runningCovered);
    runningCovered += Math.min(t.amount, stillDue);
  }
  const collected = runningCovered;
  const remaining = Math.max(0, totalTtc - collected);
  const change = Math.max(0, totalTendered - totalTtc);

  const handlePickMethod = async (method: PosPaymentMethod): Promise<void> => {
    if (method === 'card' && onCardCheckout) {
      // CB jumps straight to the polling banner — the amount equals the
      // remaining (TPE doesn't accept partial-on-the-fly).
      setStep({ kind: 'card-pending', amount: remaining, status: 'pending' });
      const final = await onCardCheckout(remaining, (s, detail) =>
        setStep({ kind: 'card-pending', amount: remaining, status: s, detail }),
      );
      setStep({
        kind: 'card-pending',
        amount: remaining,
        status: final.status,
        detail: final.detail,
      });
      if (final.status === 'paid') {
        const next = [...tenders, { method: 'card' as const, amount: remaining }];
        setTenders(next);
        if (next.reduce((s, t) => s + t.amount, 0) >= totalTtc - 0.001) {
          setStep({ kind: 'confirm' });
        } else {
          setStep({ kind: 'select' });
        }
      }
      return;
    }
    setStep({ kind: 'amount', method });
  };

  const handleAmountConfirmed = (amount: number): void => {
    if (step.kind !== 'amount') return;
    // Cash allows overpayment (the surplus is returned as change to the
    // client, and the receipt prints "RENDU: X €"). Other methods are
    // capped at the remaining due — chèque / avoir don't make change.
    const tendered =
      step.method === 'cash' ? amount : Math.min(amount, remaining);
    const next = [...tenders, { method: step.method, amount: tendered }];
    setTenders(next);
    // Coverage is what counts toward "remaining = 0"; for cash the surplus
    // doesn't, but the sale is still complete since cash >= remaining.
    let cover = 0;
    for (const t of next) {
      const stillDue = Math.max(0, totalTtc - cover);
      cover += Math.min(t.amount, stillDue);
    }
    if (cover >= totalTtc - 0.001) {
      setStep({ kind: 'confirm' });
    } else {
      setStep({ kind: 'select' });
    }
  };

  const handleCommit = async (): Promise<void> => {
    setCommitting(true);
    try {
      await onCommit(tenders);
      handleClose();
    } finally {
      setCommitting(false);
    }
  };

  const handleRemoveTender = (index: number): void => {
    setTenders((prev) => prev.filter((_, i) => i !== index));
    if (step.kind === 'confirm') setStep({ kind: 'select' });
  };

  // ----- Step renderers ---------------------------------------------------

  if (step.kind === 'amount') {
    return (
      <NumPadModal
        open={open}
        onClose={() => setStep({ kind: 'select' })}
        method={step.method}
        remainingAmount={remaining}
        onConfirm={handleAmountConfirmed}
      />
    );
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      closeOnBackdrop={false}
      title={
        step.kind === 'card-pending' && step.status === 'pending'
          ? 'Paiement en cours…'
          : step.kind === 'confirm'
            ? 'Confirmer la vente'
            : `Encaisser ${formatCurrency(totalTtc)}`
      }
      actions={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-5 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
            disabled={
              committing ||
              (step.kind === 'card-pending' && step.status === 'pending')
            }
          >
            Annuler
          </button>
          {step.kind === 'confirm' && (
            <button
              type="button"
              onClick={() => void handleCommit()}
              disabled={committing}
              className="min-h-[48px] rounded-xl bg-vz-teal px-5 py-3 text-base font-semibold text-white transition-colors hover:bg-vz-teal-deep disabled:opacity-60"
            >
              {committing ? 'Enregistrement…' : 'Valider la vente'}
            </button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {/* Progress indicator — 3 dots */}
        <div className="flex items-center justify-center gap-2">
          {(['select', 'amount/card', 'confirm'] as const).map((slot, i) => {
            const active =
              (slot === 'select' && step.kind === 'select') ||
              (slot === 'amount/card' &&
                (step.kind === 'amount' || step.kind === 'card-pending')) ||
              (slot === 'confirm' && step.kind === 'confirm');
            return (
              <span
                key={i}
                className={[
                  'h-2 w-2 rounded-full transition-colors',
                  active ? 'bg-vz-teal' : 'bg-vz-line',
                ].join(' ')}
                aria-hidden="true"
              />
            );
          })}
        </div>

        {step.kind === 'select' && (
          <PaymentMethodSelector
            remainingAmount={remaining}
            disabled={{
              avoir:
                !hasClient ||
                (avoirBalance !== undefined && avoirBalance < remaining - 0.001),
            }}
            disabledReasons={{
              avoir: !hasClient
                ? 'Sélectionne un client'
                : 'Solde insuffisant',
            }}
            onPick={(m) => void handlePickMethod(m)}
          />
        )}

        {step.kind === 'card-pending' && (
          <div className="space-y-3">
            <PaymentStatusBanner
              status={step.status}
              detail={step.detail}
            />
            {step.status === 'failed' || step.status === 'timeout' ? (
              <button
                type="button"
                onClick={() => setStep({ kind: 'select' })}
                className="min-h-[48px] w-full rounded-xl bg-vz-teal px-4 py-3 text-base font-semibold text-white hover:bg-vz-teal-deep"
              >
                Choisir un autre moyen
              </button>
            ) : null}
          </div>
        )}

        {step.kind === 'confirm' && (
          <div className="space-y-3">
            <p className="text-sm text-vz-ink-soft">
              Vérifie le détail des paiements puis valide. La transaction
              sera signée NF525 et le ticket pourra être imprimé.
            </p>
            <div className="rounded-xl border border-vz-line bg-vz-surface">
              {tenders.map((t, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b border-vz-line px-4 py-3 last:border-b-0"
                >
                  <span className="text-sm font-medium text-vz-ink">
                    {labelFor(t.method)}
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-base font-semibold tabular-nums text-vz-ink">
                      {formatCurrency(t.amount)}
                    </span>
                    {!committing && (
                      <button
                        type="button"
                        onClick={() => handleRemoveTender(i)}
                        className="text-xs text-vz-accent hover:underline"
                      >
                        Retirer
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between rounded-xl bg-vz-teal-soft px-4 py-3">
              <span className="text-sm font-medium text-vz-teal-deep">
                Total encaissé
              </span>
              <span className="font-mono text-2xl font-bold tabular-nums text-vz-teal-deep">
                {formatCurrency(collected)}
              </span>
            </div>
            {change > 0 && (
              <div className="flex items-center justify-between rounded-xl bg-vz-accent-soft px-4 py-4 ring-2 ring-vz-accent">
                <span className="text-base font-semibold text-vz-ink">
                  Monnaie à rendre
                </span>
                <span className="font-mono text-3xl font-bold tabular-nums text-vz-ink">
                  {formatCurrency(change)}
                </span>
              </div>
            )}
          </div>
        )}

        {tenders.length > 0 && step.kind === 'select' && (
          <div className="rounded-xl bg-vz-bg-alt p-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Déjà encaissé
            </div>
            <ul className="space-y-1 text-sm">
              {tenders.map((t, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between"
                >
                  <span>{labelFor(t.method)}</span>
                  <span className="font-mono tabular-nums">
                    {formatCurrency(t.amount)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  );
}

function labelFor(m: PosPaymentMethod): string {
  return {
    cash: 'Espèces',
    card: 'Carte bancaire',
    cheque: 'Chèque',
    avoir: 'Avoir',
  }[m];
}
