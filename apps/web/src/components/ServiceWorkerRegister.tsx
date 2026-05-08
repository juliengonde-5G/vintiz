'use client';

/**
 * Registers the Vintiz service worker (public/sw.js) on first mount.
 *
 * Mounted once at the layout root — invisible component, no UI. Bails
 * out cleanly when:
 *  - the browser doesn't support service workers (older browsers),
 *  - we're running on http:// (SW requires HTTPS or localhost),
 *  - the registration throws (the page still works without push).
 *
 * The register is intentionally fire-and-forget : we don't surface
 * errors to the manager because they can't act on them.
 */

import { useEffect } from 'react';

export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!('serviceWorker' in navigator)) return;
    // SW requires a secure context. localhost is treated as secure by the
    // browser, so dev (http://localhost:3000) still works.
    if (!window.isSecureContext) return;

    const ctrl = new AbortController();

    // Defer to idle so we don't compete with the first paint of the
    // back-office. requestIdleCallback isn't in iOS Safari ; fall back
    // to setTimeout(0) which at least yields after the first frame.
    const schedule =
      'requestIdleCallback' in window
        ? (cb: () => void) => (window as unknown as { requestIdleCallback: (cb: () => void) => number }).requestIdleCallback(cb)
        : (cb: () => void) => window.setTimeout(cb, 0);

    schedule(() => {
      if (ctrl.signal.aborted) return;
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
        // Ignore — registration failures are non-fatal for the back-office.
      });
    });

    return () => ctrl.abort();
  }, []);

  return null;
}
