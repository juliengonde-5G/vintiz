'use client';

import React from 'react';

export type PosPaymentMethod = 'cash' | 'card' | 'cheque' | 'cheque_cdc' | 'avoir';

interface MethodConfig {
  id: PosPaymentMethod;
  label: string;
  hint?: string;
  icon: React.ReactNode;
}

interface Props {
  /** Methods to display. Order matters — keep the most-used first. */
  methods?: PosPaymentMethod[];
  /** Disable specific methods (e.g. avoir when no client is selected). */
  disabled?: Partial<Record<PosPaymentMethod, boolean>>;
  /** Hint surfaced under a disabled tile. */
  disabledReasons?: Partial<Record<PosPaymentMethod, string>>;
  onPick: (method: PosPaymentMethod) => void;
  /** Show the remaining-to-collect strip on top of the grid. */
  remainingAmount?: number;
  remainingLabel?: string;
}

const ICON_PROPS = {
  width: 48,
  height: 48,
  viewBox: '0 0 48 48',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const;

const METHODS: Record<PosPaymentMethod, MethodConfig> = {
  cash: {
    id: 'cash',
    label: 'Espèces',
    hint: 'Numpad + rendu monnaie',
    icon: (
      <svg {...ICON_PROPS} aria-hidden="true">
        <rect x="4" y="14" width="40" height="20" rx="2" />
        <circle cx="24" cy="24" r="5" />
        <path d="M11 18v-1M37 30v1" />
      </svg>
    ),
  },
  card: {
    id: 'card',
    label: 'Carte bancaire',
    hint: 'TPE SumUp Solo',
    icon: (
      <svg {...ICON_PROPS} aria-hidden="true">
        <rect x="4" y="10" width="40" height="28" rx="3" />
        <path d="M4 18h40" />
        <path d="M10 30h8M22 30h6" />
      </svg>
    ),
  },
  cheque: {
    id: 'cheque',
    label: 'Chèque',
    hint: 'Saisie libre',
    icon: (
      <svg {...ICON_PROPS} aria-hidden="true">
        <rect x="4" y="12" width="40" height="24" rx="2" />
        <path d="M9 19h12M9 24h22M9 29h12" />
        <path d="M30 27l3 3 6-6" />
      </svg>
    ),
  },
  cheque_cdc: {
    id: 'cheque_cdc',
    label: 'Chèque CDC',
    hint: 'Le Club des Commerçants',
    icon: (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src="/payment/cdc-logo.svg"
        alt=""
        aria-hidden="true"
        width={44}
        height={44}
        className="object-contain"
      />
    ),
  },
  avoir: {
    id: 'avoir',
    label: 'Avoir',
    hint: 'Solde client',
    icon: (
      <svg {...ICON_PROPS} aria-hidden="true">
        <path d="M42 24V14H10a4 4 0 0 1 0-8h28v8" />
        <path d="M6 10v28a4 4 0 0 0 4 4h32V32" />
        <path d="M36 24a4 4 0 0 0 0 8h8v-8Z" />
      </svg>
    ),
  },
};

/**
 * SumUp-style payment method picker.
 *
 * Renders a 2×2 grid of large 140×140 cards (icon + label) with the Sauge
 * Néo tokens. The wizard uses this both at "step 1" (full amount) and
 * after a partial payment ("complete with another method") so the layout
 * stays the same.
 */
export default function PaymentMethodSelector({
  methods = ['cash', 'card', 'cheque', 'cheque_cdc', 'avoir'],
  disabled = {},
  disabledReasons = {},
  onPick,
  remainingAmount,
  remainingLabel = 'Reste à encaisser',
}: Props) {
  return (
    <div className="space-y-4">
      {remainingAmount !== undefined && (
        <div className="flex items-center justify-between rounded-xl bg-vz-teal-soft px-4 py-3">
          <span className="text-sm font-medium text-vz-teal-deep">
            {remainingLabel}
          </span>
          <span className="font-mono text-2xl font-bold tabular-nums text-vz-teal-deep">
            {remainingAmount.toFixed(2)} €
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {methods.map((id) => {
          const cfg = METHODS[id];
          const isDisabled = !!disabled[id];
          const reason = disabledReasons[id];
          return (
            <button
              key={id}
              type="button"
              onClick={() => !isDisabled && onPick(id)}
              disabled={isDisabled}
              className={[
                'flex h-[140px] flex-col items-center justify-center gap-2 rounded-2xl border transition-all',
                'focus:outline-none focus:ring-2 focus:ring-vz-teal focus:ring-offset-2',
                isDisabled
                  ? 'cursor-not-allowed border-vz-line bg-vz-bg-alt opacity-60'
                  : 'border-vz-line bg-vz-bg-alt hover:bg-vz-teal-soft active:bg-vz-teal-soft active:scale-[0.98]',
              ].join(' ')}
              aria-label={cfg.label}
              aria-disabled={isDisabled}
            >
              <span
                className={
                  isDisabled
                    ? 'text-vz-ink-mute'
                    : 'text-vz-teal'
                }
              >
                {cfg.icon}
              </span>
              <span className="font-display text-base font-semibold text-vz-ink">
                {cfg.label}
              </span>
              {(isDisabled ? reason : cfg.hint) && (
                <span className="text-xs text-vz-ink-mute">
                  {isDisabled ? reason : cfg.hint}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
