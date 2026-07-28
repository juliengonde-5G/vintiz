'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

const CONSENT_KEY = 'vintiz_cookie_consent';

/** Événement émis par le lien « Gérer les cookies » du footer. */
export const OPEN_CONSENT_EVENT = 'vintiz:open-consent';

function emitConsent(state: 'accepted' | 'declined') {
  localStorage.setItem(CONSENT_KEY, state);
  window.dispatchEvent(
    new CustomEvent('vintiz:consent', { detail: { state } })
  );
}

interface CookieBannerProps {
  /**
   * `true` seulement si un traceur soumis à consentement (GA4) est configuré.
   * Matomo cookieless étant exempté, sans GA4 il n'y a rien à consentir : le
   * bandeau ne s'affiche pas et le retrait n'a pas d'objet.
   */
  hasConsentTracker?: boolean;
}

export default function CookieBanner({ hasConsentTracker = false }: CookieBannerProps) {
  const [show, setShow] = useState(false);
  // Choix déjà exprimé ? (pilote le libellé « gérer » vs 1ʳᵉ visite)
  const [priorChoice, setPriorChoice] = useState<string | null>(null);

  useEffect(() => {
    if (!hasConsentTracker) return;
    const stored = localStorage.getItem(CONSENT_KEY);
    setPriorChoice(stored);
    if (!stored) setShow(true); // 1ʳᵉ visite : demande de consentement.

    // Réouverture à la demande (footer « Gérer les cookies »).
    const openHandler = () => {
      setPriorChoice(localStorage.getItem(CONSENT_KEY));
      setShow(true);
    };
    window.addEventListener(OPEN_CONSENT_EVENT, openHandler);
    return () => window.removeEventListener(OPEN_CONSENT_EVENT, openHandler);
  }, [hasConsentTracker]);

  if (!hasConsentTracker || !show) return null;

  const accept = () => {
    emitConsent('accepted');
    setPriorChoice('accepted');
    setShow(false);
  };

  const decline = () => {
    // Sert aussi de RETRAIT : si l'utilisateur avait accepté, on repasse en
    // refusé et Analytics coupe la mesure GA4 (Consent Mode → denied).
    emitConsent('declined');
    setPriorChoice('declined');
    setShow(false);
  };

  const isManaging = priorChoice !== null;

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
              uniquement des cookies fonctionnels nécessaires au site. Notre mesure d&apos;audience
              anonyme (sans cookie) ne nécessite pas votre accord. Avec votre consentement,
              Google&nbsp;Analytics&nbsp;4 pourra en plus déposer un cookie de mesure. Aucun cookie
              publicitaire tiers.
              {isManaging && (
                <span className="block mt-1 text-vz-ink-mute">
                  Choix actuel :{' '}
                  <span className="font-medium">
                    {priorChoice === 'accepted' ? 'accepté' : 'refusé'}
                  </span>
                  . Vous pouvez le modifier ci-contre à tout moment.
                </span>
              )}{' '}
              <Link href="/confidentialite" className="underline text-vz-teal hover:text-vz-teal-deep">
                Politique de confidentialité
              </Link>
            </p>
          </div>
          {/* Refus aussi simple et visible que l'acceptation (lignes directrices
              CNIL/EDPB) : mêmes dimensions, contraste équivalent. Le refus vaut
              retrait quand un choix a déjà été exprimé. */}
          <div className="flex gap-3 shrink-0">
            <button
              type="button"
              onClick={decline}
              data-testid="cookie-decline"
              className="flex-1 sm:flex-none sm:min-w-[150px] px-4 py-2 text-sm font-medium text-vz-teal border border-vz-teal rounded-lg hover:bg-vz-teal/5 transition-colors"
            >
              {isManaging ? 'Refuser / retirer' : 'Continuer sans accepter'}
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
