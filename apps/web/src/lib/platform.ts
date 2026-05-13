/**
 * Platform detection helpers — single source of truth for OS-specific
 * branches in the UI.
 *
 * Vintiz tourne désormais 100% sur Android (Lenovo Idea Tab Pro Gen 2
 * en caisse, autres tablettes Android pour les ventes mobiles). Les
 * helpers iOS/Safari/AirPrint/Apple Wallet ont été retirés — la base
 * de code est sans branche iOS.
 *
 * Prefer **feature detection** when possible (``'ontouchstart' in window``,
 * ``navigator.share``, ``WebUSB`` etc.). Only fall back to UA sniffing
 * when no feature flag exists — typically pour différencier desktop
 * vs tablette Android.
 *
 * All helpers are SSR-safe: they return ``false`` on the server (where
 * ``navigator`` is undefined) so React hydration won't mismatch.
 */

const _ua = (): string => {
  if (typeof navigator === 'undefined') return '';
  return navigator.userAgent || '';
};

/** True on Android phones and tablets (Chrome, Samsung Internet, Firefox). */
export function isAndroid(): boolean {
  return /Android/i.test(_ua());
}

/**
 * Generic "tablet or phone with touch" probe. Used when we want to
 * downsize a click-only desktop UI without hard-coding the OS.
 */
export function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false;
  return 'ontouchstart' in window || (navigator?.maxTouchPoints || 0) > 0;
}
