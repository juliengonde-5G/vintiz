'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Card from '@/components/ui/Card';
import RecoCard, { type RecoCardData } from './RecoCard';
import SeasonTimeline from './SeasonTimeline';
import FashionTrendsWidget, { type FashionSignal } from './FashionTrendsWidget';
import { api } from '@/lib/api';

// Persistance locale des recos « reportées 7j » / « pourquoi pas ».
// Pas de round-trip backend pour l'instant : c'est un tri visuel côté
// manager. Si une décision doit être journalisée plus tard (analytics IA),
// on remplacera ce store par un POST.
const RECO_HIDE_KEY = 'vintiz.recos.hidden';
type HiddenEntry = { id: string; until: number }; // until = epoch ms ; 0 = permanent

function readHidden(): HiddenEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(RECO_HIDE_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw) as HiddenEntry[];
    const now = Date.now();
    return list.filter((e) => e.until === 0 || e.until > now);
  } catch { return []; }
}
function writeHidden(list: HiddenEntry[]): void {
  if (typeof window === 'undefined') return;
  try { window.localStorage.setItem(RECO_HIDE_KEY, JSON.stringify(list)); } catch { /* silent */ }
}

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
  const router = useRouter();
  const [sub, setSub] = useState<SubTab>('recos');

  // --- Recos data (built from /api/ai/trends top items) ---
  const [recos, setRecos] = useState<RecoCardData[]>([]);
  const [loadingRecos, setLoadingRecos] = useState(false);
  const [hidden, setHidden] = useState<HiddenEntry[]>([]);

  // Charge les pièces masquées au montage (reportées 7j ou rejetées).
  useEffect(() => { setHidden(readHidden()); }, []);

  const visibleRecos = useMemo(() => {
    const hiddenIds = new Set(hidden.map((h) => h.id));
    return recos.filter((r) => !hiddenIds.has(r.product_id));
  }, [recos, hidden]);

  // « Accepter » : ouvrir la fiche produit pour passer à l'acte
  // (déplacement vitrine, etc.). Pas de side-effect IA pour l'instant.
  const handleAccept = (productId: string) => {
    router.push(`/inventory/${productId}`);
  };

  // « Reporter 7j » : masque la reco pendant 7 jours, puis elle revient.
  const handlePostpone = (productId: string) => {
    const next = [
      ...hidden.filter((h) => h.id !== productId),
      { id: productId, until: Date.now() + 7 * 24 * 3600 * 1000 },
    ];
    writeHidden(next);
    setHidden(next);
  };

  // « Pourquoi pas » : masque définitivement (jusqu'à ce que le manager
  // vide manuellement le localStorage ; à câbler à un endpoint de
  // ``recommendation_dismissed`` quand on saura ce qu'on en fait).
  const handleReject = (productId: string) => {
    const next = [
      ...hidden.filter((h) => h.id !== productId),
      { id: productId, until: 0 },
    ];
    writeHidden(next);
    setHidden(next);
  };

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
      // Endpoint dédié : pièces présentes à actionner aujourd'hui, classées
      // par note. (Avant : /api/ai/trends, qui ne renvoie pas de produits
      // individuels → items toujours vide → "Aucune recommandation".)
      const r = await api.get('/api/ai/daily-recommendations?limit=6');
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
      // La config de scoring expose le calendrier des saisons à plat sous
      // ``season_calendar`` (et non ``season_boost.category_calendar``, qui
      // n'existe pas → "Aucune catégorie configurée" alors qu'il y en a).
      setCalendar(cfg.season_calendar || {});
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
          { key: 'recos', label: '💡 Recommandations', count: visibleRecos.length },
          { key: 'season', label: '📅 Vue saisons', count: Object.keys(calendar).length },
          { key: 'fashion', label: '🌟 Influence fashion', count: fashionSignals.length },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setSub(t.key as SubTab)}
            className={`text-sm px-4 py-2 rounded-lg min-h-0 ${
              sub === t.key ? 'bg-vz-teal text-white' : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
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
          {visibleRecos.map((r) => (
            <RecoCard
              key={r.product_id}
              reco={r}
              onAccept={handleAccept}
              onPostpone={handlePostpone}
              onReject={handleReject}
            />
          ))}
          {!loadingRecos && recos.length > 0 && visibleRecos.length === 0 && (
            <Card className="p-6">
              <p className="text-sm text-gray-500">
                Toutes les recommandations du jour ont été reportées ou écartées.{' '}
                <button
                  type="button"
                  onClick={() => { writeHidden([]); setHidden([]); }}
                  className="text-vz-teal underline"
                >
                  Tout réafficher
                </button>
              </p>
            </Card>
          )}
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
  // orange = score 30-50 : repositionner (vitrine / zone tendance). Pas de
  // démarque — la boutique ne pratique pas la réduction de prix post-shelving.
  if (c.includes('orange') || c.includes('repositi') || c.includes('demarq') || c.includes('démarq')) return 'REPOSITIONNER';
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
