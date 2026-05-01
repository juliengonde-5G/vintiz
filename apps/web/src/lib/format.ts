/**
 * Display formatting helpers — single source of truth for the back-office UI.
 *
 * Replaces the 13 ad-hoc ``formatCurrency`` definitions that drifted across
 * pages (`` €`` vs `` €``, ``toFixed(0)`` vs ``toFixed(2)``,
 * thousands separator on/off…). Co-locates the rule with a clear default so
 * future callers don't reinvent it.
 *
 * French typographic convention used here:
 *   - decimal point  → comma
 *   - thousands sep  → narrow no-break space (U+202F)
 *   - currency space → no-break space (U+00A0) before €
 *
 * Pure helpers: never throw, always return a string.
 */

const NBSP = ' ';
const NNBSP = ' ';

export type CurrencyOptions = {
  /** Number of decimals (default 2). Use 0 for KPI tiles, 2 for prices. */
  decimals?: number;
  /** Insert a NNBSP between thousands (default true). */
  thousands?: boolean;
};

/**
 * Format a number as Euros, French convention.
 *
 *   formatCurrency(12.5)          → "12,50 €"
 *   formatCurrency(1234.5)        → "1 234,50 €"
 *   formatCurrency(1234, { decimals: 0 }) → "1 234 €"
 *
 * ``null`` / ``undefined`` / ``NaN`` → "—" (em-dash) so empty cells in
 * tables render politely without "NaN €" leaking into the UI.
 */
export function formatCurrency(
  value: number | null | undefined,
  opts: CurrencyOptions = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const decimals = opts.decimals ?? 2;
  const thousands = opts.thousands ?? true;
  const fixed = value.toFixed(decimals);
  const [intPart, decPart] = fixed.split('.');
  const intGrouped = thousands
    ? intPart.replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP)
    : intPart;
  const body = decPart ? `${intGrouped},${decPart}` : intGrouped;
  return `${body}${NBSP}€`;
}

/**
 * Integer-only currency for KPI tiles where we don't care about cents.
 * Thin alias to keep callsites readable.
 */
export function formatCurrencyInt(value: number | null | undefined): string {
  return formatCurrency(value, { decimals: 0 });
}

/**
 * Format an integer with French thousands separator. No currency suffix.
 *
 *   formatNumber(1234567)  → "1 234 567"
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return Math.round(value)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);
}

/**
 * Format a fraction as a percent with one decimal:
 *
 *   formatPercent(0.124)  → "12,4 %"
 *   formatPercent(12.4)   → "12,4 %"        (auto-detect 0..1 vs 0..100)
 *
 * Heuristic: if 0 <= |value| <= 1 we treat it as a fraction; otherwise as
 * already-scaled percent. Override via the ``alreadyPercent`` flag.
 */
export function formatPercent(
  value: number | null | undefined,
  opts: { decimals?: number; alreadyPercent?: boolean } = {},
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  const decimals = opts.decimals ?? 1;
  const scaled = opts.alreadyPercent ?? Math.abs(value) > 1
    ? value
    : value * 100;
  return `${scaled.toFixed(decimals).replace('.', ',')}${NBSP}%`;
}
