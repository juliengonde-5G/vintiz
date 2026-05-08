'use client';

import React from 'react';

export interface InvoiceFields {
  is_invoice: boolean;
  client_company_name: string;
  client_siret: string;
  client_billing_address: string;
}

interface Props {
  value: InvoiceFields;
  onChange: (next: InvoiceFields) => void;
  /** When false, the toggle row is hidden (e.g. the wizard already opens
   * with invoice mode forced on). */
  showToggle?: boolean;
  /** Compact mode — used inside the wizard side-panel. */
  compact?: boolean;
}

const SIRET_REGEX = /^\d{14}$/;

export function isInvoiceFormValid(v: InvoiceFields): boolean {
  if (!v.is_invoice) return true;
  return (
    v.client_company_name.trim().length > 0 &&
    SIRET_REGEX.test(v.client_siret.replace(/\s+/g, '')) &&
    v.client_billing_address.trim().length > 0
  );
}

/**
 * B2B invoice toggle + buyer block (raison sociale, SIRET, adresse).
 *
 * Lives in the POS panel (left column) and inside the wizard when the
 * cashier ticks "Émettre une facture". The validation matches
 * ``PosService.create_transaction`` server-side: 14-digit SIRET,
 * non-empty company + address.
 *
 * The component is pure — the parent owns the state; PR 6 wires it into
 * the ``CreateTransactionRequest`` body sent at commit time.
 */
export default function InvoiceClientForm({
  value,
  onChange,
  showToggle = true,
  compact = false,
}: Props) {
  const set = (patch: Partial<InvoiceFields>): void =>
    onChange({ ...value, ...patch });

  const siretClean = value.client_siret.replace(/\s+/g, '');
  const siretInvalid =
    value.is_invoice &&
    siretClean.length > 0 &&
    !SIRET_REGEX.test(siretClean);

  return (
    <div className={compact ? 'space-y-2' : 'space-y-3'}>
      {showToggle && (
        <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-vz-line bg-vz-surface px-3 py-3 hover:bg-vz-bg-alt">
          <input
            type="checkbox"
            checked={value.is_invoice}
            onChange={(e) => set({ is_invoice: e.target.checked })}
            className="h-5 w-5 accent-vz-teal"
          />
          <div className="flex-1">
            <div className="text-sm font-semibold text-vz-ink">
              Émettre une facture (B2B)
            </div>
            <div className="text-xs text-vz-ink-mute">
              Numéro FACT-AAAA-NNNNNN, raison sociale et SIRET sur le ticket.
            </div>
          </div>
        </label>
      )}

      {value.is_invoice && (
        <div className="space-y-3 rounded-xl border border-vz-line bg-vz-bg-alt p-3">
          <Field
            label="Raison sociale"
            value={value.client_company_name}
            onChange={(s) => set({ client_company_name: s })}
            placeholder="ACME SARL"
            required
          />
          <Field
            label="SIRET (14 chiffres)"
            value={value.client_siret}
            onChange={(s) => set({ client_siret: s.replace(/[^0-9 ]/g, '') })}
            placeholder="123 456 789 01234"
            inputMode="numeric"
            error={
              siretInvalid
                ? 'Le SIRET doit contenir exactement 14 chiffres.'
                : undefined
            }
            required
          />
          <Field
            label="Adresse de facturation"
            value={value.client_billing_address}
            onChange={(s) => set({ client_billing_address: s })}
            placeholder={'1 rue Lafayette\n75009 Paris'}
            required
            multiline
          />
        </div>
      )}
    </div>
  );
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  multiline?: boolean;
  inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode'];
  error?: string;
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
  multiline,
  inputMode,
  error,
}: FieldProps) {
  const baseClass =
    'w-full rounded-lg border bg-vz-surface px-3 py-2 text-base text-vz-ink focus:outline-none focus:ring-1 ' +
    (error
      ? 'border-vz-accent focus:border-vz-accent focus:ring-vz-accent'
      : 'border-vz-line focus:border-vz-teal focus:ring-vz-teal');
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-vz-ink-soft">
        {label}
        {required && <span className="ml-1 text-vz-accent">*</span>}
      </span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={3}
          className={baseClass + ' min-h-[80px] resize-y'}
        />
      ) : (
        <input
          type="text"
          inputMode={inputMode}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={baseClass}
        />
      )}
      {error && <p className="mt-1 text-xs text-vz-accent">{error}</p>}
    </label>
  );
}
