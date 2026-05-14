'use client';

import React, { useState } from 'react';

import { formatCurrency } from '@/lib/format';

interface Props {
  ticketNumber: number;
  totalTtc: number;
  isInvoice?: boolean;
  invoiceNumber?: number | null;
  /** Pre-formatted ticket text (80mm width) — usually fetched from
   * ``GET /api/pos/transactions/{id}/receipt``. */
  receiptText: string;
  clientEmail?: string | null;
  clientPhone?: string | null;
  /** Print via the MUNBYN ESC/POS endpoint (recommended). */
  onPrintEscpos?: () => Promise<void> | void;
  /** Deprecated AirPrint fallback. Vintiz tourne désormais 100% sur
   * Android (Lenovo Idea Tab Pro Gen 2) où window.print() retombe sur
   * "Imprimer en PDF" — donc cette prop n'est plus rendue. Laissée dans
   * la signature pour compat appels existants. */
  onPrintAirprint?: () => void;
  /** Send the receipt by email/sms — falls through to
   * /transactions/:id/resend. ``to`` is the optional ad-hoc address (for
   * walk-in customers without a CRM record). */
  onResend?: (channel: 'email' | 'sms', to?: string) => Promise<void> | void;
  /** Download the B2B invoice PDF (only when isInvoice). */
  onDownloadInvoicePdf?: () => Promise<void> | void;
  onNewSale: () => void;
}

/**
 * "Vente validée" success card with the action grid.
 *
 * Boutons (priorité descendante) :
 *   Imprimer (MUNBYN ESC/POS) → Envoyer par email → Envoyer par SMS
 *   → Facture PDF (B2B) → Nouvelle vente.
 *
 * Les boutons email/SMS s'affichent toujours : si la fiche client n'a
 * pas d'adresse, on déplie un petit input pour saisir un destinataire
 * ad-hoc (cas walk-in « envoyez-moi le ticket par mail »).
 */
export default function ReceiptPreviewCard({
  ticketNumber,
  totalTtc,
  isInvoice,
  invoiceNumber,
  receiptText,
  clientEmail,
  clientPhone,
  onPrintEscpos,
  onResend,
  onDownloadInvoicePdf,
  onNewSale,
}: Props) {
  const [emailDraft, setEmailDraft] = useState(clientEmail ?? '');
  const [phoneDraft, setPhoneDraft] = useState(clientPhone ?? '');
  const [showEmailInput, setShowEmailInput] = useState(false);
  const [showSmsInput, setShowSmsInput] = useState(false);
  const [sending, setSending] = useState<'email' | 'sms' | null>(null);
  const [feedback, setFeedback] = useState<{ msg: string; ok: boolean } | null>(null);

  const handleResend = async (channel: 'email' | 'sms', to?: string) => {
    if (!onResend) return;
    setSending(channel);
    setFeedback(null);
    try {
      await onResend(channel, to);
      setFeedback({
        msg: channel === 'email'
          ? `Email envoyé à ${to || clientEmail}`
          : `SMS envoyé au ${to || clientPhone}`,
        ok: true,
      });
      setShowEmailInput(false);
      setShowSmsInput(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Échec de l'envoi";
      setFeedback({ msg, ok: false });
    } finally {
      setSending(null);
    }
  };

  const emailLooksValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailDraft.trim());
  const phoneLooksValid = /^\+?[\d\s().-]{6,}$/.test(phoneDraft.trim());

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-vz-teal-soft p-4 text-center">
        <div className="mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded-full bg-vz-teal text-white">
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M5 14l5 5 13-13" />
          </svg>
        </div>
        <div className="font-display text-xl font-semibold text-vz-teal-deep">
          Vente validée
        </div>
        <div className="mt-1 text-sm text-vz-ink-soft">
          {isInvoice && invoiceNumber
            ? `Facture FACT-${new Date().getFullYear()}-${String(
                invoiceNumber,
              ).padStart(6, '0')}`
            : `Ticket #${ticketNumber}`}{' '}
          · {formatCurrency(totalTtc)}
        </div>
      </div>

      <pre
        className="max-h-72 overflow-auto rounded-xl border border-vz-line bg-vz-bg-alt p-4 font-mono text-xs leading-tight text-vz-ink"
        aria-label="Aperçu du ticket"
      >
        {receiptText}
      </pre>

      {feedback && (
        <div
          role="status"
          className={`rounded-xl px-3 py-2 text-sm ${
            feedback.ok
              ? 'bg-green-50 text-green-700'
              : 'bg-red-50 text-red-700'
          }`}
        >
          {feedback.msg}
        </div>
      )}

      <div className="grid gap-2">
        {onPrintEscpos && (
          <button
            type="button"
            onClick={() => void onPrintEscpos()}
            className="min-h-[48px] rounded-xl bg-vz-teal px-4 py-3 text-base font-semibold text-white transition-colors hover:bg-vz-teal-deep"
          >
            Imprimer (MUNBYN)
          </button>
        )}

        {onResend && (
          <div className="space-y-2">
            {clientEmail && !showEmailInput ? (
              <button
                type="button"
                disabled={sending === 'email'}
                onClick={() => void handleResend('email')}
                className="w-full min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-50"
              >
                {sending === 'email' ? 'Envoi…' : `Envoyer par email (${clientEmail})`}
              </button>
            ) : showEmailInput ? (
              <div className="flex gap-2">
                <input
                  type="email"
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  placeholder="exemple@domaine.fr"
                  className="flex-1 min-h-[48px] px-3 py-2 rounded-lg border border-vz-line bg-vz-surface text-vz-ink"
                  autoFocus
                />
                <button
                  type="button"
                  disabled={!emailLooksValid || sending === 'email'}
                  onClick={() => void handleResend('email', emailDraft.trim())}
                  className="px-4 rounded-lg bg-vz-teal text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Envoyer
                </button>
                <button
                  type="button"
                  onClick={() => setShowEmailInput(false)}
                  className="px-3 text-vz-ink-mute"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowEmailInput(true)}
                className="w-full min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
              >
                Envoyer par email…
              </button>
            )}

            {clientPhone && !showSmsInput ? (
              <button
                type="button"
                disabled={sending === 'sms'}
                onClick={() => void handleResend('sms')}
                className="w-full min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-50"
              >
                {sending === 'sms' ? 'Envoi…' : `Envoyer par SMS (${clientPhone})`}
              </button>
            ) : showSmsInput ? (
              <div className="flex gap-2">
                <input
                  type="tel"
                  value={phoneDraft}
                  onChange={(e) => setPhoneDraft(e.target.value)}
                  placeholder="06 12 34 56 78"
                  className="flex-1 min-h-[48px] px-3 py-2 rounded-lg border border-vz-line bg-vz-surface text-vz-ink"
                  autoFocus
                />
                <button
                  type="button"
                  disabled={!phoneLooksValid || sending === 'sms'}
                  onClick={() => void handleResend('sms', phoneDraft.trim())}
                  className="px-4 rounded-lg bg-vz-teal text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Envoyer
                </button>
                <button
                  type="button"
                  onClick={() => setShowSmsInput(false)}
                  className="px-3 text-vz-ink-mute"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowSmsInput(true)}
                className="w-full min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
              >
                Envoyer par SMS…
              </button>
            )}
          </div>
        )}

        {isInvoice && onDownloadInvoicePdf && (
          <button
            type="button"
            onClick={() => void onDownloadInvoicePdf()}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
          >
            Télécharger la facture PDF
          </button>
        )}
        <button
          type="button"
          onClick={onNewSale}
          className="min-h-[48px] rounded-xl bg-vz-bg-alt px-4 py-3 text-base font-medium text-vz-ink-soft hover:bg-vz-line"
        >
          Nouvelle vente
        </button>
      </div>
    </div>
  );
}
