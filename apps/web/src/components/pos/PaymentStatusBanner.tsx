'use client';

import React from 'react';

export type PaymentStatus =
  | 'pending'
  | 'paid'
  | 'failed'
  | 'cancelled'
  | 'timeout';

interface Props {
  status: PaymentStatus;
  /** Friendly label override — e.g. "Carte refusée" instead of "Échec". */
  label?: string;
  /** Extra detail shown under the label (error code, retry hint…). */
  detail?: string;
  /** Optional secondary action (cancel, retry) — surfaced as a small button. */
  actionLabel?: string;
  onAction?: () => void;
}

const PALETTE: Record<
  PaymentStatus,
  { bg: string; text: string; ring: string; defaultLabel: string }
> = {
  pending: {
    bg: 'bg-vz-bg-alt',
    text: 'text-vz-ink',
    ring: 'ring-vz-line',
    defaultLabel: 'En attente du terminal…',
  },
  paid: {
    bg: 'bg-vz-teal-soft',
    text: 'text-vz-teal-deep',
    ring: 'ring-vz-teal',
    defaultLabel: 'Paiement validé',
  },
  failed: {
    bg: 'bg-vz-accent-soft',
    text: 'text-vz-ink',
    ring: 'ring-vz-accent',
    defaultLabel: 'Paiement refusé',
  },
  cancelled: {
    bg: 'bg-vz-bg-alt',
    text: 'text-vz-ink-soft',
    ring: 'ring-vz-line',
    defaultLabel: 'Paiement annulé',
  },
  timeout: {
    bg: 'bg-vz-accent-soft',
    text: 'text-vz-ink',
    ring: 'ring-vz-accent',
    defaultLabel: 'Délai dépassé',
  },
};

/**
 * Status banner used inside the payment wizard while a CB checkout polls.
 *
 * Responsibilities are kept thin: render the current status + optional
 * detail and a small action button. The wizard owns the timer / polling
 * (``usePosPayment`` in PR6); failed status emissions can later be paired
 * with a ``PaymentAttempt`` log via the API.
 */
export default function PaymentStatusBanner({
  status,
  label,
  detail,
  actionLabel,
  onAction,
}: Props) {
  const palette = PALETTE[status];
  const showSpinner = status === 'pending';
  const showCheck = status === 'paid';
  return (
    <div
      role="status"
      aria-live="polite"
      className={[
        'rounded-2xl px-4 py-4 ring-1',
        palette.bg,
        palette.text,
        palette.ring,
      ].join(' ')}
    >
      <div className="flex items-center gap-3">
        {showSpinner && (
          <span
            aria-hidden="true"
            className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-vz-teal border-t-transparent"
          />
        )}
        {showCheck && (
          <svg
            aria-hidden="true"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 10l5 5 9-9" />
          </svg>
        )}
        <span className="font-semibold">{label || palette.defaultLabel}</span>
        {actionLabel && onAction && (
          <button
            type="button"
            onClick={onAction}
            className="ml-auto rounded-lg border border-current px-3 py-1.5 text-sm font-medium hover:bg-white/40"
          >
            {actionLabel}
          </button>
        )}
      </div>
      {detail && (
        <p className="mt-1 text-sm opacity-80">{detail}</p>
      )}
    </div>
  );
}
