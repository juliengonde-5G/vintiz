/**
 * Platform detection helpers — single source of truth for OS-specific
 * branches in the UI.
 *
 * Vintiz used to be iPad-first (Safari + AirPrint + Apple Wallet). After
 * the M1 hardware migration to Android tablets (Lenovo Idea Tab Pro 13"
 * caisse + Galaxy Tab S11 Ultra portable), several flows need to behave
 * differently: AirPrint vanishes, pop-up settings move from "Safari" to
 * "Chrome", Apple Wallet becomes irrelevant on Android.
 *
 * Prefer **feature detection** when possible (``'ontouchstart' in window``,
 * ``navigator.share``, ``WebUSB`` etc.). Only fall back to UA sniffing
 * when no feature flag exists for what we want — typically: which app
 * label / which print path / which wallet provider.
 *
 * All helpers are SSR-safe: they return ``false`` on the server (where
 * ``navigator`` is undefined) so React hydration won't mismatch.
 */

const _ua = (): string => {
  if (typeof navigator === 'undefined') return '';
  return navigator.userAgent || '';
};

/** True on iPhone / iPad / iPod, including iPadOS desktop-mode fallback. */
export function isIOS(): boolean {
  const ua = _ua();
  if (!ua) return false;
  if (/iPad|iPhone|iPod/.test(ua)) return true;
  // iPadOS 13+ reports "MacIntel" by default. Cross-check with touch.
  if (typeof navigator !== 'undefined') {
    const platform = (navigator as { platform?: string }).platform || '';
    if (platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1) {
      return true;
    }
  }
  return false;
}

/** True on Android phones and tablets (Chrome, Samsung Internet, Firefox). */
export function isAndroid(): boolean {
  return /Android/i.test(_ua());
}

/** True if the device runs iOS Safari (vs Chrome iOS, which spells WebKit too). */
export function isIOSSafari(): boolean {
  if (!isIOS()) return false;
  const ua = _ua();
  // CriOS = Chrome iOS, FxiOS = Firefox iOS, EdgiOS = Edge iOS — exclude them.
  return /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
}

/**
 * Generic "tablet or phone with touch" probe. Used when we want to
 * downsize a click-only desktop UI without hard-coding iOS or Android.
 */
export function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false;
  return 'ontouchstart' in window || (navigator?.maxTouchPoints || 0) > 0;
}
