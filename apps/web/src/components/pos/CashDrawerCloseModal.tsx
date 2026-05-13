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
 * Cash drawer close — Odoo 17 fullscreen wizard. 3 phases :
 *
 *  1. **Décompte**       — denomination grid (or quick numpad) to count
 *  2. **Comparaison**    — counted vs expected, alert if |diff| > allowed
 *                          + mandatory note when over tolerance
 *  3. **Confirmation**   — submit, then prompt to email the Z report
 *
 * Phase state persists across navigations so the cashier can return to
 * count after compare without losing entered values.
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

  if (!open) return null;

  const phaseLabel =
    phase === 'count'
      ? 'Décompte'
      : phase === 'compare'
        ? 'Comparaison'
        : 'Caisse clôturée';

  return (
    <div className="fixed inset-0 z-[58] bg-vz-bg flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg">
        <button
          onClick={() => {
            if (submitting) return;
            if (phase === 'compare') setPhase('count');
            else handleClose();
          }}
          disabled={submitting || phase === 'done'}
          className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px] disabled:opacity-30"
          aria-label={phase === 'compare' ? 'Modifier le décompte' : 'Annuler'}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span className="text-sm font-medium">
            {phase === 'compare' ? 'Modifier' : 'Retour'}
          </span>
        </button>
        <div className="h-7 w-px bg-white/15" />
        <h1 className="font-display text-lg">Clôture de caisse</h1>
        <span className="text-xs opacity-70 px-2 py-1 rounded bg-white/10">{phaseLabel}</span>

        {/* Phase indicator */}
        <div className="hidden md:flex items-center gap-2 ml-3">
          {(['count', 'compare', 'done'] as const).map((p, idx) => {
            const active = p === phase;
            const done =
              (phase === 'compare' && p === 'count') ||
              (phase === 'done' && p !== 'done');
            return (
              <React.Fragment key={p}>
                <span
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                    active
                      ? 'bg-vz-accent text-white shadow-lg'
                      : done
                        ? 'bg-white/30 text-white'
                        : 'bg-white/10 text-white/40'
                  }`}
                  aria-current={active ? 'step' : undefined}
                >
                  {done && !active ? '✓' : idx + 1}
                </span>
                {idx < 2 && <span className="w-6 h-px bg-white/15" />}
              </React.Fragment>
            );
          })}
        </div>

        <div className="flex-1" />

        {/* Counted preview always visible */}
        <div className="flex flex-col items-end leading-tight">
          <span className="text-[10px] opacity-70 uppercase tracking-wider">Compté</span>
          <span className="font-display text-2xl font-bold font-mono">{formatCurrency(counted)}</span>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {phase === 'count' && (
          <>
            {/* LEFT — mode + running totals */}
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
                {detailMode
                  ? "Compte les espèces par dénomination. Le détail est conservé pour le Z report (NF525) et la réconciliation."
                  : "Saisis directement le total compté. Plus rapide, mais sans détail dans le Z report."}
              </section>

              {/* Live recap */}
              <section className="mt-auto space-y-2">
                <div className="p-3 bg-vz-bg-alt rounded-xl flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-vz-ink-mute">Attendu</span>
                  <span className="font-mono text-base font-semibold text-vz-ink tabular-nums">
                    {formatCurrency(expected)}
                  </span>
                </div>
                <div className="p-3 bg-vz-teal-soft rounded-xl flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-vz-teal-deep">Compté</span>
                  <span className="font-mono text-2xl font-bold text-vz-teal-deep tabular-nums">
                    {formatCurrency(counted)}
                  </span>
                </div>
                {counted > 0 && (
                  <div
                    className={`p-3 rounded-xl flex items-center justify-between ${
                      Math.abs(discrepancy) > allowed
                        ? 'bg-vz-accent-soft'
                        : 'bg-green-50'
                    }`}
                  >
                    <span
                      className={`text-xs uppercase tracking-wider ${
                        Math.abs(discrepancy) > allowed ? 'text-vz-accent' : 'text-green-700'
                      }`}
                    >
                      Écart
                    </span>
                    <span
                      className={`font-mono text-base font-bold tabular-nums ${
                        Math.abs(discrepancy) > allowed ? 'text-vz-accent' : 'text-green-700'
                      }`}
                    >
                      {discrepancy > 0 ? '+' : ''}
                      {formatCurrency(discrepancy)}
                    </span>
                  </div>
                )}
              </section>
            </div>

            {/* RIGHT — input */}
            <div className="flex-1 overflow-y-auto bg-vz-bg p-5">
              {detailMode ? (
                <DenominationGrid value={breakdown} onChange={setBreakdown} />
              ) : (
                <div className="max-w-md mx-auto">
                  <NumPad value={quickAmount} onChange={setQuickAmount} />
                </div>
              )}
            </div>
          </>
        )}

        {phase === 'compare' && (
          <div className="flex-1 overflow-y-auto p-5 md:p-8 bg-vz-bg">
            <div className="max-w-3xl mx-auto space-y-4">
              <section className="bg-white rounded-2xl border border-vz-line p-5">
                <h2 className="font-display text-lg text-vz-ink mb-4">Comparaison</h2>
                <div className="grid gap-2">
                  <SummaryRow label="Attendu en caisse" value={expected} muted />
                  <SummaryRow label="Compté" value={counted} />
                  <SummaryRow
                    label="Écart"
                    value={discrepancy}
                    signed
                    tone={overTolerance ? 'alert' : 'ok'}
                  />
                </div>
              </section>

              <section className="bg-white rounded-xl border border-vz-line p-3 text-xs text-vz-ink-soft flex items-center justify-between">
                <span>
                  Tolérance autorisée :{' '}
                  <span className="font-mono font-semibold text-vz-ink">{formatCurrency(allowed)}</span>
                </span>
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
                  className="text-vz-teal hover:text-vz-teal-deep underline text-xs"
                >
                  Modifier (manager)
                </button>
              </section>

              {overTolerance && (
                <section className="rounded-xl bg-vz-accent-soft border border-vz-accent/40 p-4">
                  <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-vz-ink">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-vz-accent">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                      <line x1="12" y1="9" x2="12" y2="13"/>
                      <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    Écart hors tolérance
                  </div>
                  <p className="text-xs text-vz-ink-soft">
                    Une note est obligatoire pour valider la clôture (NF525).
                  </p>
                </section>
              )}

              <section className="bg-white rounded-xl border border-vz-line p-4">
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-vz-ink">
                    Commentaire de clôture
                    {noteRequired && <span className="ml-1 text-vz-accent">*</span>}
                  </span>
                  <textarea
                    value={closingNote}
                    onChange={(e) => setClosingNote(e.target.value)}
                    rows={4}
                    placeholder="Précise la cause de l'écart si nécessaire."
                    className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2.5 text-sm text-vz-ink focus:border-vz-teal focus:outline-none focus:ring-2 focus:ring-vz-teal"
                  />
                </label>
              </section>
            </div>
          </div>
        )}

        {phase === 'done' && (
          <div className="flex-1 flex items-center justify-center bg-vz-bg p-6">
            <div className="max-w-lg w-full bg-white rounded-2xl border border-vz-line shadow-lg p-8 text-center">
              <div className="mx-auto w-20 h-20 rounded-full bg-vz-teal-soft flex items-center justify-center mb-5">
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-vz-teal-deep">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <h2 className="font-display text-2xl text-vz-ink mb-2">Caisse clôturée</h2>
              <p className="text-sm text-vz-ink-soft">
                {zReportNumber !== null
                  ? `Rapport Z #${zReportNumber} généré.`
                  : 'Rapport Z généré.'}{' '}
                Tu peux le télécharger depuis <code className="text-xs px-1 py-0.5 rounded bg-vz-bg-alt">/admin/z-reports</code> puis le verrouiller (NF525) une fois validé.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Bottom action bar */}
      <footer className="flex-shrink-0 bg-white border-t border-vz-line px-4 md:px-6 py-3 flex items-center gap-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
        {phase !== 'done' ? (
          <>
            <button
              type="button"
              onClick={() => {
                if (phase === 'compare') setPhase('count');
                else handleClose();
              }}
              disabled={submitting}
              className="px-5 py-3 rounded-xl text-sm font-medium text-vz-ink-soft bg-vz-bg-alt hover:bg-vz-line transition-colors min-h-[52px] disabled:opacity-50"
            >
              {phase === 'compare' ? 'Modifier le décompte' : 'Annuler'}
            </button>
            <button
              type="button"
              disabled={
                submitting ||
                counted <= 0 ||
                (phase === 'compare' && noteRequired && !closingNote.trim())
              }
              onClick={handleNext}
              className={`flex-1 py-3 rounded-xl text-lg font-bold transition-colors min-h-[52px] flex items-center justify-center gap-3 ${
                submitting ||
                counted <= 0 ||
                (phase === 'compare' && noteRequired && !closingNote.trim())
                  ? 'bg-vz-line text-vz-ink-mute cursor-not-allowed'
                  : 'bg-vz-teal text-white hover:bg-vz-teal-deep active:bg-vz-teal-deep shadow-lg'
              }`}
            >
              {submitting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Clôture…
                </>
              ) : phase === 'count' ? (
                <>
                  Continuer
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </>
              ) : (
                <>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Clôturer — {formatCurrency(counted)}
                </>
              )}
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={handleClose}
            className="flex-1 py-3 rounded-xl text-lg font-bold bg-vz-teal text-white hover:bg-vz-teal-deep transition-colors min-h-[52px] shadow-lg"
          >
            Terminer
          </button>
        )}
      </footer>
    </div>
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
      className={`flex items-center justify-between rounded-xl px-4 py-3 ${
        muted ? 'bg-vz-bg-alt' : 'bg-vz-surface border border-vz-line'
      }`}
    >
      <span className="text-sm font-medium text-vz-ink-soft">{label}</span>
      <span className={`font-mono text-xl font-bold tabular-nums ${toneClass}`}>
        {sign}
        {formatCurrency(value)}
      </span>
    </div>
  );
}
