'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

const CONSENT_KEY = 'vintiz_cookie_consent';

function emitConsent(state: 'accepted' | 'declined') {
  localStorage.setItem(CONSENT_KEY, state);
  window.dispatchEvent(
    new CustomEvent('vintiz:consent', { detail: { state } })
  );
}

export default function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(CONSENT_KEY)) {
      setShow(true);
    }
  }, []);

  if (!show) return null;

  const accept = () => {
    emitConsent('accepted');
    setShow(false);
  };

  const decline = () => {
    emitConsent('declined');
    setShow(false);
  };

  return (
    <div
      role="dialog"
      aria-label="Gestion des cookies"
      className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-vz-accent-soft/30 shadow-lg"
    >
      <div className="max-w-4xl mx-auto px-4 py-4 sm:px-6">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 text-sm text-black/70">
            <p>
              <span className="font-semibold text-black">Votre vie privée</span> — Nous utilisons des cookies
              fonctionnels nécessaires au fonctionnement du site. Avec votre accord, des cookies analytiques
              (mesure d&apos;audience anonyme via Google Analytics) pourront être déposés afin d&apos;améliorer votre expérience.{' '}
              <Link href="/confidentialite" className="underline text-vz-teal hover:text-vz-teal-deep">
                Politique de confidentialité
              </Link>
            </p>
          </div>
          <div className="flex gap-3 shrink-0">
            <button
              onClick={decline}
              className="px-4 py-2 text-sm font-medium text-black/70 border border-black/20 rounded-lg hover:bg-black/5 transition-colors"
            >
              Refuser
            </button>
            <button
              onClick={accept}
              className="px-4 py-2 text-sm font-medium text-white bg-vz-teal rounded-lg hover:bg-vz-teal-deep transition-colors"
            >
              Tout accepter
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
