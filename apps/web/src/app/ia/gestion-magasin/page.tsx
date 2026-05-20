'use client';

/**
 * Audit boutique — persona Responsable de magasin.
 *
 * Affiche les KPI de santé du module d'entrée produit (couverture photo,
 * analyse IA, zones, dates) + le diagnostic narratif de la persona. Source :
 * GET /api/ai/persona/store-ops (régénération manuelle disponible).
 */

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface Metrics {
  active_total: number;
  en_stock: number;
  en_magasin: number;
  sans_photo: number;
  pct_sans_photo: number;
  sans_date_entree: number;
  sans_zone_en_rayon: number;
  sans_date_rayon: number;
  champs_incomplets: number;
  pct_champs_incomplets: number;
  analyse_ia: number;
  pct_analyse_ia: number;
  stock_stagnant: number;
  stagnant_days: number;
}

interface Action {
  priorite: string;
  action: string;
  impact: string;
}

interface Audit {
  persona: string;
  diagnostic: string;
  points_forts: string[];
  points_faibles: string[];
  actions_prioritaires: Action[];
  note_sur_module: string;
}

interface Report {
  generated_at: string;
  ai_generated: boolean;
  metrics: Metrics;
  audit: Audit;
}

const PRIO_COLOR: Record<string, string> = {
  haute: 'bg-vz-accent-soft text-vz-accent',
  moyenne: 'bg-vz-teal-soft text-vz-teal-deep',
  basse: 'bg-vz-bg-alt text-vz-ink-mute',
  faible: 'bg-vz-bg-alt text-vz-ink-mute',
};

function Tile({ label, value, hint, tone = 'default' }: { label: string; value: string; hint?: string; tone?: 'default' | 'good' | 'warn' }) {
  const toneCls = tone === 'good' ? 'text-vz-teal' : tone === 'warn' ? 'text-amber-600' : 'text-vz-ink';
  return (
    <div className="rounded-xl border border-vz-line bg-white p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${toneCls}`}>{value}</p>
      {hint && <p className="text-xs text-gray-400 mt-0.5">{hint}</p>}
    </div>
  );
}

export default function StoreOpsAuditPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/ai/persona/store-ops');
      if (!res.ok) throw new Error('failed');
      setReport(await res.json());
    } catch {
      setError("L'audit n'a pas pu être chargé.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const regenerate = async () => {
    if (regenerating) return;
    setRegenerating(true);
    setError(null);
    try {
      const res = await api.post('/api/ai/persona/store-ops/regenerate', {});
      if (!res.ok) throw new Error('failed');
      setReport(await res.json());
    } catch {
      setError("L'audit n'a pas pu être régénéré.");
    } finally {
      setRegenerating(false);
    }
  };

  const m = report?.metrics;
  const a = report?.audit;

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

        <div className="rounded-3xl bg-vz-ink p-6 md:p-8 text-white shadow-vz-soft mb-6 relative overflow-hidden">
          <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
          <div className="relative z-10 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-90">
                Persona · Responsable de magasin
              </p>
              <h1 className="text-3xl md:text-4xl font-display font-semibold mt-1">Audit boutique</h1>
              <p className="text-sm opacity-90 mt-1 max-w-xl">
                Audit du module d&apos;entrée produit : couverture photo, analyse IA,
                affectation en zone, dates d&apos;entrée et de mise en rayon.
              </p>
              {a?.persona && <p className="text-xs opacity-75 mt-3 italic">{a.persona}</p>}
            </div>
            <Button onClick={regenerate} disabled={regenerating || loading} variant="secondary">
              {regenerating ? 'Analyse…' : 'Régénérer l\'audit'}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-vz-accent-soft bg-vz-accent-soft text-vz-accent px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-16">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-vz-teal" />
          </div>
        )}

        {!loading && m && (
          <>
            {/* KPI tiles */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <Tile label="Articles actifs" value={String(m.active_total)} hint={`${m.en_stock} stock · ${m.en_magasin} magasin`} />
              <Tile label="Avec analyse IA" value={`${m.pct_analyse_ia}%`} hint={`${m.analyse_ia} articles`} tone={m.pct_analyse_ia >= 60 ? 'good' : 'warn'} />
              <Tile label="Sans photo" value={String(m.sans_photo)} hint={`${m.pct_sans_photo}% du parc`} tone={m.sans_photo === 0 ? 'good' : 'warn'} />
              <Tile label="En rayon sans zone" value={String(m.sans_zone_en_rayon)} tone={m.sans_zone_en_rayon === 0 ? 'good' : 'warn'} />
              <Tile label="Sans date d'entrée" value={String(m.sans_date_entree)} tone={m.sans_date_entree === 0 ? 'good' : 'warn'} />
              <Tile label="Sans date de rayon" value={String(m.sans_date_rayon)} tone={m.sans_date_rayon === 0 ? 'good' : 'warn'} />
              <Tile label="Fiches incomplètes" value={String(m.champs_incomplets)} hint={`${m.pct_champs_incomplets}%`} tone={m.pct_champs_incomplets <= 25 ? 'good' : 'warn'} />
              <Tile label="Stock dormant" value={String(m.stock_stagnant)} hint={`> ${m.stagnant_days} j`} tone={m.stock_stagnant === 0 ? 'good' : 'warn'} />
            </div>

            {a && (
              <div className="space-y-4">
                <Card title="Diagnostic">
                  <p className="text-sm text-gray-700 leading-relaxed">{a.diagnostic}</p>
                  {!report?.ai_generated && (
                    <p className="text-xs text-gray-400 mt-2 italic">
                      Diagnostic généré à partir des métriques (clé IA absente — analyse Claude indisponible).
                    </p>
                  )}
                </Card>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card title="Points forts">
                    {a.points_forts.length === 0 ? (
                      <p className="text-sm text-gray-400">—</p>
                    ) : (
                      <ul className="space-y-2">
                        {a.points_forts.map((p, i) => (
                          <li key={i} className="text-sm text-gray-700 flex gap-2">
                            <span className="text-vz-teal">✓</span> {p}
                          </li>
                        ))}
                      </ul>
                    )}
                  </Card>
                  <Card title="Points à corriger">
                    {a.points_faibles.length === 0 ? (
                      <p className="text-sm text-gray-400">Rien à signaler.</p>
                    ) : (
                      <ul className="space-y-2">
                        {a.points_faibles.map((p, i) => (
                          <li key={i} className="text-sm text-gray-700 flex gap-2">
                            <span className="text-amber-500">!</span> {p}
                          </li>
                        ))}
                      </ul>
                    )}
                  </Card>
                </div>

                {a.actions_prioritaires.length > 0 && (
                  <Card title="Actions prioritaires">
                    <div className="space-y-3">
                      {a.actions_prioritaires.map((act, i) => (
                        <div key={i} className="flex items-start gap-3">
                          <span className={`text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap ${PRIO_COLOR[act.priorite] || PRIO_COLOR.faible}`}>
                            {act.priorite}
                          </span>
                          <div>
                            <p className="text-sm text-gray-800 font-medium">{act.action}</p>
                            <p className="text-xs text-gray-500">{act.impact}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {a.note_sur_module && (
                  <Card title="Avis sur le parcours d'entrée">
                    <p className="text-sm text-gray-700 leading-relaxed">{a.note_sur_module}</p>
                  </Card>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
