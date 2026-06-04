'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';
import { mediaUrl } from '@/lib/format';

// Cf. apps/api/app/services/capsule.py — formes synchronisées avec
// ``serialize_capsule()`` côté backend.
interface CapsuleProduct {
  id: string;
  name: string;
  brand?: string | null;
  category?: string | null;
  color?: string | null;
  size?: string | null;
  price_eur: number | null;
  photo_url?: string | null;
  trend_score?: number | null;
}

interface ColorPastille { name: string; hex?: string; note?: string }
interface WatchTypePastille { label: string; note?: string }
interface GiftIdeaPastille { label: string; price_range?: string; note?: string }

interface CapsuleProposal {
  iso_month: string;
  generated_at: string;
  audience: {
    top_categories: { name: string; count: number }[];
    top_brands: { name: string; count: number }[];
    top_colors: { name: string; count: number }[];
    cohort_size: number;
    period_days: number;
  };
  event: { name: string; keywords: string[] } | null;
  trend_products: CapsuleProduct[];
  event_products: CapsuleProduct[];
  pastilles: {
    colors: ColorPastille[];
    watch_types: WatchTypePastille[];
    gift_ideas: GiftIdeaPastille[];
  };
  available_count: number;
}

interface CapsuleResponse {
  id: string;
  iso_month: string;
  proposal: CapsuleProposal;
  used_llm: boolean;
  accepted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

const MONTH_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function formatIsoMonth(iso: string): string {
  const [year, month] = iso.split('-');
  const idx = Math.max(0, Math.min(11, Number(month) - 1));
  return `${MONTH_FR[idx]} ${year}`;
}

function formatPrice(p?: number | null): string {
  if (p == null) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: p % 1 === 0 ? 0 : 2,
  }).format(p);
}

function ProductCard({ product, badge }: { product: CapsuleProduct; badge?: string }) {
  return (
    <Link
      href={`/inventory/${product.id}`}
      className="group block rounded-vz-lg overflow-hidden bg-white border border-vz-line hover:shadow-vz-soft transition-shadow"
    >
      <div className="aspect-[4/5] bg-vz-bg-alt relative">
        {product.photo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl(product.photo_url)}
            alt={product.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs text-vz-ink-mute px-4 text-center">
            Pas de photo
          </div>
        )}
        {badge && (
          <span className="absolute top-2 left-2 text-[10px] tracking-[0.18em] uppercase font-semibold px-2 py-1 rounded-full bg-white/95 text-vz-teal-deep">
            {badge}
          </span>
        )}
        {product.trend_score != null && product.trend_score >= 60 && (
          <span className="absolute top-2 right-2 text-[10px] font-mono px-2 py-1 rounded-full bg-vz-teal text-white">
            ★ {Math.round(product.trend_score)}
          </span>
        )}
      </div>
      <div className="p-3 space-y-1">
        <p className="text-sm font-medium text-vz-ink truncate">{product.name}</p>
        <p className="text-[11px] text-vz-ink-mute truncate">
          {[product.brand, product.category, product.size].filter(Boolean).join(' · ') || '—'}
        </p>
        <p className="text-sm font-display font-semibold text-vz-teal-deep">
          {formatPrice(product.price_eur)}
        </p>
      </div>
    </Link>
  );
}

export default function CapsulePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [capsule, setCapsule] = useState<CapsuleResponse | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/admin/capsule/current');
      if (!res.ok) throw new Error('load failed');
      setCapsule(await res.json());
    } catch {
      setError("La capsule n'a pas pu être chargée.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const regenerate = async () => {
    setRegenerating(true);
    setError(null);
    try {
      const res = await api.post('/api/admin/capsule/regenerate', {});
      if (!res.ok) throw new Error('regen failed');
      setCapsule(await res.json());
    } catch {
      setError('Régénération impossible. Réessaie dans un instant.');
    } finally {
      setRegenerating(false);
    }
  };

  const proposal = capsule?.proposal;
  const audienceSummary = useMemo(() => {
    if (!proposal?.audience?.top_categories?.length) return null;
    return proposal.audience.top_categories
      .slice(0, 3)
      .map((c) => c.name)
      .join(' · ');
  }, [proposal]);

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 max-w-6xl">
        {/* Mobile sticky top bar */}
        <div className="md:hidden sticky top-0 z-30 -mx-4 mb-4 px-4 py-2 bg-white/90 backdrop-blur border-b border-gray-200 flex items-center gap-3 text-sm">
          <Link href="/ia" className="text-vz-teal font-medium">← IA</Link>
          <span className="font-semibold text-vz-ink">Capsule du mois</span>
        </div>
        <Link
          href="/ia"
          className="inline-flex items-center gap-2 text-sm text-vz-teal hover:text-vz-teal-deep mb-4"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Retour au compagnon IA
        </Link>

        {/* Hero */}
        <div className="rounded-3xl bg-vz-teal p-6 md:p-8 text-white shadow-vz-soft mb-6 relative overflow-hidden">
          <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
          <div className="relative z-10 flex items-start justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-90">
                Capsule éditoriale
              </p>
              <h1 className="text-3xl md:text-4xl font-display font-semibold mt-1 capitalize">
                {proposal ? formatIsoMonth(proposal.iso_month) : 'Chargement…'}
              </h1>
              {proposal?.event && (
                <p className="text-sm opacity-90 mt-1 max-w-xl">
                  Événement du mois : <strong>{proposal.event.name}</strong>
                </p>
              )}
              {audienceSummary && (
                <p className="text-sm opacity-80 mt-2 max-w-xl">
                  Audience fidèle ciblée · {audienceSummary}
                  {proposal && proposal.audience.cohort_size > 0 && (
                    <span className="opacity-75"> ({proposal.audience.cohort_size} clientes actives sur {proposal.audience.period_days}j)</span>
                  )}
                </p>
              )}
              <p className="text-xs opacity-75 mt-3 italic">
                Régénérée automatiquement le 1er de chaque mois à 8h00 (Paris). Seuls les produits actuellement en stock sont proposés.
              </p>
            </div>
            <Button
              onClick={regenerate}
              disabled={regenerating || loading}
              variant="secondary"
            >
              {regenerating ? 'Régénération…' : 'Régénérer maintenant'}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-vz-accent-soft bg-vz-accent-soft text-vz-accent px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {loading && (
          <Card>
            <div className="flex items-center gap-3 text-sm text-gray-600">
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" />
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
              <span>Composition de la capsule en cours…</span>
            </div>
          </Card>
        )}

        {proposal && (
          <div className="space-y-10">
            {/* Pastilles d'information */}
            <section>
              <div className="mb-3">
                <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
                  Inspirations du mois
                </p>
                <h2 className="text-2xl font-display font-semibold text-vz-ink mt-1">
                  Pastilles éditoriales
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {/* Couleurs tendances */}
                <Card title="Couleurs tendances" variant="default">
                  <div className="space-y-3">
                    {proposal.pastilles.colors.map((c, i) => (
                      <div key={`${c.name}-${i}`} className="flex items-start gap-3">
                        <span
                          className="mt-0.5 h-8 w-8 rounded-full border border-vz-line shrink-0"
                          style={{ backgroundColor: c.hex || '#CDE5DF' }}
                          aria-hidden
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-vz-ink">{c.name}</p>
                          {c.note && (
                            <p className="text-xs text-vz-ink-mute leading-relaxed">{c.note}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>

                {/* Types à surveiller */}
                <Card title="À surveiller" variant="default">
                  <ul className="space-y-3">
                    {proposal.pastilles.watch_types.map((w, i) => (
                      <li key={`${w.label}-${i}`} className="flex items-start gap-2">
                        <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-vz-teal shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-vz-ink">{w.label}</p>
                          {w.note && (
                            <p className="text-xs text-vz-ink-mute leading-relaxed">{w.note}</p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>

                {/* Idées cadeaux */}
                <Card title="Idées cadeaux" variant="accent">
                  <ul className="space-y-3">
                    {proposal.pastilles.gift_ideas.map((g, i) => (
                      <li key={`${g.label}-${i}`}>
                        <div className="flex items-baseline justify-between gap-2">
                          <p className="text-sm font-medium text-vz-ink">{g.label}</p>
                          {g.price_range && (
                            <span className="text-[11px] font-mono text-vz-accent">{g.price_range}</span>
                          )}
                        </div>
                        {g.note && (
                          <p className="text-xs text-vz-ink-mute mt-0.5 leading-relaxed">{g.note}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            </section>

            {/* Zone tendance — produits de la semaine */}
            <section>
              <div className="flex items-baseline justify-between mb-3">
                <div>
                  <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
                    Zone tendance
                  </p>
                  <h2 className="text-2xl font-display font-semibold text-vz-ink mt-1">
                    Coups d&apos;éclat de la semaine
                  </h2>
                </div>
                <span className="text-xs text-vz-ink-mute">
                  {proposal.trend_products.length} pièce{proposal.trend_products.length > 1 ? 's' : ''} en stock
                </span>
              </div>
              {proposal.trend_products.length === 0 ? (
                <Card>
                  <p className="text-sm text-vz-ink-mute">
                    Pas encore de pièces avec un score de tendance suffisant ce mois-ci.
                    Saisis de nouvelles arrivées pour alimenter la zone.
                  </p>
                </Card>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {proposal.trend_products.map((p) => (
                    <ProductCard key={p.id} product={p} badge="Tendance" />
                  ))}
                </div>
              )}
            </section>

            {/* Produits événement */}
            {proposal.event && proposal.event_products.length > 0 && (
              <section>
                <div className="flex items-baseline justify-between mb-3">
                  <div>
                    <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
                      Événement du mois
                    </p>
                    <h2 className="text-2xl font-display font-semibold text-vz-ink mt-1">
                      Spécial {proposal.event.name}
                    </h2>
                  </div>
                  <span className="text-xs text-vz-ink-mute">
                    {proposal.event_products.length} pièce{proposal.event_products.length > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {proposal.event_products.map((p) => (
                    <ProductCard key={p.id} product={p} badge="Événement" />
                  ))}
                </div>
                {proposal.event.keywords?.length > 0 && (
                  <p className="text-[11px] text-vz-ink-mute mt-3">
                    Sélection basée sur les mots-clés :{' '}
                    {proposal.event.keywords.map((k) => (
                      <span
                        key={k}
                        className="inline-block mr-1 mb-1 px-2 py-0.5 rounded-full bg-vz-bg-alt text-vz-ink-soft"
                      >
                        {k}
                      </span>
                    ))}
                  </p>
                )}
              </section>
            )}

            {/* Footer technique */}
            <p className="text-[11px] text-vz-ink-mute text-center pt-4 border-t border-vz-line">
              Générée le {new Date(proposal.generated_at).toLocaleString('fr-FR')} ·{' '}
              {capsule?.used_llm ? 'pastilles rédigées par Claude' : 'pastilles en mode repli'} ·{' '}
              {proposal.available_count} pièces actives au catalogue
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
