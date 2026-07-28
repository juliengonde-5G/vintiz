'use client';

import Script from 'next/script';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

const CONSENT_KEY = 'vintiz_cookie_consent';

interface AnalyticsProps {
  /** GA4 (legacy) — chargé UNIQUEMENT si un ID est fourni ET consentement. */
  gaId?: string;
  /** Matomo — URL de l'instance (ex. https://analytics.vintiz.fr/). */
  matomoUrl?: string;
  /** Matomo — identifiant du site (setSiteId). */
  matomoSiteId?: string;
}

/**
 * Mesure d'audience Vintiz.
 *
 * PRIMAIRE = Matomo en mode « cookieless » (disableCookies). Configuré côté
 * serveur en mesure d'audience exemptée CNIL (anonymisation IP, pas de suivi
 * cross-site, pas de partage des données) → **exempté de consentement**, donc
 * chargé sans bandeau. Cf. docs/COMPLIANCE_TRACKING_PIXELS_2026.md.
 *
 * LEGACY = Google Analytics 4, conservé pour compat/repli. Non exempté par la
 * CNIL → reste strictement conditionné au consentement (bandeau cookies +
 * Consent Mode v2 à `denied` par défaut dans layout.tsx). Désactivé tant que
 * `NEXT_PUBLIC_GA_ID` est vide (état recommandé après migration Matomo).
 */
export default function Analytics({ gaId, matomoUrl, matomoSiteId }: AnalyticsProps) {
  const pathname = usePathname();
  const [gaReady, setGaReady] = useState(false);

  // --- GA4 (legacy) : gate consentement, inchangé ---------------------------
  useEffect(() => {
    if (!gaId) return;
    const consent = localStorage.getItem(CONSENT_KEY);
    if (consent === 'accepted') {
      setGaReady(true);
      window.gtag?.('consent', 'update', { analytics_storage: 'granted' });
    }
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ state: 'accepted' | 'declined' }>).detail;
      if (detail?.state === 'accepted') {
        setGaReady(true);
        window.gtag?.('consent', 'update', { analytics_storage: 'granted' });
      } else {
        // Retrait / refus : on coupe la mesure GA4 côté Consent Mode.
        window.gtag?.('consent', 'update', { analytics_storage: 'denied' });
      }
    };
    window.addEventListener('vintiz:consent', handler as EventListener);
    return () => window.removeEventListener('vintiz:consent', handler as EventListener);
  }, [gaId]);

  // --- Matomo (primaire) : suivi des changements de route (SPA) --------------
  const matomoOn = Boolean(matomoUrl && matomoSiteId);
  useEffect(() => {
    if (!matomoOn || !pathname) return;
    const paq = (window as unknown as { _paq?: unknown[] })._paq;
    if (!paq) return;
    paq.push(['setCustomUrl', window.location.href]);
    paq.push(['setDocumentTitle', document.title]);
    paq.push(['trackPageView']);
  }, [pathname, matomoOn]);

  return (
    <>
      {/* Matomo cookieless — exempté, chargé sans consentement. */}
      {matomoOn && (
        <Script id="matomo-init" strategy="afterInteractive">
          {`
            var _paq = window._paq = window._paq || [];
            _paq.push(['disableCookies']);
            _paq.push(['enableLinkTracking']);
            _paq.push(['trackPageView']);
            (function() {
              var u="${matomoUrl!.endsWith('/') ? matomoUrl : matomoUrl + '/'}";
              _paq.push(['setTrackerUrl', u+'matomo.php']);
              _paq.push(['setSiteId', '${matomoSiteId}']);
              var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
              g.async=true; g.src=u+'matomo.js'; s.parentNode.insertBefore(g,s);
            })();
          `}
        </Script>
      )}

      {/* GA4 legacy — uniquement si ID posé ET consentement accordé. */}
      {gaId && gaReady && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
            strategy="afterInteractive"
          />
          <Script id="ga-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              window.gtag = gtag;
              gtag('js', new Date());
              gtag('config', '${gaId}', {
                anonymize_ip: true,
                page_path: window.location.pathname,
              });
            `}
          </Script>
        </>
      )}
    </>
  );
}

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}
