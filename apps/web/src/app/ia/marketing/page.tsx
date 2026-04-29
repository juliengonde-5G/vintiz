'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface InstaPost {
  produit_id?: string;
  produit_nom?: string;
  angle_editorial?: string;
  caption_instagram?: string;
  hashtags?: string[];
  best_time_post?: string;
  story_idea?: string;
  visual_brief?: string;
  carousel_slides?: string[];
}

interface DigitalMarketing {
  persona?: string;
  post_de_la_semaine?: InstaPost;
  actions_de_la_semaine?: string[];
}

interface MonthTrend { mois: string; tendance: string }
interface MajorEvent { date: string; evenement: string; impact: string }
interface Reco { priorite: string; action: string; impact: string }

interface RetailDirector {
  persona?: string;
  conjoncture_mois_dernier?: string;
  tendance_3_mois?: MonthTrend[];
  evenements_majeurs?: MajorEvent[];
  recommandations_boutique?: Reco[];
  kpi_cibles?: Record<string, string | number>;
}

interface HeroProduct {
  id: string;
  name: string;
  brand?: string | null;
  size?: string | null;
  color?: string | null;
  price_eur: number;
  photo_url?: string | null;
  trend_score?: number;
}

interface Report {
  generated_at?: string;
  context?: Record<string, number>;
  hero_product?: HeroProduct | null;
  digital_marketing?: DigitalMarketing;
  retail_director?: RetailDirector;
}

const PRIO_COLOR: Record<string, string> = {
  haute: 'bg-vz-accent-soft text-vz-accent',
  moyenne: 'bg-vz-teal-soft text-vz-teal-deep',
  faible: 'bg-vz-bg-alt text-vz-ink-mute',
};

export default function MarketingReportPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [generatingVisual, setGeneratingVisual] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/ai/persona/marketing', {});
      if (!res.ok) throw new Error('report failed');
      setReport(await res.json());
    } catch {
      setError('Le rapport n’a pas pu être généré. Vérifie la clé ANTHROPIC_API_KEY.');
    } finally {
      setLoading(false);
    }
  };

  const generateVisual = async () => {
    const post = report?.digital_marketing?.post_de_la_semaine;
    if (!post?.visual_brief) return;
    setGeneratingVisual(true);
    try {
      // Best-effort: ask the AI image endpoint if available, otherwise open a search/prompt link
      const res = await api.post('/api/ai/visual/generate', { prompt: post.visual_brief });
      if (res.ok) {
        const data = await res.json();
        if (data.image_url) {
          window.open(data.image_url, '_blank');
        }
      } else {
        // Fallback: open Imagen / DALL-E playground prompt in new tab
        const search = encodeURIComponent(post.visual_brief);
        window.open(`https://image.pollinations.ai/prompt/${search}`, '_blank');
      }
    } catch {
      const search = encodeURIComponent(post.visual_brief);
      window.open(`https://image.pollinations.ai/prompt/${search}`, '_blank');
    }
    setGeneratingVisual(false);
  };

  const dm = report?.digital_marketing;
  const rd = report?.retail_director;
  const hero = report?.hero_product;

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 max-w-5xl">
        <Link href="/ia" className="inline-flex items-center gap-2 text-sm text-vz-teal hover:text-vz-teal-deep mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Retour au compagnon IA
        </Link>

        <div className="rounded-3xl bg-vz-teal p-6 md:p-8 text-white shadow-vz-soft mb-6 relative overflow-hidden">
          <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
          <div className="relative z-10 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-90">
                Personas · Marketing digital + Direction retail
              </p>
              <h1 className="text-3xl md:text-4xl font-display font-semibold mt-1">
                Rapport marketing
              </h1>
              <p className="text-sm opacity-90 mt-1 max-w-xl">
                Deux experts à votre service : Léa (marketing digital) propose la
                publication Instagram de la semaine. Jean-Marc (direction régionale retail)
                analyse la conjoncture et les 3 prochains mois.
              </p>
            </div>
            <Button onClick={generate} disabled={loading} variant="secondary">
              {loading ? 'Analyse en cours…' : report ? 'Régénérer' : 'Générer le rapport'}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-vz-accent-soft bg-vz-accent-soft text-vz-accent px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {!report && !loading && (
          <Card variant="gradient">
            <p className="text-sm text-gray-700">
              Cliquez sur <strong>Générer le rapport</strong> pour obtenir le brief
              hebdomadaire complet — la publication Instagram de la semaine avec son visuel,
              et la note retail mensuelle (conjoncture, prévisions 3 mois, événements majeurs).
            </p>
          </Card>
        )}

        {loading && (
          <Card>
            <div className="flex items-center gap-3 text-sm text-gray-600">
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" />
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
              <span>Léa et Jean-Marc rédigent le rapport…</span>
            </div>
          </Card>
        )}

        {report && (
          <div className="space-y-8 animate-slide-up">
            {/* ─── PARTIE 1 — Marketing digital · Insta post de la semaine ─── */}
            {dm && (
              <section>
                <div className="flex items-baseline justify-between mb-3">
                  <div>
                    <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
                      Partie 1 · Marketing digital
                    </p>
                    <h2 className="text-2xl font-display font-semibold text-black mt-1">
                      Publication Instagram de la semaine
                    </h2>
                  </div>
                </div>
                {dm.persona && (
                  <p className="text-sm text-vz-ink-mute mb-4 italic">— {dm.persona}</p>
                )}

                {dm.post_de_la_semaine && (
                  <Card>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                      {/* Hero / produit */}
                      <div>
                        <div className="aspect-square rounded-vz-lg overflow-hidden bg-vz-bg-alt mb-3">
                          {hero?.photo_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={hero.photo_url} alt={hero.name} className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-xs text-vz-ink-mute p-3 text-center">
                              {dm.post_de_la_semaine.visual_brief || 'Visuel à générer'}
                            </div>
                          )}
                        </div>
                        {hero && (
                          <Link href={`/inventory/${hero.id}`} className="block bg-vz-bg rounded-lg p-3 hover:bg-vz-bg-alt transition-colors">
                            <p className="text-[10px] uppercase tracking-[0.18em] text-vz-teal font-medium">Pièce mise en avant</p>
                            <p className="font-medium text-black mt-1">{hero.brand || hero.name}</p>
                            <p className="text-xs text-vz-ink-soft">
                              {hero.name} {hero.size && `· T. ${hero.size}`} {hero.color && `· ${hero.color}`}
                            </p>
                            <p className="text-sm font-display font-semibold text-vz-teal mt-1">
                              {hero.price_eur.toFixed(0)} €
                            </p>
                          </Link>
                        )}
                      </div>

                      {/* Caption + meta */}
                      <div className="md:col-span-2 space-y-4">
                        {dm.post_de_la_semaine.angle_editorial && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-1">
                              Angle éditorial
                            </p>
                            <p className="text-base text-black font-display italic">
                              &laquo;&nbsp;{dm.post_de_la_semaine.angle_editorial}&nbsp;&raquo;
                            </p>
                          </div>
                        )}

                        {dm.post_de_la_semaine.caption_instagram && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-1">
                              Caption Instagram
                            </p>
                            <div className="bg-vz-bg rounded-lg p-4 whitespace-pre-line text-sm text-vz-ink-soft border border-vz-line">
                              {dm.post_de_la_semaine.caption_instagram}
                            </div>
                            <button
                              onClick={() => navigator.clipboard?.writeText(dm.post_de_la_semaine?.caption_instagram || '')}
                              className="mt-2 text-xs text-vz-teal hover:underline"
                            >
                              Copier la caption
                            </button>
                          </div>
                        )}

                        {dm.post_de_la_semaine.visual_brief && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-1">
                              Brief visuel (prompt photo)
                            </p>
                            <div className="bg-vz-bg-alt rounded-lg p-3 text-xs font-mono text-vz-ink-soft mb-2">
                              {dm.post_de_la_semaine.visual_brief}
                            </div>
                            <Button onClick={generateVisual} disabled={generatingVisual} size="sm">
                              {generatingVisual ? 'Génération…' : 'Générer le visuel'}
                            </Button>
                          </div>
                        )}

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                          {dm.post_de_la_semaine.best_time_post && (
                            <div>
                              <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-1">
                                Créneau optimal
                              </p>
                              <p className="text-vz-ink-soft">{dm.post_de_la_semaine.best_time_post}</p>
                            </div>
                          )}
                          {dm.post_de_la_semaine.story_idea && (
                            <div>
                              <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-1">
                                Story associée
                              </p>
                              <p className="text-vz-ink-soft">{dm.post_de_la_semaine.story_idea}</p>
                            </div>
                          )}
                        </div>

                        {dm.post_de_la_semaine.carousel_slides && dm.post_de_la_semaine.carousel_slides.length > 0 && (
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-2">
                              Plan du carousel
                            </p>
                            <ol className="space-y-1">
                              {dm.post_de_la_semaine.carousel_slides.map((s, i) => (
                                <li key={i} className="text-sm text-vz-ink-soft flex items-start gap-2">
                                  <span className="font-mono text-vz-teal text-xs">{String(i + 1).padStart(2, '0')}</span>
                                  <span>{s}</span>
                                </li>
                              ))}
                            </ol>
                          </div>
                        )}

                        {dm.post_de_la_semaine.hashtags && dm.post_de_la_semaine.hashtags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {dm.post_de_la_semaine.hashtags.map((h, i) => (
                              <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-vz-teal-soft text-vz-teal-deep font-mono">
                                {h}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                )}

                {dm.actions_de_la_semaine && dm.actions_de_la_semaine.length > 0 && (
                  <Card title="Actions digitales de la semaine" className="mt-4">
                    <ul className="space-y-2">
                      {dm.actions_de_la_semaine.map((a, i) => (
                        <li key={i} className="flex items-start gap-3 text-sm">
                          <span className="h-6 w-6 rounded-full bg-vz-teal/10 text-vz-teal flex items-center justify-center text-xs font-semibold flex-shrink-0">
                            {i + 1}
                          </span>
                          <span className="text-vz-ink-soft">{a}</span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
              </section>
            )}

            {/* ─── PARTIE 2 — Direction retail · Note de période ─── */}
            {rd && (
              <section className="border-t border-vz-line pt-8">
                <div className="flex items-baseline justify-between mb-3">
                  <div>
                    <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
                      Partie 2 · Direction régionale retail
                    </p>
                    <h2 className="text-2xl font-display font-semibold text-black mt-1">
                      Note de la période
                    </h2>
                  </div>
                </div>
                {rd.persona && (
                  <p className="text-sm text-vz-ink-mute mb-4 italic">— {rd.persona}</p>
                )}

                {rd.conjoncture_mois_dernier && (
                  <Card title="Conjoncture du mois dernier — retail mode France">
                    <p className="text-sm text-vz-ink-soft leading-relaxed">{rd.conjoncture_mois_dernier}</p>
                  </Card>
                )}

                {rd.tendance_3_mois && rd.tendance_3_mois.length > 0 && (
                  <Card title="Tendances des 3 prochains mois" className="mt-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {rd.tendance_3_mois.map((m, i) => (
                        <div key={i} className="bg-vz-bg rounded-lg p-4 border border-vz-line">
                          <p className="text-[10px] uppercase tracking-[0.22em] text-vz-teal font-medium mb-1">
                            {m.mois}
                          </p>
                          <p className="text-sm text-vz-ink-soft leading-relaxed">{m.tendance}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {rd.evenements_majeurs && rd.evenements_majeurs.length > 0 && (
                  <Card title="Événements majeurs · Calendrier national" className="mt-4">
                    <div className="space-y-2">
                      {rd.evenements_majeurs.map((e, i) => (
                        <div key={i} className="flex items-start gap-3 text-sm border-b border-vz-line pb-2 last:border-0 last:pb-0">
                          <span className="font-mono text-vz-teal font-medium flex-shrink-0 w-16">{e.date}</span>
                          <div className="flex-1">
                            <p className="font-medium text-black">{e.evenement}</p>
                            <p className="text-vz-ink-soft text-xs mt-0.5">Impact : {e.impact}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {rd.recommandations_boutique && rd.recommandations_boutique.length > 0 && (
                  <Card title="Recommandations pour la boutique" className="mt-4">
                    <ol className="space-y-3">
                      {rd.recommandations_boutique.map((a, i) => (
                        <li key={i} className="flex items-start gap-3 rounded-xl bg-white border border-vz-line px-4 py-3">
                          <span className="h-7 w-7 rounded-full bg-vz-teal text-white flex items-center justify-center text-sm font-semibold flex-shrink-0">
                            {i + 1}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="font-medium text-black">{a.action}</p>
                            {a.impact && <p className="text-sm text-vz-ink-soft mt-0.5">Impact : {a.impact}</p>}
                            {a.priorite && (
                              <span className={`inline-block mt-1 text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-full uppercase ${PRIO_COLOR[a.priorite.toLowerCase()] || 'bg-gray-100 text-gray-600'}`}>
                                {a.priorite}
                              </span>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </Card>
                )}

                {rd.kpi_cibles && (
                  <Card title="KPI cibles · 30 jours" className="mt-4">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {Object.entries(rd.kpi_cibles).map(([k, v]) => (
                        <div key={k} className="rounded-xl bg-vz-bg px-4 py-3">
                          <p className="text-[11px] uppercase tracking-wider text-vz-ink-mute">
                            {k.replace(/_/g, ' ')}
                          </p>
                          <p className="font-display font-semibold text-lg text-black mt-0.5">
                            {typeof v === 'number' ? v.toLocaleString('fr-FR') : String(v)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </section>
            )}

            <p className="text-xs text-vz-ink-mute text-center">
              {report?.generated_at ? `Généré le ${new Date(report.generated_at).toLocaleString('fr-FR')}` : 'Rapport généré par Claude'}
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
