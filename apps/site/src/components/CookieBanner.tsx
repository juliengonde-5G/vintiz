'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

const CONSENT_KEY = 'vintiz_cookie_consent';

export default function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(CONSENT_KEY)) {
      setShow(true);
    }
  }, []);

  if (!show) return null;

  const accept = () => {
    localStorage.setItem(CONSENT_KEY, 'accepted');
    setShow(false);
  };

  const decline = () => {
    localStorage.setItem(CONSENT_KEY, 'declined');
    setShow(false);
  };

  return (
    <div
      role="dialog"
      aria-label="Gestion des cookies"
      className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 shadow-lg"
    >
      <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 text-sm text-gray-700">
            <p>
              <span className="font-semibold text-gray-900">Votre vie privée</span> — Nous utilisons des cookies
              fonctionnels nécessaires au fonctionnement du site. Avec votre accord, des cookies analytiques
              (mesure d&apos;audience anonyme) pourront être déposés afin d&apos;améliorer votre expérience.{' '}
              <Link href="/confidentialite" className="underline text-teal-700 hover:text-teal-900">
                Politique de confidentialité
              </Link>
            </p>
          </div>
          <div className="flex gap-3 shrink-0">
            <button
              onClick={decline}
              className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Refuser
            </button>
            <button
              onClick={accept}
              className="px-4 py-2 text-sm font-medium text-white bg-teal-700 rounded-lg hover:bg-teal-800 transition-colors"
            >
              Tout accepter
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
