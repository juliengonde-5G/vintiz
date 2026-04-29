'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import SeoSnapshotsCard from '@/components/visibility/SeoSnapshotsCard';
import SocialPostsCard from '@/components/visibility/SocialPostsCard';
import ReviewsCard from '@/components/visibility/ReviewsCard';
import { api } from '@/lib/api';

interface SEOCheck {
  name: string;
  passed: boolean;
  detail: string | null;
}

interface SEOStatus {
  site_url: string;
  ga_measurement_id: string | null;
  google_site_verification_configured: boolean;
  checks: SEOCheck[];
  score: number;
  fetched_at: string;
  response_ms: number | null;
}

const SEARCH_CONSOLE_URL = 'https://search.google.com/search-console';
const GA_URL = 'https://analytics.google.com/';
const PAGESPEED_URL_BASE = 'https://pagespeed.web.dev/report?url=';

function scoreColor(score: number): string {
  if (score >= 85) return 'text-vz-teal';
  if (score >= 60) return 'text-orange-500';
  return 'text-red-600';
}

function scoreBg(score: number): string {
  if (score >= 85) return 'bg-vz-teal/10 border-vz-teal/30';
  if (score >= 60) return 'bg-orange-50 border-orange-200';
  return 'bg-red-50 border-red-200';
}

export default function SEOPage() {
  const [status, setStatus] = useState<SEOStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/seo/status');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const pageSpeedUrl = status
    ? `${PAGESPEED_URL_BASE}${encodeURIComponent(status.site_url)}`
    : PAGESPEED_URL_BASE;

  return (
    <div className="min-h-screen bg-vz-bg md:pl-64">
      <Sidebar />
      <main className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
            <div>
              <h1 className="font-display text-2xl md:text-3xl text-black">
                Performance SEO
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                Suivi du référencement naturel de la landing page publique.
              </p>
            </div>
            <Button onClick={refresh} disabled={loading}>
              {loading ? 'Analyse…' : 'Rafraîchir'}
            </Button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 text-sm">
              {error}
            </div>
          )}

          {loading && !status && (
            <div className="text-gray-400 py-12 text-center">Analyse en cours…</div>
          )}

          {status && (
            <>
              {/* Score global */}
              <Card className="mb-6">
                <div className="flex flex-col sm:flex-row items-center gap-6">
                  <div
                    className={`w-32 h-32 rounded-full border-4 ${scoreBg(
                      status.score
                    )} flex items-center justify-center flex-shrink-0`}
                  >
                    <div className="text-center">
                      <div className={`text-4xl font-bold ${scoreColor(status.score)}`}>
                        {status.score}
                      </div>
                      <div className="text-xs text-gray-400 uppercase tracking-wider">
                        /100
                      </div>
                    </div>
                  </div>
                  <div className="flex-1 text-center sm:text-left">
                    <div className="text-sm text-gray-500 mb-1">Landing page</div>
                    <a
                      href={status.site_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-lg font-display text-vz-teal hover:underline break-all"
                    >
                      {status.site_url}
                    </a>
                    <div className="mt-3 flex gap-4 text-sm text-gray-500 flex-wrap justify-center sm:justify-start">
                      <span>
                        Temps de réponse :{' '}
                        <b className="text-black">
                          {status.response_ms != null ? `${status.response_ms} ms` : '—'}
                        </b>
                      </span>
                      <span>
                        Dernière analyse :{' '}
                        <b className="text-black">
                          {new Date(status.fetched_at).toLocaleString('fr-FR')}
                        </b>
                      </span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Analytics config */}
              <Card title="Marqueurs & intégrations" className="mb-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                        status.ga_measurement_id ? 'bg-vz-teal/10 text-vz-teal' : 'bg-gray-100 text-gray-400'
                      }`}
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-black">Google Analytics 4</div>
                      <div className="text-xs text-gray-500 font-mono mt-0.5">
                        {status.ga_measurement_id || 'Non configuré (NEXT_PUBLIC_GA_ID)'}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        Chargement différé après consentement cookies (RGPD).
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                        status.google_site_verification_configured
                          ? 'bg-vz-teal/10 text-vz-teal'
                          : 'bg-gray-100 text-gray-400'
                      }`}
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 12l2 2 4-4" />
                        <circle cx="12" cy="12" r="10" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-black">Search Console</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {status.google_site_verification_configured
                          ? 'Vérification configurée'
                          : 'Non configurée (NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION)'}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="mt-5 pt-5 border-t border-gray-100 flex gap-3 flex-wrap">
                  <a
                    href={GA_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm px-4 py-2 bg-vz-teal text-white rounded-lg hover:bg-vz-teal/90 transition-colors"
                  >
                    Ouvrir GA4 →
                  </a>
                  <a
                    href={SEARCH_CONSOLE_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm px-4 py-2 bg-white border border-vz-teal text-vz-teal rounded-lg hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    Search Console →
                  </a>
                  <a
                    href={pageSpeedUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    PageSpeed Insights →
                  </a>
                  <a
                    href={`${status.site_url}/robots.txt`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    robots.txt
                  </a>
                  <a
                    href={`${status.site_url}/sitemap.xml`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    sitemap.xml
                  </a>
                </div>
              </Card>

              {/* Checks détaillés */}
              <Card title="Contrôles techniques" className="mb-6">
                <ul className="divide-y divide-gray-100">
                  {status.checks.map((check, idx) => (
                    <li key={idx} className="py-3 flex items-start gap-3">
                      <span
                        className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                          check.passed
                            ? 'bg-vz-teal/10 text-vz-teal'
                            : 'bg-red-50 text-red-600'
                        }`}
                      >
                        {check.passed ? '✓' : '!'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-black">
                          {check.name}
                        </div>
                        {check.detail && (
                          <div className="text-xs text-gray-500 mt-0.5 truncate font-mono">
                            {check.detail}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>

              {/* Procédure d'activation */}
              <Card title="Activer le suivi GA4" className="mb-6">
                <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside">
                  <li>
                    Créer une propriété GA4 sur{' '}
                    <a className="text-vz-teal underline" href={GA_URL} target="_blank" rel="noopener noreferrer">
                      analytics.google.com
                    </a>{' '}
                    et récupérer le Measurement ID (<code className="bg-gray-100 px-1 py-0.5 rounded">G-XXXXXXXXXX</code>).
                  </li>
                  <li>
                    Ajouter dans <code className="bg-gray-100 px-1 py-0.5 rounded">apps/site/.env</code> :{' '}
                    <code className="bg-gray-100 px-1 py-0.5 rounded">NEXT_PUBLIC_GA_ID=G-XXXXXXXXXX</code>
                  </li>
                  <li>
                    Ajouter dans <code className="bg-gray-100 px-1 py-0.5 rounded">apps/api/.env</code> :{' '}
                    <code className="bg-gray-100 px-1 py-0.5 rounded">GA_MEASUREMENT_ID=G-XXXXXXXXXX</code>
                  </li>
                  <li>
                    Vérifier le site sur Search Console et renseigner{' '}
                    <code className="bg-gray-100 px-1 py-0.5 rounded">NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION</code>.
                  </li>
                  <li>Redéployer et revenir ici pour voir le score passer au vert.</li>
                </ol>
              </Card>
            </>
          )}

          {/* P3-003 + P3-004 + P3-005 — visibility module */}
          <div className="mt-6 space-y-6">
            <SeoSnapshotsCard />
            <SocialPostsCard />
            <ReviewsCard />
          </div>
        </div>
      </main>
    </div>
  );
}
