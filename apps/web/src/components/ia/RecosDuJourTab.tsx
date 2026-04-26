'use client';

import React, { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import RecoCard, { type RecoCardData } from './RecoCard';
import SeasonTimeline from './SeasonTimeline';
import FashionTrendsWidget, { type FashionSignal } from './FashionTrendsWidget';
import { api } from '@/lib/api';

type SubTab = 'recos' | 'season' | 'fashion';

/**
 * L2.5 — Quatre vues complémentaires sous l'onglet "Recos du jour" :
 *  - recos : carrousel de RecoCard (ordre = urgence décroissante)
 *  - season : matrice catégorie × 12 mois avec stock + alerte fin de saison
 *  - fashion : couleurs + coupes + marques en hausse (signaux externes)
 *
 * La 4e vue ("Vitrine de la semaine") reste accessible sous l'onglet
 * "Mapping Boutique" et sera intégrée dans une itération suivante.
 */
export default function RecosDuJourTab() {
  const [sub, setSub] = useState<SubTab>('recos');

  // --- Recos data (built from /api/ai/trends top items) ---
  const [recos, setRecos] = useState<RecoCardData[]>([]);
  const [loadingRecos, setLoadingRecos] = useState(false);

  // --- Season data (from scoring config category_calendar) ---
  const [calendar, setCalendar] = useState<Record<string, number[]>>({});
  const [stockByCategory, setStockByCategory] = useState<Record<string, number>>({});

  // --- Fashion signals (placeholder — backend service à brancher en L4 v2.5) ---
  const [fashionSignals, setFashionSignals] = useState<FashionSignal[]>([]);

  useEffect(() => {
    loadRecos();
    loadCalendar();
    loadFashionSignals();
  }, []);

  const loadRecos = async () => {
    setLoadingRecos(true);
    try {
      // Reuse the trends endpoint already mounted — top products with action.
      const r = await api.get('/api/ai/trends?limit=6');
      if (!r.ok) return;
      const data = await r.json();
      const items = data.items || data.products || [];
      const cards: RecoCardData[] = items.map((it: any) => {
        const action = mapAction(it.action_color || it.action || '');
        const reasons = buildReasons(it);
        return {
          product_id: it.product_id || it.id,
          product_name: it.product_name || it.name,
          product_thumb: it.photo_url,
          score: it.score ?? it.total_score,
          days_on_shelf: it.days_on_shelf,
          action,
          reasons,
          similar_products: [],
        };
      });
      setRecos(cards);
    } catch { /* silent */ }
    setLoadingRecos(false);
  };

  const loadCalendar = async () => {
    try {
      const r = await api.get('/api/admin/scoring-config');
      if (!r.ok) return;
      const cfg = await r.json();
      setCalendar(cfg.season_boost?.category_calendar || {});
    } catch { /* silent */ }
  };

  const loadFashionSignals = async () => {
    // Placeholder — until service fashion_watch.py is wired (L4 v2.5).
    // Show a hint dataset to demonstrate the UI shape.
    setFashionSignals([
      { term: 'bordeaux', category: 'color', velocity: 23, source: 'Vinted public' },
      { term: 'écru', category: 'color', velocity: 18, source: 'Google Trends' },
      { term: 'kaki', category: 'color', velocity: 12, source: 'Vinted public' },
      { term: 'oversize', category: 'cut', velocity: 31, source: 'Instagram' },
      { term: 'cintré', category: 'cut', velocity: 14, source: 'Google Trends' },
      { term: 'fluide', category: 'cut', velocity: 9, source: 'Google Trends' },
      { term: 'Sandro', category: 'brand', velocity: 27, source: 'Vinted public' },
      { term: 'Maje', category: 'brand', velocity: 18, source: 'Vinted public' },
    ]);
  };

  return (
    <div className="space-y-4">
      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-gray-200 pb-2">
        {[
          { key: 'recos', label: '💡 Recommandations', count: recos.length },
          { key: 'season', label: '📅 Vue saisons', count: Object.keys(calendar).length },
          { key: 'fashion', label: '🌟 Influence fashion', count: fashionSignals.length },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setSub(t.key as SubTab)}
            className={`text-sm px-4 py-2 rounded-lg min-h-0 ${
              sub === t.key ? 'bg-teal text-white' : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
            }`}
          >
            {t.label}
            {t.count > 0 && (
              <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full ${
                sub === t.key ? 'bg-white/30 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {sub === 'recos' && (
        <div className="space-y-4">
          {loadingRecos && <p className="text-sm text-gray-400">Chargement…</p>}
          {!loadingRecos && recos.length === 0 && (
            <Card>
              <p className="text-sm text-gray-500">
                Aucune recommandation aujourd'hui — patientez quelques jours pour que l'historique s'enrichisse.
              </p>
            </Card>
          )}
          {recos.map((r) => (
            <RecoCard
              key={r.product_id}
              reco={r}
              onAccept={(id) => console.log('Accept', id)}
              onPostpone={(id) => console.log('Postpone', id)}
              onReject={(id) => console.log('Reject', id)}
            />
          ))}
        </div>
      )}

      {sub === 'season' && (
        <Card title="Calendrier des saisons">
          <SeasonTimeline categoryCalendar={calendar} stockByCategory={stockByCategory} />
        </Card>
      )}

      {sub === 'fashion' && (
        <Card title="Influence fashion (signaux externes)">
          <FashionTrendsWidget signals={fashionSignals} />
        </Card>
      )}
    </div>
  );
}

function mapAction(raw: string): RecoCardData['action'] {
  const c = (raw || '').toLowerCase();
  if (c.includes('red') || c.includes('retir')) return 'RETIRER';
  if (c.includes('orange') || c.includes('demarq') || c.includes('démarq')) return 'DEMARQUER';
  if (c.includes('yellow') || c.includes('avant')) return 'METTRE_EN_AVANT';
  return 'MAINTENIR';
}

function buildReasons(it: any): string[] {
  const reasons: string[] = [];
  if (it.score) reasons.push(`Score ${Number(it.score).toFixed(0)}/100`);
  if (it.days_on_shelf != null) reasons.push(`En rayon depuis ${it.days_on_shelf} jours`);
  if (it.brand) reasons.push(`Marque : ${it.brand}`);
  if (it.color) reasons.push(`Couleur ${it.color}`);
  return reasons.slice(0, 3);
}
