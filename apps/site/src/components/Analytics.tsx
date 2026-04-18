'use client';

import Script from 'next/script';
import { useEffect, useState } from 'react';

const CONSENT_KEY = 'vintiz_cookie_consent';

interface AnalyticsProps {
  gaId: string;
}

// GA4 with Google Consent Mode v2.
// Loaded only when NEXT_PUBLIC_GA_ID is set AND the visitor has accepted cookies.
// Until consent, gtag commands buffer with analytics_storage='denied' (set in layout).
export default function Analytics({ gaId }: AnalyticsProps) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!gaId) return;
    const consent = localStorage.getItem(CONSENT_KEY);
    if (consent === 'accepted') {
      setReady(true);
      if (typeof window !== 'undefined' && typeof window.gtag === 'function') {
        window.gtag('consent', 'update', {
          analytics_storage: 'granted',
        });
      }
    }
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ state: 'accepted' | 'declined' }>).detail;
      if (detail?.state === 'accepted') {
        setReady(true);
        window.gtag?.('consent', 'update', { analytics_storage: 'granted' });
      } else {
        window.gtag?.('consent', 'update', { analytics_storage: 'denied' });
      }
    };
    window.addEventListener('vintiz:consent', handler as EventListener);
    return () => window.removeEventListener('vintiz:consent', handler as EventListener);
  }, [gaId]);

  if (!gaId || !ready) return null;

  return (
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
  );
}

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}
