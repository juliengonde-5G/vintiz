'use client';

import { useEffect } from 'react';

import { isAndroid } from './platform';

/**
 * Best-effort landscape lock — only effective when the app runs as a
 * standalone PWA (display-mode: standalone) AND the device honours the
 * Screen Orientation API. In a regular tab (Chrome non-installed), the
 * call throws DOMException "The page needs to be fullscreen" and we
 * silently swallow it.
 *
 * The caller decides when to lock — typically on /pos and /pos/close
 * mounted screens, where rotating to portrait makes the cart + product
 * grid layout collapse.
 */
export function useLandscapeLock(): void {
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Only attempt on Android (Lenovo Idea Tab Pro Gen 2 Chrome).
    if (!isAndroid()) return;

    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as { standalone?: boolean }).standalone === true;
    if (!isStandalone) return;

    const orientation = (screen as Screen & { orientation?: ScreenOrientation }).orientation;
    if (!orientation || typeof orientation.lock !== 'function') return;

    let unlocked = false;
    void orientation
      .lock('landscape')
      .catch(() => {
        // Swallowed — Chrome throws when not in fullscreen mode or when the
        // user disabled rotation lock in the OS. The page still works.
        unlocked = true;
      });

    return () => {
      if (unlocked) return;
      try {
        orientation.unlock();
      } catch {
        // Ignore — the next route might re-lock anyway.
      }
    };
  }, []);
}
