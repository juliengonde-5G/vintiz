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
      aria-modal="false"
      aria-labelledby="cookie-banner-title"
      aria-describedby="cookie-banner-desc"
      data-testid="cookie-banner"
      className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-vz-accent-soft/30 shadow-lg"
    >
      <div className="max-w-4xl mx-auto px-4 py-4 sm:px-6">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 text-sm text-black/70">
            <p id="cookie-banner-title" className="sr-only">
              Gestion des cookies
            </p>
            <p id="cookie-banner-desc">
              <span className="font-semibold text-black">Votre vie privée</span> — Nous utilisons
              uniquement des cookies fonctionnels nécessaires au site. Avec votre accord,
              Google&nbsp;Analytics&nbsp;4 (mesure d&apos;audience anonymisée, hébergement UE)
              pourra déposer un cookie pour améliorer votre expérience. Aucun cookie publicitaire
              tiers.{' '}
              <Link href="/confidentialite" className="underline text-vz-teal hover:text-vz-teal-deep">
                Politique de confidentialité
              </Link>
            </p>
          </div>
          {/* Refus aussi simple et visible que l'acceptation (lignes directrices
              CNIL/EDPB) : mêmes dimensions, contraste équivalent. */}
          <div className="flex gap-3 shrink-0">
            <button
              type="button"
              onClick={decline}
              data-testid="cookie-decline"
              className="flex-1 sm:flex-none sm:min-w-[150px] px-4 py-2 text-sm font-medium text-vz-teal border border-vz-teal rounded-lg hover:bg-vz-teal/5 transition-colors"
            >
              Continuer sans accepter
            </button>
            <button
              type="button"
              onClick={accept}
              data-testid="cookie-accept"
              className="flex-1 sm:flex-none sm:min-w-[150px] px-4 py-2 text-sm font-medium text-white bg-vz-teal rounded-lg hover:bg-vz-teal-deep transition-colors"
            >
              Tout accepter
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
