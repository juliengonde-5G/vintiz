'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

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

function formatCurrency(v: number) {
  return v.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

// ---------------------------------------------------------------------------
// Visual floor plan of the boutique (L-shaped, ~98m2)
// Zones are positioned to match the real layout:
//   - Vitrine gauche (front left)
//   - Podium entree (entry area)
//   - Mur gauche (left wall)
//   - Mur droit (right wall / cash desk)
//   - Mur fond (back wall)
//   - Zone centrale (center around pillar)
//   - Cabine essayage (fitting room, back)
// ---------------------------------------------------------------------------

const ZONE_LAYOUT: Record<string, { x: number; y: number; w: number; h: number; label: string; shortLabel: string }> = {
  'Vitrine gauche':      { x: 10,  y: 10,  w: 120, h: 70,  label: 'Vitrine gauche',     shortLabel: 'Vitrine' },
  'Podium entree':       { x: 140, y: 10,  w: 160, h: 70,  label: 'Podium entree',      shortLabel: 'Podium' },
  'Mur gauche':          { x: 10,  y: 90,  w: 60,  h: 200, label: 'Mur gauche',         shortLabel: 'Mur G' },
  'Mur droit':           { x: 310, y: 10,  w: 60,  h: 160, label: 'Mur droit / Caisse', shortLabel: 'Caisse' },
  'Zone centrale':       { x: 100, y: 110, w: 180, h: 130, label: 'Zone centrale',      shortLabel: 'Centre' },
  'Mur fond':            { x: 10,  y: 300, w: 270, h: 60,  label: 'Mur fond',           shortLabel: 'Fond' },
  'Cabine essayage':     { x: 290, y: 200, w: 80,  h: 160, label: 'Cabine essayage',    shortLabel: 'Cabine' },
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

        {/* Street indicator */}
        <text x="195" y="378" textAnchor="middle" fontSize="9" fill="#9CA3AF" fontFamily="sans-serif">
          &#x2191; Rue Saint-Jacques &#x2191;
        </text>

        {/* Entry arrow */}
        <line x1="220" y1="5" x2="220" y2="0" stroke="#2A8B8B" strokeWidth="2" markerEnd="url(#arrowhead)" />
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="4" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#2A8B8B" />
          </marker>
        </defs>
        <text x="220" y="-4" textAnchor="middle" fontSize="8" fill="#2A8B8B" fontFamily="sans-serif" fontWeight="600">
          ENTREE
        </text>

        {/* Pillar in center */}
        <rect x="182" y="168" width="16" height="16" rx="2" fill="#D1D5DB" stroke="#9CA3AF" strokeWidth="1" />
        <text x="190" y="178" textAnchor="middle" fontSize="6" fill="#6B7280" fontFamily="sans-serif">P</text>

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

export default function IAPage() {
  const [tab, setTab] = useState<'vision' | 'trends' | 'pricing' | 'mapping'>('vision');
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
        // Init zones
        const initRes = await api.post('/api/ai/mapping/init-zones', {});
        if (initRes.ok) {
          const zonesRes = await api.get('/api/ai/mapping/zones');
          if (zonesRes.ok) setZones(await zonesRes.json());
        }
      }
    } catch { setError('Erreur chargement zones'); }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (tab === 'trends') loadTrends();
    else if (tab === 'pricing') loadMarkdowns();
    else if (tab === 'mapping') loadZones();
  }, [tab, loadTrends, loadMarkdowns, loadZones]);

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

  const tabs = [
    { key: 'vision' as const, label: 'Analyse Photo', icon: '\uD83D\uDCF7' },
    { key: 'trends' as const, label: 'Tendances', icon: '\uD83D\uDCC8' },
    { key: 'pricing' as const, label: 'Prix & Demarques', icon: '\uD83C\uDFF7\uFE0F' },
    { key: 'mapping' as const, label: 'Mapping Boutique', icon: '\uD83D\uDDFA\uFE0F' },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">IA Booster</h1>
          <p className="text-gray-500 mt-1">Intelligence artificielle au service de votre boutique</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg min-h-[44px] whitespace-nowrap transition-colors ${
                tab === t.key
                  ? 'bg-teal text-white font-medium'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        {/* VISION TAB */}
        {tab === 'vision' && (
          <div className="space-y-6">
            <Card title="Analyse de photo produit">
              <p className="text-sm text-gray-500 mb-4">
                Uploadez une photo de vetement. L&apos;IA detectera automatiquement le type, la couleur, la matiere, la marque, la taille et l&apos;etat.
              </p>
              <div className="flex items-center gap-4">
                <label className="cursor-pointer inline-flex items-center gap-2 px-6 py-3 bg-teal text-white rounded-lg hover:bg-teal-600 transition-colors min-h-[48px]">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  {loading ? 'Analyse en cours...' : 'Choisir une photo'}
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handlePhotoUpload}
                    className="hidden"
                    disabled={loading}
                  />
                </label>
              </div>
            </Card>

            {visionResult && !visionResult.error && (
              <Card title="Resultat de l'analyse">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Type</span>
                      <span className="font-medium text-black">{visionResult.type}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Couleur</span>
                      <span className="font-medium text-black">{visionResult.couleur}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Matiere</span>
                      <span className="font-medium text-black">{visionResult.matiere}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Marque</span>
                      <span className="font-medium text-black">{visionResult.marque}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Taille</span>
                      <span className="font-medium text-black">{visionResult.taille}</span>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Etat</span>
                      <span className="font-medium text-black">{visionResult.etat}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Saison</span>
                      <span className="font-medium text-black">{visionResult.saison}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Style</span>
                      <span className="font-medium text-black">{visionResult.style}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Gamme</span>
                      <span className="font-medium text-black">{visionResult.gamme_estimee}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-500">Confiance</span>
                      <span className="font-medium text-black">{visionResult.confiance ? `${Math.round(visionResult.confiance * 100)}%` : '-'}</span>
                    </div>
                  </div>
                </div>
                {visionResult.description && (
                  <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-500 mb-1">Description suggeree</p>
                    <p className="text-black">{visionResult.description}</p>
                  </div>
                )}
              </Card>
            )}

            {visionResult?.error && (
              <Card>
                <p className="text-red-600">{visionResult.error}</p>
              </Card>
            )}
          </div>
        )}

        {/* TRENDS TAB */}
        {tab === 'trends' && (
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
                        <tr key={t.product_id} className="border-b border-gray-50">
                          <td className="py-3 text-sm text-gray-400">{i + 1}</td>
                          <td className="py-3 text-sm text-black font-medium">{t.product_name}</td>
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

        {/* PRICING TAB */}
        {tab === 'pricing' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-black">Suggestions de demarques</h2>

            {loading ? (
              <Card><p className="text-gray-400 text-center py-8">Chargement...</p></Card>
            ) : markdowns.length === 0 ? (
              <Card><p className="text-gray-400 text-center py-8">Aucune demarque suggeree - tous les produits sont recents</p></Card>
            ) : (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-3 text-sm font-semibold text-gray-600">Produit</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600">Categorie</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Prix actuel</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Prix suggere</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Remise</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600 text-right">Semaines</th>
                        <th className="pb-3 text-sm font-semibold text-gray-600">Urgence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {markdowns.map((m) => (
                        <tr key={m.product_id} className="border-b border-gray-50">
                          <td className="py-3 text-sm text-black font-medium">{m.product_name}</td>
                          <td className="py-3 text-sm text-gray-500">{m.category || '-'}</td>
                          <td className="py-3 text-sm text-right text-gray-600">{formatCurrency(m.current_price)}</td>
                          <td className="py-3 text-sm text-right font-bold text-teal">{formatCurrency(m.suggested_price)}</td>
                          <td className="py-3 text-sm text-right text-red-600">-{m.discount_percent}%</td>
                          <td className="py-3 text-sm text-right text-gray-600">{m.weeks_on_shelf}</td>
                          <td className="py-3">
                            <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${urgencyColor(m.urgency)}`}>
                              {m.urgency}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* MAPPING TAB */}
        {tab === 'mapping' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-black">Mapping de la boutique</h2>
              <div className="flex gap-2">
                {zones.length === 0 && (
                  <Button onClick={initZones} variant="secondary" disabled={loading}>
                    Initialiser les zones
                  </Button>
                )}
                <Button onClick={generateRecommendations} disabled={recoLoading}>
                  {recoLoading ? 'Generation IA...' : 'Recommandations IA'}
                </Button>
              </div>
            </div>

            {loading ? (
              <Card><p className="text-gray-400 text-center py-8">Chargement...</p></Card>
            ) : zones.length === 0 ? (
              <Card>
                <p className="text-gray-400 text-center py-8">
                  Aucune zone configuree. Cliquez sur &quot;Initialiser les zones&quot; pour creer le plan de base.
                </p>
              </Card>
            ) : (
              <>
                {/* Visual floor plan + detail panel */}
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                  <div className="lg:col-span-3">
                    <Card title="Plan de la boutique">
                      <FloorPlan
                        zones={zones}
                        onSelectZone={(z) => setSelectedZone(z)}
                        selectedZoneId={selectedZone?.zone_id ?? null}
                      />
                    </Card>
                  </div>
                  <div className="lg:col-span-2">
                    {selectedZone ? (
                      <Card>
                        <div className="flex items-start justify-between mb-4">
                          <div>
                            <h3 className="text-lg font-semibold text-black">{selectedZone.zone_name}</h3>
                            <p className="text-xs text-gray-400 mt-1">{selectedZone.description}</p>
                          </div>
                          <button
                            onClick={() => setSelectedZone(null)}
                            className="text-gray-400 hover:text-gray-600 min-h-[36px] min-w-[36px] flex items-center justify-center"
                          >
                            &times;
                          </button>
                        </div>
                        <div className="space-y-3 text-sm">
                          <div className="flex justify-between py-2 border-b border-gray-100">
                            <span className="text-gray-500">Occupation</span>
                            <span className="font-medium text-black">{selectedZone.product_count} / {selectedZone.capacity} produits</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-3">
                            <div
                              className={`h-3 rounded-full transition-all ${
                                selectedZone.occupancy_percent > 80 ? 'bg-red-400' :
                                selectedZone.occupancy_percent > 50 ? 'bg-yellow-400' :
                                'bg-green-400'
                              }`}
                              style={{ width: `${Math.min(100, selectedZone.occupancy_percent)}%` }}
                            />
                          </div>
                          <div className="flex justify-between py-2 border-b border-gray-100">
                            <span className="text-gray-500">Taux d&apos;occupation</span>
                            <span className={`font-bold ${
                              selectedZone.occupancy_percent > 80 ? 'text-red-600' :
                              selectedZone.occupancy_percent > 50 ? 'text-yellow-600' :
                              'text-green-600'
                            }`}>
                              {selectedZone.occupancy_percent}%
                            </span>
                          </div>
                          <div className="flex justify-between py-2 border-b border-gray-100">
                            <span className="text-gray-500">Valeur en rayon</span>
                            <span className="font-medium text-teal">{formatCurrency(selectedZone.total_value)}</span>
                          </div>
                          <div className="flex justify-between py-2 border-b border-gray-100">
                            <span className="text-gray-500">Score tendance moyen</span>
                            <span className={`font-bold ${scoreColor(selectedZone.avg_trend_score)}`}>
                              {selectedZone.avg_trend_score}/100
                            </span>
                          </div>
                          <div className="flex justify-between py-2">
                            <span className="text-gray-500">Places disponibles</span>
                            <span className="font-medium text-black">{selectedZone.capacity - selectedZone.product_count}</span>
                          </div>
                        </div>
                      </Card>
                    ) : (
                      <Card>
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mb-4">
                            <circle cx="12" cy="12" r="10" />
                            <line x1="12" y1="16" x2="12" y2="12" />
                            <line x1="12" y1="8" x2="12.01" y2="8" />
                          </svg>
                          <p className="text-gray-400 text-sm">Cliquez sur une zone du plan pour voir ses details</p>
                        </div>
                      </Card>
                    )}
                  </div>
                </div>

                {/* Zone cards grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {zones.map((z) => (
                    <Card key={z.zone_id}>
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="font-semibold text-black">{z.zone_name}</h3>
                          <p className="text-xs text-gray-400">{z.description}</p>
                        </div>
                        <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                          z.occupancy_percent > 80 ? 'bg-red-100 text-red-700' :
                          z.occupancy_percent > 50 ? 'bg-yellow-100 text-yellow-700' :
                          'bg-green-100 text-green-700'
                        }`}>
                          {z.occupancy_percent}%
                        </span>
                      </div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Produits</span>
                          <span className="text-black font-medium">{z.product_count} / {z.capacity}</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              z.occupancy_percent > 80 ? 'bg-red-400' :
                              z.occupancy_percent > 50 ? 'bg-yellow-400' :
                              'bg-green-400'
                            }`}
                            style={{ width: `${Math.min(100, z.occupancy_percent)}%` }}
                          />
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Valeur</span>
                          <span className="text-black font-medium">{formatCurrency(z.total_value)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Score tendance moy.</span>
                          <span className={`font-medium ${scoreColor(z.avg_trend_score)}`}>
                            {z.avg_trend_score}
                          </span>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </>
            )}

            {/* AI Recommendations */}
            {aiReco && !aiReco.error && (
              <Card title="Recommandations IA">
                {aiReco.resume && (
                  <div className="p-3 bg-teal-50 rounded-lg mb-4">
                    <p className="text-sm text-teal-800">{aiReco.resume}</p>
                  </div>
                )}

                {aiReco.recommendations && aiReco.recommendations.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-semibold text-black mb-2">Actions recommandees</h4>
                    <div className="space-y-2">
                      {aiReco.recommendations.map((r, i) => (
                        <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                          <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                            r.action === 'mettre_en_avant' ? 'bg-green-100 text-green-700' :
                            r.action === 'deplacer' ? 'bg-blue-100 text-blue-700' :
                            r.action === 'demarquer' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {r.action}
                          </span>
                          <div>
                            <p className="text-sm text-black font-medium">{r.product_name}</p>
                            {r.to_zone && <p className="text-xs text-gray-500">Vers : {r.to_zone}</p>}
                            <p className="text-xs text-gray-400 mt-1">{r.reason}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {aiReco.zone_suggestions && aiReco.zone_suggestions.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-black mb-2">Suggestions par zone</h4>
                    <div className="space-y-2">
                      {aiReco.zone_suggestions.map((s, i) => (
                        <div key={i} className="p-3 bg-gray-50 rounded-lg">
                          <p className="text-sm font-medium text-black">{s.zone} - {s.theme_suggere}</p>
                          <p className="text-xs text-gray-500 mt-1">{s.conseil}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
