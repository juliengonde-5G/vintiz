'use client';

import React, { useEffect, useState } from 'react';

import { isAndroid, isIOS } from '@/lib/platform';

/**
 * Chrome Android emits a ``beforeinstallprompt`` event when the PWA is
 * eligible to be added to the home screen. We capture it, defer the
 * native prompt, and show our own brand-styled banner with an "Install"
 * button — Chrome only emits the event once per device, so we want full
 * control over presentation.
 *
 * On iOS Safari (which never emits the event), we render a 1-time
 * hint pointing at the Share sheet instead. The hint is dismissible
 * and the dismissal is sticky via localStorage so cashiers don't see
 * the same nudge after their first install.
 */
type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
};

const STORAGE_KEY = 'vintiz_pwa_install_dismissed';
const STORAGE_VAL = '1';

export default function PwaInstallBanner() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIosHint, setShowIosHint] = useState(false);
  const [dismissed, setDismissed] = useState(true); // pessimistic; flipped on mount

  // Hydration-safe mount detection
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Skip everything if the app is already running as a standalone PWA.
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as { standalone?: boolean }).standalone === true;
    if (isStandalone) return;

    const stickyDismissed = localStorage.getItem(STORAGE_KEY) === STORAGE_VAL;
    setDismissed(stickyDismissed);
    if (stickyDismissed) return;

    if (isIOS()) {
      // No beforeinstallprompt on iOS — show a static hint card.
      setShowIosHint(true);
    }

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handler);

    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const dismiss = (): void => {
    setDismissed(true);
    setDeferred(null);
    setShowIosHint(false);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, STORAGE_VAL);
    }
  };

  const install = async (): Promise<void> => {
    if (!deferred) return;
    await deferred.prompt();
    const result = await deferred.userChoice;
    if (result.outcome === 'accepted') {
      dismiss();
    } else {
      // User dismissed the native prompt — don't re-show the banner this session.
      setDeferred(null);
    }
  };

  if (dismissed) return null;
  if (!deferred && !showIosHint) return null;

  return (
    <div className="fixed bottom-4 inset-x-4 z-[70] flex justify-center pointer-events-none">
      <div className="pointer-events-auto max-w-md w-full rounded-2xl bg-vz-teal-deep text-white shadow-2xl border border-white/10 backdrop-blur-sm p-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0">
            {/* Logo monogramme */}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-display text-sm font-semibold leading-tight">
              Installer Vintiz Caisse
            </p>
            <p className="text-xs opacity-80 mt-0.5">
              {deferred
                ? `Ajoute l'app à l'écran d'accueil ${isAndroid() ? 'Lenovo' : ''} pour un lancement instantané.`
                : 'Sur iPad : Partager → « Sur l\'écran d\'accueil ».'}
            </p>
            <div className="flex gap-2 mt-3">
              {deferred && (
                <button
                  onClick={install}
                  className="px-3 py-2 rounded-lg bg-vz-accent hover:opacity-90 text-white text-xs font-semibold min-h-[40px]"
                >
                  Installer
                </button>
              )}
              <button
                onClick={dismiss}
                className="px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs font-medium min-h-[40px]"
              >
                Plus tard
              </button>
            </div>
          </div>
          <button
            onClick={dismiss}
            className="text-white/60 hover:text-white text-lg leading-none p-1"
            aria-label="Fermer"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
