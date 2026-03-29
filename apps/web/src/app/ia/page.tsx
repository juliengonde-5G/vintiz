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

function formatCurrency(v: number) {
  return v.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
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
  const [aiReco, setAiReco] = useState<Record<string, unknown> | null>(null);
  const [recoLoading, setRecoLoading] = useState(false);

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
            )}

            {/* AI Recommendations */}
            {aiReco && !('error' in aiReco) && (
              <Card title="Recommandations IA">
                {aiReco.resume && (
                  <div className="p-3 bg-teal-50 rounded-lg mb-4">
                    <p className="text-sm text-teal-800">{aiReco.resume as string}</p>
                  </div>
                )}

                {Array.isArray(aiReco.recommendations) && (aiReco.recommendations as Array<Record<string, string>>).length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-semibold text-black mb-2">Actions recommandees</h4>
                    <div className="space-y-2">
                      {(aiReco.recommendations as Array<Record<string, string>>).map((r, i) => (
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

                {Array.isArray(aiReco.zone_suggestions) && (aiReco.zone_suggestions as Array<Record<string, string>>).length > 0 && (
                  <div>
                    <h4 className="font-semibold text-black mb-2">Suggestions par zone</h4>
                    <div className="space-y-2">
                      {(aiReco.zone_suggestions as Array<Record<string, string>>).map((s, i) => (
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
