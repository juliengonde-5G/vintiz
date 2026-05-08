'use client';

import React from 'react';

import { formatCurrency } from '@/lib/format';
import { isIOS } from '@/lib/platform';

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
  /** Fallback AirPrint via window.print (iOS / Android print services). */
  onPrintAirprint?: () => void;
  /** Send the receipt by email/sms — falls through to /transactions/:id/resend. */
  onResend?: (channel: 'email' | 'sms') => Promise<void> | void;
  /** Download the B2B invoice PDF (only when isInvoice). */
  onDownloadInvoicePdf?: () => Promise<void> | void;
  onNewSale: () => void;
}

/**
 * "Vente validée" success card with the action grid.
 *
 * Displayed full-screen by the wizard after the transaction is signed
 * server-side. Buttons are deliberately big (44–48 px tap targets) and
 * layered top-to-bottom in priority order: Imprimer → Email → AirPrint →
 * Facture PDF (if applicable) → Nouvelle vente (secondary at the bottom).
 *
 * The AirPrint button is conditional on iOS/iPad (per ``isIOS()``) since
 * Android print services have proven flaky on the Lenovo dock.
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
  onPrintAirprint,
  onResend,
  onDownloadInvoicePdf,
  onNewSale,
}: Props) {
  const showAirprint = typeof window !== 'undefined' && isIOS();

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
        {onResend && clientEmail && (
          <button
            type="button"
            onClick={() => void onResend('email')}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
          >
            Envoyer par email ({clientEmail})
          </button>
        )}
        {onResend && clientPhone && (
          <button
            type="button"
            onClick={() => void onResend('sms')}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
          >
            Envoyer par SMS ({clientPhone})
          </button>
        )}
        {showAirprint && onPrintAirprint && (
          <button
            type="button"
            onClick={onPrintAirprint}
            className="min-h-[48px] rounded-xl border border-vz-line bg-vz-surface px-4 py-3 text-base font-medium text-vz-ink hover:bg-vz-bg-alt"
          >
            Imprimer (AirPrint)
          </button>
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
