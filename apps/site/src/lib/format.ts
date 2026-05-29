/**
 * Display formatting helpers for the public site.
 *
 * Pure + defensive: never throw, never render "NaN". A missing or invalid
 * price renders an em dash ("—") instead — this is the guard that prevents the
 * "NaN €" the Personal Shopper / Sélection cards used to show when a price
 * field was absent or in the wrong unit.
 *
 * French convention: decimal point → comma, no-break space before €.
 */

const NBSP = " ";

/** Format an integer amount of cents (e.g. 12999) as "129,99 €". */
export function formatPriceCents(cents: number | null | undefined): string {
  if (cents == null || !Number.isFinite(cents)) return "—";
  return (cents / 100).toFixed(2).replace(".", ",") + NBSP + "€";
}

/** Format an amount already expressed in euros (e.g. 129.99) as "129,99 €". */
export function formatPriceEuros(euros: number | null | undefined): string {
  if (euros == null || !Number.isFinite(euros)) return "—";
  return euros.toFixed(2).replace(".", ",") + NBSP + "€";
}
