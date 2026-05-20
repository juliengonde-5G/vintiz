'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import CompanionHero from '@/components/ai/CompanionHero';
import RecosDuJourTab from '@/components/ia/RecosDuJourTab';
import { api } from '@/lib/api';
import { formatCurrency, mediaUrl } from '@/lib/format';

interface TrendItem {
  product_id: string;
  product_name: string;
  barcode: string;
  score: number;
  max_score: number;
  factors: Record<string, number>;
}

interface MarkdownItem {
  product_id: string;
  product_name: string;
  barcode: string;
  current_price: number;
  suggested_price: number;
  discount_percent: number;
  days_on_shelf: number;
  weeks_on_shelf: number;
  urgency: string;
  category: string | null;
}

interface ZoneStat {
  zone_id: string;
  zone_name: string;
  description: string;
  capacity: number;
  product_count: number;
  occupancy_percent: number;
  total_value: number;
  avg_trend_score: number;
}

interface VisionResult {
  type?: string;
  couleur?: string;
  matiere?: string;
  marque?: string;
  taille?: string;
  etat?: string;
  saison?: string;
  style?: string;
  description?: string;
  gamme_estimee?: string;
  confiance?: number;
  error?: string;
}

interface AIRecoAction {
  action: string;
  product_name: string;
  from_zone?: string;
  to_zone?: string;
  reason: string;
}

interface AIRecoZone {
  zone: string;
  theme_suggere: string;
  conseil: string;
}

interface AIRecoResult {
  resume?: string;
  recommendations?: AIRecoAction[];
  zone_suggestions?: AIRecoZone[];
  error?: string;
}


// ---------------------------------------------------------------------------
// Visual floor plan of the boutique (Lot N°2, ~184 m² utiles).
// Zones are positioned to match the real layout (plan.jpg) :
//   - Petits Prix 1/2 + Extra 1/2 sur le mur du fond (top)
//   - Chaussures F + cabines + Portants Standards 1/2 cote gauche/centre
//   - Chaussures H + Hommes + Tendance + Vitrine sur la facade (bottom)
//   - Entrée à droite
// Coordinates use a 380x380 viewBox (cf. <svg viewBox="0 0 390 380">).
// ---------------------------------------------------------------------------

const ZONE_LAYOUT: Record<string, { x: number; y: number; w: number; h: number; label: string; shortLabel: string }> = {
  'Petits Prix 1':         { x: 282, y: 10,  w: 96,  h: 46,  label: 'Petits Prix 1',         shortLabel: 'PP1' },
  'Petits Prix 2':         { x: 180, y: 10,  w: 98,  h: 46,  label: 'Petits Prix 2',         shortLabel: 'PP2' },
  'Extra 1':               { x: 92,  y: 14,  w: 84,  h: 50,  label: 'Extra 1',               shortLabel: 'E1' },
  'Extra 2':               { x: 50,  y: 70,  w: 50,  h: 80,  label: 'Extra 2',               shortLabel: 'E2' },
  'Chaussures F':          { x: 50,  y: 158, w: 50,  h: 64,  label: 'Chaussures F',          shortLabel: 'Ch.F' },
  'Portants Standards 1':  { x: 170, y: 108, w: 86,  h: 64,  label: 'Portants Standards 1',  shortLabel: 'PS1' },
  'Portants Standards 2':  { x: 86,  y: 222, w: 86,  h: 64,  label: 'Portants Standards 2',  shortLabel: 'PS2' },
  'Chaussures H':          { x: 88,  y: 304, w: 56,  h: 56,  label: 'Chaussures H',          shortLabel: 'Ch.H' },
  'Hommes':                { x: 150, y: 314, w: 70,  h: 50,  label: 'Hommes',                shortLabel: 'H' },
  'Tendance':              { x: 226, y: 304, w: 92,  h: 56,  label: 'Tendance',              shortLabel: 'Tend' },
  'Vitrine':               { x: 324, y: 304, w: 50,  h: 56,  label: 'Vitrine',               shortLabel: 'Vit' },
};

function zoneOccupancyFill(percent: number): string {
  if (percent > 80) return '#FEE2E2';  // red-100
  if (percent > 50) return '#FEF9C3';  // yellow-100
  if (percent > 0)  return '#DCFCE7';  // green-100
  return '#F3F4F6';                     // gray-100
}

function zoneOccupancyStroke(percent: number): string {
  if (percent > 80) return '#EF4444';  // red-500
  if (percent > 50) return '#EAB308';  // yellow-500
  if (percent > 0)  return '#22C55E';  // green-500
  return '#9CA3AF';                     // gray-400
}

function FloorPlan({ zones, onSelectZone, selectedZoneId }: {
  zones: ZoneStat[];
  onSelectZone: (z: ZoneStat | null) => void;
  selectedZoneId: string | null;
}) {
  const zoneMap = new Map(zones.map(z => [z.zone_name, z]));

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox="0 0 390 380" className="w-full max-w-[700px] mx-auto" style={{ minWidth: 350 }}>
        {/* Background / building outline */}
        <rect x="5" y="5" width="370" height="365" rx="8" fill="#FFF5F8" stroke="#E8B4D0" strokeWidth="2" />

        {/* Facade / vitrine line (bottom) */}
        <text x="195" y="378" textAnchor="middle" fontSize="9" fill="#9CA3AF" fontFamily="sans-serif">
          Facade — Vitrine
        </text>

        {/* Entry arrow — entrée à droite */}
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="4" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#2A8B8B" />
          </marker>
        </defs>
        <line x1="385" y1="200" x2="378" y2="200" stroke="#2A8B8B" strokeWidth="2" markerEnd="url(#arrowhead)" />
        <text x="378" y="192" textAnchor="end" fontSize="8" fill="#2A8B8B" fontFamily="sans-serif" fontWeight="600">
          ENTREE
        </text>

        {/* Cabines essayage (left wall) */}
        <rect x="20" y="158" width="22" height="58" rx="3" fill="#F3E8FF" stroke="#A78BFA" strokeWidth="1" strokeDasharray="2 2" />
        <text x="31" y="190" textAnchor="middle" fontSize="6" fill="#6B7280" fontFamily="sans-serif">Cabines</text>

        {/* Zone rectangles */}
        {Object.entries(ZONE_LAYOUT).map(([name, rect]) => {
          const zoneData = zoneMap.get(name);
          const occ = zoneData?.occupancy_percent ?? 0;
          const isSelected = zoneData?.zone_id === selectedZoneId;
          return (
            <g
              key={name}
              onClick={() => onSelectZone(zoneData || null)}
              className="cursor-pointer"
              role="button"
              tabIndex={0}
            >
              <rect
                x={rect.x}
                y={rect.y}
                width={rect.w}
                height={rect.h}
                rx={6}
                fill={zoneOccupancyFill(occ)}
                stroke={isSelected ? '#2A8B8B' : zoneOccupancyStroke(occ)}
                strokeWidth={isSelected ? 3 : 1.5}
                opacity={0.95}
              />
              {/* Zone short label */}
              <text
                x={rect.x + rect.w / 2}
                y={rect.y + rect.h / 2 - 6}
                textAnchor="middle"
                fontSize="10"
                fontWeight="600"
                fill="#1A1A1A"
                fontFamily="sans-serif"
              >
                {rect.shortLabel}
              </text>
              {/* Product count / capacity */}
              <text
                x={rect.x + rect.w / 2}
                y={rect.y + rect.h / 2 + 8}
                textAnchor="middle"
                fontSize="9"
                fill="#6B7280"
                fontFamily="sans-serif"
              >
                {zoneData ? `${zoneData.product_count}/${zoneData.capacity}` : '0/0'}
              </text>
              {/* Occupancy badge */}
              {zoneData && zoneData.product_count > 0 && (
                <>
                  <rect
                    x={rect.x + rect.w / 2 - 14}
                    y={rect.y + rect.h / 2 + 14}
                    width={28}
                    height={14}
                    rx={7}
                    fill={zoneOccupancyStroke(occ)}
                    opacity={0.2}
                  />
                  <text
                    x={rect.x + rect.w / 2}
                    y={rect.y + rect.h / 2 + 24}
                    textAnchor="middle"
                    fontSize="8"
                    fontWeight="600"
                    fill={zoneOccupancyStroke(occ)}
                    fontFamily="sans-serif"
                  >
                    {occ}%
                  </text>
                </>
              )}
            </g>
          );
        })}

        {/* Legend */}
        <g transform="translate(10, 370)">
          <rect x="0" y="-8" width="8" height="8" rx="2" fill="#DCFCE7" stroke="#22C55E" strokeWidth="1" />
          <text x="12" y="-1" fontSize="7" fill="#6B7280" fontFamily="sans-serif">&lt;50%</text>
          <rect x="50" y="-8" width="8" height="8" rx="2" fill="#FEF9C3" stroke="#EAB308" strokeWidth="1" />
          <text x="62" y="-1" fontSize="7" fill="#6B7280" fontFamily="sans-serif">50-80%</text>
          <rect x="108" y="-8" width="8" height="8" rx="2" fill="#FEE2E2" stroke="#EF4444" strokeWidth="1" />
          <text x="120" y="-1" fontSize="7" fill="#6B7280" fontFamily="sans-serif">&gt;80%</text>
        </g>
      </svg>
    </div>
  );
}

function urgencyColor(u: string) {
  if (u === 'critique') return 'bg-red-100 text-red-700';
  if (u === 'haute') return 'bg-orange-100 text-orange-700';
  if (u === 'moyenne') return 'bg-yellow-100 text-yellow-700';
  return 'bg-gray-100 text-gray-600';
}

function scoreColor(score: number) {
  if (score >= 70) return 'text-green-600';
  if (score >= 40) return 'text-yellow-600';
  return 'text-red-600';
}

interface ChecklistItem {
  type: string;
  priority: string;
  title: string;
  description: string;
  products?: Array<{ id?: string; name: string; barcode?: string; sale_price?: number; trend_score?: number }>;
}

interface ZoneProductItem {
  id: string;
  barcode: string;
  name: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  sale_price: number;
  status: string;
  trend_score: number | null;
  photo_url: string | null;
}

interface WeeklyChecklist {
  week: number;
  year: number;
  generated_at: string;
  checklist: ChecklistItem[];
}

interface TrendArticle {
  id: string;
  title: string;
  key_words?: string[];
  source: string;
  article: string;
  visual_prompt?: string;
  categories?: string[];
  colors?: string[];
  match_keywords?: string[];
}

interface TrendBrand {
  name: string;
  tier?: string;
  why?: string;
  logo_query?: string;
}

interface InventoryMatch {
  id: string;
  name: string;
  barcode: string;
  price_eur: number;
  brand?: string | null;
  size?: string | null;
  color?: string | null;
  photo_url?: string | null;
}

interface TrendsMode {
  week: number;
  year: number;
  season?: string;
  generated_at: string;
  editorial_intro?: string;
  channels: {
    reseaux_sociaux: { summary: string; top_items: string[]; colors: string[] };
    vinted: { summary: string; top_categories: string[]; price_trends: string };
    retail: { summary: string; key_trends: string[] };
  };
  trends?: TrendArticle[];
  brands?: TrendBrand[];
  inventory_matches?: Record<string, InventoryMatch[]>;
}


export default function IAPage() {
  const [tab, setTab] = useState<'recos_du_jour' | 'checklist' | 'fashion_book' | 'trends_scoring'>('recos_du_jour');
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [markdowns, setMarkdowns] = useState<MarkdownItem[]>([]);
  const [zones, setZones] = useState<ZoneStat[]>([]);
  const [visionResult, setVisionResult] = useState<VisionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [aiReco, setAiReco] = useState<AIRecoResult | null>(null);
  const [recoLoading, setRecoLoading] = useState(false);
  const [selectedZone, setSelectedZone] = useState<ZoneStat | null>(null);
  const [zoneProducts, setZoneProducts] = useState<ZoneProductItem[]>([]);
  const [zoneProductsLoading, setZoneProductsLoading] = useState(false);

  // Checklist states
  const [checklist, setChecklist] = useState<WeeklyChecklist | null>(null);
  const [checklistLoading, setChecklistLoading] = useState(false);
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});

  // Tendances mode states
  const [trendsMode, setTrendsMode] = useState<TrendsMode | null>(null);
  const [trendsModeLoading, setTrendsModeLoading] = useState(false);
  // Legacy channel tab state retained for /api/ai/trends fallback shape — unused with the editorial rewrite below.
  // (intentionally removed — using <details> for raw channels)

  // Load checklist checkbox states from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('vintiz_checklist_checks');
      if (saved) setCheckedItems(JSON.parse(saved));
    } catch { /* ignore */ }
  }, []);

  const toggleChecklistItem = (key: string) => {
    setCheckedItems((prev: Record<string, boolean>) => {
      const updated = { ...prev, [key]: !prev[key] };
      try { localStorage.setItem('vintiz_checklist_checks', JSON.stringify(updated)); } catch { /* ignore */ }
      return updated;
    });
  };

  const loadTrends = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/ai/trends/scores?limit=30');
      if (res.ok) setTrends(await res.json());
    } catch { setError('Erreur chargement tendances'); }
    setLoading(false);
  }, []);

  const loadMarkdowns = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/ai/pricing/markdowns');
      if (res.ok) {
        const data = await res.json();
        setMarkdowns(data.suggestions || []);
      }
    } catch { setError('Erreur chargement demarques'); }
    setLoading(false);
  }, []);

  const loadZones = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/ai/mapping/zones');
      if (res.ok) {
        const data = await res.json();
        setZones(data);
      } else if (res.status === 404) {
        const initRes = await api.post('/api/ai/mapping/init-zones', {});
        if (initRes.ok) {
          const zonesRes = await api.get('/api/ai/mapping/zones');
          if (zonesRes.ok) setZones(await zonesRes.json());
        }
      }
    } catch { setError('Erreur chargement zones'); }
    setLoading(false);
  }, []);

  const loadChecklist = useCallback(async (forceRefresh = false) => {
    setChecklistLoading(true);
    try {
      const url = forceRefresh ? '/api/ai/weekly-checklist?force_refresh=true' : '/api/ai/weekly-checklist';
      const res = await api.get(url);
      if (res.ok) setChecklist(await res.json());
      else setError('Erreur chargement checklist');
    } catch { setError('Erreur chargement checklist'); }
    setChecklistLoading(false);
  }, []);

  const loadTrendsMode = useCallback(async (forceRefresh = false) => {
    setTrendsModeLoading(true);
    try {
      const url = forceRefresh ? '/api/ai/trends?force_refresh=true' : '/api/ai/trends';
      const res = await api.get(url);
      if (res.ok) setTrendsMode(await res.json());
      else setError('Erreur chargement tendances');
    } catch { setError('Erreur chargement tendances'); }
    setTrendsModeLoading(false);
  }, []);

  const loadZoneProducts = useCallback(async (zoneId: string) => {
    setZoneProductsLoading(true);
    setZoneProducts([]);
    try {
      const res = await api.get(`/api/ai/mapping/zones/${zoneId}/products`);
      if (res.ok) {
        const data = await res.json();
        setZoneProducts(data.products || []);
      }
    } catch { /* silent */ }
    setZoneProductsLoading(false);
  }, []);


  useEffect(() => {
    if (tab === 'trends_scoring') loadTrends();
    else if (tab === 'checklist') loadChecklist();
    else if (tab === 'fashion_book') loadTrendsMode();
  }, [tab, loadTrends, loadChecklist, loadTrendsMode]);

  const refreshScores = async () => {
    setRefreshing(true);
    try {
      const res = await api.post('/api/ai/trends/refresh', {});
      if (res.ok) {
        await loadTrends();
      }
    } catch { setError('Erreur rafraichissement'); }
    setRefreshing(false);
  };

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setVisionResult(null);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.upload('/api/ai/vision/analyze', fd);
      if (res.ok) {
        setVisionResult(await res.json());
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || 'Erreur analyse photo');
      }
    } catch {
      setError('Erreur envoi photo');
    }
    setLoading(false);
  };

  const generateRecommendations = async () => {
    setRecoLoading(true);
    setAiReco(null);
    try {
      const res = await api.post('/api/ai/mapping/recommendations', {});
      if (res.ok) setAiReco(await res.json());
      else setError('Erreur generation recommandations');
    } catch { setError('Erreur IA'); }
    setRecoLoading(false);
  };

  const initZones = async () => {
    setLoading(true);
    try {
      const res = await api.post('/api/ai/mapping/init-zones', {});
      if (res.ok) await loadZones();
    } catch { setError('Erreur initialisation zones'); }
    setLoading(false);
  };

  const handleSelectZone = (z: ZoneStat | null) => {
    setSelectedZone(z);
    if (z) loadZoneProducts(z.zone_id);
    else setZoneProducts([]);
  };

  const tabs = [
    { key: 'recos_du_jour' as const, label: 'Recos du jour', icon: '💡' },
    { key: 'checklist' as const, label: 'Checklist semaine', icon: '✅' },
    { key: 'fashion_book' as const, label: 'Fashion Book', icon: '👗' },
    { key: 'trends_scoring' as const, label: 'Trends scoring', icon: '📈' },
  ];

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 max-w-7xl">
        <CompanionHero />

        {error && (
          <div className="mb-4 p-3 bg-vz-accent-soft text-vz-accent rounded-lg text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        {/* Skills */}
        <div className="mb-4">
          <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
            Tes outils IA
          </p>
          <h2 className="font-display font-semibold text-lg text-black mt-0.5">
            Explorer un domaine
          </h2>
        </div>
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl min-h-[48px] whitespace-nowrap transition-colors ${
                tab === t.key
                  ? 'bg-vz-teal text-white font-medium shadow-vz-soft'
                  : 'bg-white text-gray-600 hover:bg-vz-teal-soft hover:text-vz-teal border border-gray-100'
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
          <Link
            href="/ia/marketing"
            className="flex items-center gap-2 px-4 py-2 rounded-xl min-h-[48px] whitespace-nowrap bg-vz-teal text-white font-medium shadow-vz-soft hover:shadow-vz-soft transition-all"
          >
            <span>📣</span>
            <span>Rapport marketing</span>
          </Link>
          <Link
            href="/ia/gestion-magasin"
            className="flex items-center gap-2 px-4 py-2 rounded-xl min-h-[48px] whitespace-nowrap bg-white border border-vz-line text-vz-ink font-medium hover:bg-vz-bg-alt transition-all"
          >
            <span>🏬</span>
            <span>Audit boutique</span>
          </Link>
        </div>

        {/* RECOS DU JOUR TAB (L2.5) */}
        {tab === 'recos_du_jour' && (
          <RecosDuJourTab />
        )}

        {/* TRENDS SCORING TAB (renommé Lot 6) */}
        {tab === 'trends_scoring' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-black">Scores de tendance</h2>
              <Button onClick={refreshScores} disabled={refreshing} variant="secondary">
                {refreshing ? 'Calcul...' : 'Recalculer les scores'}
              </Button>
            </div>

            {loading ? (
              <Card><p className="text-gray-400 text-center py-8">Chargement...</p></Card>
            ) : trends.length === 0 ? (
              <Card><p className="text-gray-400 text-center py-8">Aucun produit actif</p></Card>
            ) : (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-3 text-sm font-semibold text-gray-600">#</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600">Produit</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600">Code</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Score</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Vitesse cat.</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Fraicheur</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Prix</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trends.map((t, i) => (
                        <tr key={t.product_id} className="border-b border-gray-50 hover:bg-vz-accent-soft transition-colors cursor-pointer"
                          onClick={() => window.location.href = `/inventory/${t.product_id}`}>
                          <td className="py-3 text-sm text-gray-400">{i + 1}</td>
                          <td className="py-3 text-sm text-black font-medium hover:text-vz-teal">{t.product_name}</td>
                          <td className="py-3 text-sm text-gray-500 font-mono">{t.barcode}</td>
                          <td className={`py-3 text-sm text-right font-bold ${scoreColor(t.score)}`}>
                            {t.score}/{t.max_score}
                          </td>
                          <td className="py-3 text-sm text-right text-gray-600">{t.factors.category_velocity}</td>
                          <td className="py-3 text-sm text-right text-gray-600">{t.factors.freshness}</td>
                          <td className="py-3 text-sm text-right text-gray-600">{t.factors.price_attractiveness}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        )}
        {/* CHECKLIST SEMAINE TAB */}
        {tab === 'checklist' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-black">Checklist de la semaine</h2>
                {checklist && <p className="text-sm text-gray-500">Semaine {checklist.week} — {checklist.year} · Générée le {new Date(checklist.generated_at).toLocaleDateString('fr-FR')}</p>}
                <p className="text-xs text-gray-400 mt-1">Régénérée automatiquement chaque lundi à 9h00 (Paris).</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => loadChecklist(true)} disabled={checklistLoading}
                  className="min-h-[48px] px-4 py-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 text-sm font-medium transition-colors disabled:opacity-50">
                  {checklistLoading ? 'Régénération…' : 'Régénérer manuellement'}
                </button>
              </div>
            </div>
            {checklistLoading ? (
              <Card><div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-vz-teal" /></div></Card>
            ) : !checklist ? (
              <Card><p className="text-gray-400 text-center py-8">Cliquez &quot;Charger&quot; pour afficher la checklist de la semaine.</p></Card>
            ) : (
              <>
                {/* Progress summary */}
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-vz-teal h-2 rounded-full transition-all"
                        style={{ width: `${checklist.checklist.length > 0 ? Math.round(checklist.checklist.filter((_, i) => checkedItems[`${checklist.week}-${checklist.year}-${i}`]).length / checklist.checklist.length * 100) : 0}%` }} />
                    </div>
                  </div>
                  <span className="text-sm font-medium text-gray-700">
                    {checklist.checklist.filter((_, i) => checkedItems[`${checklist.week}-${checklist.year}-${i}`]).length}/{checklist.checklist.length} fait
                  </span>
                </div>
              <div className="space-y-4">
                {checklist.checklist.map((item, i) => {
                  const typeConfig: Record<string, { icon: string; bg: string; border: string }> = {
                    mise_en_avant: { icon: '🎯', bg: 'bg-green-50', border: 'border-green-200' },
                    reduction_prix: { icon: '💰', bg: 'bg-orange-50', border: 'border-orange-200' },
                    vitrine: { icon: '🪟', bg: 'bg-blue-50', border: 'border-blue-200' },
                    commande: { icon: '📦', bg: 'bg-purple-50', border: 'border-purple-200' },
                  };
                  const cfg = typeConfig[item.type] || { icon: '•', bg: 'bg-gray-50', border: 'border-gray-200' };
                  const priorityColor = item.priority === 'haute' ? 'bg-red-100 text-red-700' : item.priority === 'moyenne' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600';
                  const itemKey = `${checklist.week}-${checklist.year}-${i}`;
                  const isDone = !!checkedItems[itemKey];
                  return (
                    <div key={i} className={`rounded-xl border p-4 transition-opacity ${cfg.bg} ${cfg.border} ${isDone ? 'opacity-60' : ''}`}>
                      <div className="flex items-start gap-3">
                        <button
                          onClick={() => toggleChecklistItem(itemKey)}
                          className={`mt-0.5 flex-shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center transition-colors ${isDone ? 'bg-vz-teal border-vz-teal text-white' : 'border-gray-300 hover:border-vz-teal'}`}
                        >
                          {isDone && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>}
                        </button>
                        <span className="text-2xl">{cfg.icon}</span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className={`font-semibold ${isDone ? 'line-through text-gray-400' : 'text-black'}`}>{item.title}</h3>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${priorityColor}`}>{item.priority}</span>
                          </div>
                          <p className="text-sm text-gray-600">{item.description}</p>
                          {item.products && item.products.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {item.products.map((p, j) => (
                                <span key={j} className="text-xs bg-white border border-gray-200 px-2 py-0.5 rounded-full text-gray-700">{p.name}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
          <WeeklyTasksTimeline />
        </div>
        )}

        {/* FASHION BOOK TAB — refonte éditoriale (persona "Camille Berthier") */}
        {tab === 'fashion_book' && (
          <div className="space-y-8">
            {/* Editorial header */}
            <header className="border-b border-vz-line pb-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
                    Fashion Book · {trendsMode?.season || 'Saison en cours'}
                  </p>
                  <h2 className="text-3xl font-display font-semibold text-black mt-2">
                    Le Book de la semaine
                  </h2>
                  {trendsMode && (
                    <p className="text-sm text-vz-ink-mute mt-1">
                      Semaine {trendsMode.week} — {trendsMode.year} · Édité par <em>Camille Berthier</em> ·
                      Actualisé le {new Date(trendsMode.generated_at).toLocaleDateString('fr-FR')}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-vz-ink-mute italic max-w-[200px] text-right hidden md:block">
                    Régénéré automatiquement chaque lundi à 7h30 (Paris).
                  </span>
                  <button onClick={() => loadTrendsMode(true)} disabled={trendsModeLoading}
                    className="min-h-[48px] px-4 py-2 rounded-lg border border-vz-line text-vz-ink hover:bg-white text-sm font-medium transition-colors disabled:opacity-50">
                    {trendsModeLoading ? 'Actualisation…' : 'Régénérer manuellement'}
                  </button>
                </div>
              </div>
              {trendsMode?.editorial_intro && (
                <p className="text-base text-vz-ink-soft mt-5 leading-relaxed font-display italic max-w-3xl">
                  &laquo;&nbsp;{trendsMode.editorial_intro}&nbsp;&raquo;
                </p>
              )}
            </header>

            {trendsModeLoading ? (
              <Card><div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-vz-teal" /></div></Card>
            ) : !trendsMode ? (
              <Card><p className="text-gray-400 text-center py-8">Chargement du Fashion Book…</p></Card>
            ) : (
              <>
                {/* The 5 trend articles */}
                {trendsMode.trends && trendsMode.trends.length > 0 && (
                  <section className="space-y-8">
                    <div className="flex items-baseline justify-between">
                      <h3 className="text-xs tracking-[0.22em] uppercase text-vz-teal font-medium">
                        Tendances clés
                      </h3>
                      <span className="text-xs text-vz-ink-mute">
                        {trendsMode.trends.length} {trendsMode.trends.length > 1 ? 'articles' : 'article'}
                      </span>
                    </div>
                    {trendsMode.trends.map((t, i) => {
                      const matches = trendsMode.inventory_matches?.[t.id] || [];
                      return (
                        <article key={t.id || i} className="grid grid-cols-1 md:grid-cols-3 gap-6 border-b border-vz-line pb-8 last:border-0">
                          {/* Visual / hero */}
                          <div className="md:col-span-1">
                            <div className="aspect-[4/5] rounded-vz-lg overflow-hidden bg-gradient-to-br from-vz-bg-alt to-vz-teal-soft flex items-center justify-center text-[10px] uppercase tracking-[0.22em] text-vz-ink-mute p-4 text-center">
                              {t.visual_prompt ? (
                                <span className="font-mono whitespace-pre-line">{t.visual_prompt}</span>
                              ) : (
                                <span>Visuel à générer</span>
                              )}
                            </div>
                            {t.colors && t.colors.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-3">
                                {t.colors.map((c, j) => (
                                  <span key={j} className="text-[11px] px-2 py-0.5 rounded-full bg-vz-teal-soft text-vz-teal-deep">
                                    {c}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          {/* Article body */}
                          <div className="md:col-span-2">
                            <div className="flex items-center gap-2 text-[10px] tracking-[0.18em] uppercase text-vz-ink-mute mb-2">
                              <span className="font-mono text-vz-teal">N° {String(i + 1).padStart(2, '0')}</span>
                              <span>·</span>
                              <span>Source : {t.source}</span>
                            </div>
                            <h4 className="text-2xl font-display font-semibold text-black leading-tight">
                              {t.title}
                            </h4>
                            {t.key_words && t.key_words.length > 0 && (
                              <p className="text-xs text-vz-ink-mute mt-1">
                                {t.key_words.join(' · ')}
                              </p>
                            )}
                            <p className="text-base text-vz-ink-soft mt-3 leading-relaxed">{t.article}</p>

                            {matches.length > 0 && (
                              <div className="mt-4 p-4 rounded-lg bg-vz-bg border border-vz-line">
                                <div className="flex items-center justify-between mb-3">
                                  <span className="text-[10px] uppercase tracking-[0.18em] text-vz-teal font-medium">
                                    En boutique · {matches.length} pièce{matches.length > 1 ? 's' : ''} matche{matches.length > 1 ? 'nt' : ''} cette tendance
                                  </span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                  {matches.slice(0, 6).map((p) => (
                                    <Link key={p.id} href={`/inventory/${p.id}`} className="group">
                                      <div className="aspect-square rounded-lg overflow-hidden bg-vz-bg-alt flex items-center justify-center">
                                        {p.photo_url ? (
                                          // eslint-disable-next-line @next/next/no-img-element
                                          <img src={mediaUrl(p.photo_url)} alt={p.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                                        ) : (
                                          <span className="text-[10px] text-vz-ink-mute">Sans visuel</span>
                                        )}
                                      </div>
                                      <p className="text-xs text-black mt-1.5 truncate font-medium">{p.brand || p.name}</p>
                                      <p className="text-[11px] text-vz-ink-mute truncate">
                                        {p.size && `T. ${p.size} · `}{p.price_eur.toFixed(0)} €
                                      </p>
                                    </Link>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </article>
                      );
                    })}
                  </section>
                )}

                {/* Trending brands */}
                {trendsMode.brands && trendsMode.brands.length > 0 && (
                  <section className="border-t border-vz-line pt-8">
                    <div className="flex items-baseline justify-between mb-5">
                      <h3 className="text-xs tracking-[0.22em] uppercase text-vz-teal font-medium">
                        Marques tendance
                      </h3>
                      <span className="text-xs text-vz-ink-mute">{trendsMode.brands.length} marques</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                      {trendsMode.brands.map((b, i) => (
                        <div key={i} className="bg-white border border-vz-line rounded-vz-lg p-4 hover:shadow-vz-soft transition-shadow">
                          <div className="h-12 mb-2 flex items-center">
                            {/* Logo placeholder via Google logo search query — opens in a new tab */}
                            <a
                              href={`https://www.google.com/search?q=${encodeURIComponent(b.logo_query || `${b.name} logo`)}&tbm=isch`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-display text-2xl font-semibold text-vz-ink hover:text-vz-teal transition-colors"
                            >
                              {b.name}
                            </a>
                          </div>
                          {b.tier && (
                            <p className="text-[10px] uppercase tracking-[0.18em] text-vz-teal font-medium">
                              {b.tier}
                            </p>
                          )}
                          {b.why && (
                            <p className="text-xs text-vz-ink-soft mt-1.5 leading-relaxed">{b.why}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Legacy channels — collapsed below trends for context */}
                {trendsMode.channels && (
                  <details className="border-t border-vz-line pt-6">
                    <summary className="text-xs tracking-[0.22em] uppercase text-vz-ink-mute font-medium cursor-pointer hover:text-vz-teal">
                      Données brutes · Canaux ↓
                    </summary>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                      <div className="p-4 rounded-lg bg-vz-bg-alt">
                        <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-2">Réseaux sociaux</p>
                        <p className="text-sm text-vz-ink-soft">{trendsMode.channels.reseaux_sociaux.summary}</p>
                      </div>
                      <div className="p-4 rounded-lg bg-vz-bg-alt">
                        <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-2">Vinted</p>
                        <p className="text-sm text-vz-ink-soft">{trendsMode.channels.vinted.summary}</p>
                        <p className="text-xs text-vz-ink-mute mt-1.5">{trendsMode.channels.vinted.price_trends}</p>
                      </div>
                      <div className="p-4 rounded-lg bg-vz-bg-alt">
                        <p className="text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-2">Retail</p>
                        <p className="text-sm text-vz-ink-soft">{trendsMode.channels.retail.summary}</p>
                      </div>
                    </div>
                  </details>
                )}
              </>
            )}
          </div>
        )}



      </main>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Weekly tasks timeline (Lot 4 backend → surfaced in Companion IA, Lot 6)
// ---------------------------------------------------------------------------

interface WeeklyTaskRow {
  id: string;
  kind: string;
  scheduled_for: string;
  status: 'pending' | 'done' | 'skipped';
  payload: Record<string, unknown>;
  completed_at: string | null;
}

const KIND_LABEL: Record<string, string> = {
  monday_scoring_update: 'Repositionnement (Lundi)',
  morning_restock: 'Mise en rayon du matin',
  tuesday_window_refresh: 'Vitrine (Mardi)',
  wednesday_featured_refresh: 'Vedettes Tendance (Mercredi)',
  thursday_six_weeks_exit: 'Sortie 6 semaines (Jeudi)',
};

function WeeklyTasksTimeline() {
  const [grouped, setGrouped] = React.useState<Record<string, WeeklyTaskRow[]>>({});
  const [loading, setLoading] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/checklist/this-week');
      if (res.ok) {
        const data = await res.json();
        setGrouped(data.by_day || {});
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const markComplete = async (id: string, action: 'complete' | 'skip') => {
    setBusy(id);
    try {
      await api.post(`/api/checklist/${id}/${action}`, {});
      await load();
    } finally {
      setBusy(null);
    }
  };

  const days = Object.keys(grouped).sort();

  return (
    <Card title="Tâches automatiques de la semaine" className="mt-4">
      {loading && <p className="text-sm text-gray-500">Chargement…</p>}
      {!loading && days.length === 0 && (
        <p className="text-sm text-gray-500">
          Aucune tâche programmée — les crons n’ont pas encore tourné cette semaine.
        </p>
      )}
      <div className="space-y-3">
        {days.map((day) => (
          <div key={day} className="border-l-2 border-vz-teal/30 pl-3">
            <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">
              {new Date(day + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
            <ul className="space-y-1">
              {grouped[day].map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2 text-sm py-1">
                  <span className="flex-1">
                    <span className={`font-medium ${
                      t.status === 'done' ? 'text-vz-teal' :
                      t.status === 'skipped' ? 'text-gray-400 line-through' : 'text-black'
                    }`}>
                      {KIND_LABEL[t.kind] || t.kind}
                    </span>
                    {(t.payload as { total?: number; total_eligible?: number })?.total !== undefined && (
                      <span className="ml-2 text-xs text-gray-400">
                        ({String((t.payload as { total: number }).total)} produit(s))
                      </span>
                    )}
                    {(t.payload as { transitioned?: number })?.transitioned !== undefined && (
                      <span className="ml-2 text-xs text-orange-500">
                        {String((t.payload as { transitioned: number }).transitioned)} sortis
                      </span>
                    )}
                  </span>
                  {t.status === 'pending' && (
                    <span className="flex gap-1 shrink-0">
                      <button
                        onClick={() => markComplete(t.id, 'complete')}
                        disabled={busy === t.id}
                        className="text-xs px-2 py-0.5 rounded bg-vz-teal/10 text-vz-teal hover:bg-vz-teal/20"
                      >
                        Validé
                      </button>
                      <button
                        onClick={() => markComplete(t.id, 'skip')}
                        disabled={busy === t.id}
                        className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-500 hover:bg-gray-200"
                      >
                        Passer
                      </button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}
