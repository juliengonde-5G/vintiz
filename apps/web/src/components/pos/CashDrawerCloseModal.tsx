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
  /** Live expected total — preview computed from
   * ``GET /api/pos/drawer/current`` + cash-movements. The API recomputes
   * it on close, but showing the cashier the target while counting helps
   * catch mistakes early. */
  expectedAmount: number | null;
  /** Default tolerance from settings (CashManagementSettingsPanel). */
  defaultAllowedDiscrepancy: number;
  defaultDetailMode?: boolean;
  /** Submit handler — POST /drawer/close. Returns the Z-report number on
   * success so the parent can offer "Email du Z report" inline. */
  onSubmit: (payload: {
    closing_amount: number;
    closing_breakdown: DenominationLine[] | null;
    closing_note: string | null;
    allowed_discrepancy_override: number | null;
  }) => Promise<{ z_report_number: number } | void>;
}

type Phase = 'count' | 'compare' | 'done';

/**
 * Cash drawer close modal — 3-phase wizard:
 *
 *  1. **Décompte**       — denomination grid (or quick numpad) to count
 *  2. **Comparaison**    — counted vs expected, alert if |diff| > allowed
 *                          + mandatory note when over tolerance
 *  3. **Confirmation**   — submit, then prompt to email the Z report
 *
 * The grid / quick toggle persists across phases so the cashier can go
 * back and edit the count without losing entered values.
 */
export default function CashDrawerCloseModal({
  open,
  onClose,
  expectedAmount,
  defaultAllowedDiscrepancy,
  defaultDetailMode = true,
  onSubmit,
}: Props) {
  const [phase, setPhase] = useState<Phase>('count');
  const [detailMode, setDetailMode] = useState<boolean>(defaultDetailMode);
  const [breakdown, setBreakdown] = useState<DenominationLine[]>([]);
  const [quickAmount, setQuickAmount] = useState<number>(0);
  const [closingNote, setClosingNote] = useState<string>('');
  const [allowedOverride, setAllowedOverride] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [zReportNumber, setZReportNumber] = useState<number | null>(null);

  const counted = detailMode ? totalFromBreakdown(breakdown) : quickAmount;
  const expected = expectedAmount ?? 0;
  const discrepancy = counted - expected;
  const allowed = allowedOverride ?? defaultAllowedDiscrepancy;
  const overTolerance = Math.abs(discrepancy) > allowed;
  const noteRequired = overTolerance;

  const handleClose = (): void => {
    if (submitting) return;
    setPhase('count');
    setBreakdown([]);
    setQuickAmount(0);
    setClosingNote('');
    setAllowedOverride(null);
    setZReportNumber(null);
    onClose();
  };

  const handleNext = (): void => {
    if (phase === 'count') {
      setPhase('compare');
    } else if (phase === 'compare') {
      void handleSubmit();
    }
  };

  const handleSubmit = async (): Promise<void> => {
    if (noteRequired && !closingNote.trim()) return;
    setSubmitting(true);
    try {
      const result = await onSubmit({
        closing_amount: counted,
        closing_breakdown: detailMode ? breakdown : null,
        closing_note: closingNote.trim() || null,
        allowed_discrepancy_override: allowedOverride,
      });
      if (result && 'z_report_number' in result) {
        setZReportNumber(result.z_report_number);
      }
      setPhase('done');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      closeOnBackdrop={false}
      title={
        phase === 'count'
          ? 'Clôturer la caisse — décompte'
          : phase === 'compare'
            ? 'Clôturer la caisse — comparaison'
            : 'Caisse clôturée'
      }
      actions={
        <>
          <button
            type="button"
            onClick={() => {
              if (phase === 'compare') setPhase('count');
              else handleClose();
            }}
            disabled={submitting}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-5 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-60"
          >
            {phase === 'compare' ? 'Modifier' : 'Annuler'}
          </button>
          {phase !== 'done' && (
            <button
              type="button"
              disabled={
                submitting ||
                counted <= 0 ||
                (phase === 'compare' && noteRequired && !closingNote.trim())
              }
              onClick={handleNext}
              className="min-h-[48px] rounded-xl bg-vz-teal px-5 py-3 text-base font-semibold text-white transition-colors hover:bg-vz-teal-deep disabled:opacity-60"
            >
              {phase === 'count'
                ? 'Continuer'
                : submitting
                  ? 'Clôture…'
                  : 'Clôturer'}
            </button>
          )}
          {phase === 'done' && (
            <button
              type="button"
              onClick={handleClose}
              className="min-h-[48px] rounded-xl bg-vz-teal px-5 py-3 text-base font-semibold text-white hover:bg-vz-teal-deep"
            >
              Terminer
            </button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {/* Phase indicator */}
        <div className="flex items-center justify-center gap-2">
          {(['count', 'compare', 'done'] as const).map((p) => (
            <span
              key={p}
              className={[
                'h-2 w-2 rounded-full transition-colors',
                p === phase ? 'bg-vz-teal' : 'bg-vz-line',
              ].join(' ')}
              aria-hidden="true"
            />
          ))}
        </div>

        {phase === 'count' && (
          <>
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
                Détail
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
                Rapide
              </button>
            </div>

            {detailMode ? (
              <DenominationGrid
                value={breakdown}
                onChange={setBreakdown}
              />
            ) : (
              <>
                <NumPad value={quickAmount} onChange={setQuickAmount} />
                <div className="rounded-xl bg-vz-teal-soft px-4 py-3 text-right">
                  <span className="font-mono text-2xl font-bold tabular-nums text-vz-teal-deep">
                    {formatCurrency(quickAmount)}
                  </span>
                </div>
              </>
            )}
          </>
        )}

        {phase === 'compare' && (
          <>
            <div className="grid gap-2">
              <SummaryRow
                label="Attendu en caisse"
                value={expected}
                muted
              />
              <SummaryRow label="Compté" value={counted} />
              <SummaryRow
                label="Écart"
                value={discrepancy}
                signed
                tone={overTolerance ? 'alert' : 'ok'}
              />
            </div>

            <div className="rounded-xl bg-vz-bg-alt p-3 text-xs text-vz-ink-soft">
              Tolérance autorisée :{' '}
              <span className="font-mono">{formatCurrency(allowed)}</span>
              <button
                type="button"
                onClick={() => {
                  const next = window.prompt(
                    'Nouvelle tolérance autorisée (€) :',
                    String(allowed),
                  );
                  if (next === null) return;
                  const parsed = parseFloat(next.replace(',', '.'));
                  if (!Number.isNaN(parsed) && parsed >= 0) {
                    setAllowedOverride(parsed);
                  }
                }}
                className="ml-2 text-vz-teal underline"
              >
                Modifier (manager)
              </button>
            </div>

            {overTolerance && (
              <div className="rounded-xl bg-vz-accent-soft p-3">
                <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-vz-ink">
                  <span aria-hidden="true">⚠</span> Écart hors tolérance
                </div>
                <p className="text-xs text-vz-ink-soft">
                  Une note est obligatoire pour valider la clôture (NF525).
                </p>
              </div>
            )}

            <label className="block">
              <span className="mb-1 block text-xs font-medium text-vz-ink-soft">
                Commentaire de clôture
                {noteRequired && <span className="ml-1 text-vz-accent">*</span>}
              </span>
              <textarea
                value={closingNote}
                onChange={(e) => setClosingNote(e.target.value)}
                rows={3}
                placeholder="Précise la cause de l'écart si nécessaire."
                className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm text-vz-ink focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
              />
            </label>
          </>
        )}

        {phase === 'done' && (
          <div className="rounded-xl bg-vz-teal-soft p-4 text-center">
            <div className="font-display text-lg font-semibold text-vz-teal-deep">
              Caisse clôturée
            </div>
            <p className="mt-2 text-sm text-vz-ink-soft">
              {zReportNumber !== null
                ? `Rapport Z #${zReportNumber} généré.`
                : 'Rapport Z généré.'}{' '}
              Tu peux le télécharger depuis le panneau /admin/z-reports puis
              le verrouiller (NF525) une fois validé.
            </p>
          </div>
        )}
      </div>
    </Modal>
  );
}

interface SummaryRowProps {
  label: string;
  value: number;
  signed?: boolean;
  muted?: boolean;
  tone?: 'ok' | 'alert' | 'neutral';
}

function SummaryRow({ label, value, signed, muted, tone = 'neutral' }: SummaryRowProps) {
  const toneClass =
    tone === 'alert'
      ? 'text-vz-accent'
      : tone === 'ok'
        ? 'text-vz-teal-deep'
        : 'text-vz-ink';
  const sign = signed && value > 0 ? '+' : '';
  return (
    <div
      className={[
        'flex items-center justify-between rounded-xl px-4 py-3',
        muted ? 'bg-vz-bg-alt' : 'bg-vz-surface border border-vz-line',
      ].join(' ')}
    >
      <span className="text-sm font-medium text-vz-ink-soft">{label}</span>
      <span
        className={['font-mono text-xl font-bold tabular-nums', toneClass].join(
          ' ',
        )}
      >
        {sign}
        {formatCurrency(value)}
      </span>
    </div>
  );
}
