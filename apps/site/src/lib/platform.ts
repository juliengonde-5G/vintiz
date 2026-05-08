/**
 * Platform detection helpers — single source of truth for OS-specific
 * branches in the public site UI.
 *
 * Mirrors apps/web/src/lib/platform.ts so we don't duplicate UA-sniffing
 * across both apps. Kept narrow on purpose; only what the site actually
 * needs (mostly which Wallet provider to push to first).
 *
 * SSR-safe: returns ``false`` on the server so React hydration doesn't
 * mismatch.
 */

const _ua = (): string => {
  if (typeof navigator === 'undefined') return '';
  return navigator.userAgent || '';
};

export function isIOS(): boolean {
  const ua = _ua();
  if (!ua) return false;
  if (/iPad|iPhone|iPod/.test(ua)) return true;
  if (typeof navigator !== 'undefined') {
    const platform = (navigator as { platform?: string }).platform || '';
    if (platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1) {
      return true;
    }
  }
  return false;
}

export function isAndroid(): boolean {
  return /Android/i.test(_ua());
}
