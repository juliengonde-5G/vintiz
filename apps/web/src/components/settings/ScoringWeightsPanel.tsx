'use client';

import React, { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

type Weights = {
  age: number;
  price: number;
  condition: number;
  brand: number;
  category: number;
  photos: number;
  season_transition: number;
  fashion_watch: number;
};

type AgeDecay = {
  curve: 'linear' | 'exponential' | 'step';
  max_score_days: number;
  min_score_days: number;
  saturation_days: number;
};

type SeasonBoost = {
  enabled: boolean;
  boost_pct: number;
  category_calendar: Record<string, number[]>;
};

type ConsignmentThreshold = {
  enabled: boolean;
  max_days: number;
  action_after: string;
};

type ScoringConfig = {
  version: number;
  weights: Weights;
  age_decay: AgeDecay;
  season_boost: SeasonBoost;
  consignment_threshold: ConsignmentThreshold;
  updated_by?: string | null;
  updated_at?: string | null;
};

type PreviewSample = {
  product_id: string;
  name: string;
  score_before: number;
  score_after: number;
  delta: number;
  action_before: string;
  action_after: string;
};

const WEIGHT_LABELS: { key: keyof Weights; label: string; max: number; v2: boolean }[] = [
  { key: 'age', label: 'Ancienneté en rayon', max: 0.5, v2: false },
  { key: 'price', label: 'Compétitivité prix', max: 0.5, v2: false },
  { key: 'condition', label: 'État du produit', max: 0.5, v2: false },
  { key: 'brand', label: 'Tier marque', max: 0.5, v2: false },
  { key: 'category', label: 'Tendance catégorie', max: 0.3, v2: false },
  { key: 'photos', label: 'Qualité photos', max: 0.3, v2: false },
  { key: 'season_transition', label: 'Transition saison (NEW v2)', max: 0.3, v2: true },
  { key: 'fashion_watch', label: 'Signal fashion-watch (NEW v2)', max: 0.3, v2: true },
];

const MONTH_LABELS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

export default function ScoringWeightsPanel() {
  const [config, setConfig] = useState<ScoringConfig | null>(null);
  const [original, setOriginal] = useState<ScoringConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<PreviewSample[] | null>(null);
  const [message, setMessage] = useState<string>('');
  const [error, setError] = useState<string>('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/scoring-config');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ScoringConfig = await res.json();
      setConfig(data);
      setOriginal(data);
    } catch (e: any) {
      setError(`Chargement échoué : ${e?.message || e}`);
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  if (!config) {
    return (
      <Card>
        <p className="text-sm text-gray-500">{loading ? 'Chargement…' : (error || 'Pas de config')}</p>
      </Card>
    );
  }

  const totalWeight = Object.values(config.weights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(totalWeight - 1.0) < 0.01;

  const updateWeight = (k: keyof Weights, v: number) => {
    setConfig({ ...config, weights: { ...config.weights, [k]: v } });
    setPreview(null);
  };

  const setDecayField = (k: keyof AgeDecay, v: any) => {
    setConfig({ ...config, age_decay: { ...config.age_decay, [k]: v } });
    setPreview(null);
  };

  const toggleMonth = (cat: string, month: number) => {
    const cur = config.season_boost.category_calendar[cat] || [];
    const next = cur.includes(month) ? cur.filter((m) => m !== month) : [...cur, month].sort((a, b) => a - b);
    setConfig({
      ...config,
      season_boost: {
        ...config.season_boost,
        category_calendar: { ...config.season_boost.category_calendar, [cat]: next },
      },
    });
    setPreview(null);
  };

  const reset = async (version: 1 | 2) => {
    if (!confirm(`Restaurer les valeurs par défaut v${version} ?`)) return;
    setSaving(true);
    try {
      const res = await api.post(`/api/admin/scoring-config/reset?version=${version}`, {});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
      setMessage(`Configuration v${version} restaurée.`);
    } catch (e: any) {
      setError(`Reset échoué : ${e?.message || e}`);
    }
    setSaving(false);
  };

  const save = async () => {
    if (!isValid) {
      setError('La somme des poids doit valoir 1.0 (±1%).');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const res = await api.put('/api/admin/scoring-config', config);
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`HTTP ${res.status} ${txt}`);
      }
      await load();
      setMessage('Configuration scoring sauvegardée.');
    } catch (e: any) {
      setError(`Sauvegarde échouée : ${e?.message || e}`);
    }
    setSaving(false);
  };

  const runPreview = async () => {
    setPreviewing(true);
    setError('');
    try {
      const res = await api.post('/api/admin/scoring-config/preview', config);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPreview(data.samples || []);
    } catch (e: any) {
      setError(`Simulation échouée : ${e?.message || e}`);
    }
    setPreviewing(false);
  };

  return (
    <div className="space-y-4">
      {message && (
        <div className="p-3 bg-green-50 text-green-700 rounded-lg text-sm">
          {message}
          <button onClick={() => setMessage('')} className="ml-2 font-bold">&times;</button>
        </div>
      )}
      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
        </div>
      )}

      {/* Section 1 : Pondération */}
      <Card>
        <h3 className="font-display text-lg mb-2">Pondération du score (8 composantes)</h3>
        <p className="text-sm text-gray-500 mb-4">
          Ajustez l'importance relative de chaque signal dans le calcul du score [0-100].
          La somme des 8 poids doit valoir 100%.
        </p>
        <div className="space-y-3">
          {WEIGHT_LABELS.map(({ key, label, max, v2 }) => (
            <div key={key} className="flex items-center gap-3">
              <label className="text-sm text-black w-56 flex-shrink-0 flex items-center gap-2">
                {label}
                {v2 && <span className="text-[10px] bg-teal text-white px-1.5 py-0.5 rounded">v2</span>}
              </label>
              <input
                type="range"
                min="0"
                max={max}
                step="0.01"
                value={config.weights[key]}
                onChange={(e) => updateWeight(key, parseFloat(e.target.value))}
                className="flex-1"
              />
              <span className="text-sm font-medium text-black w-14 text-right tabular-nums">
                {Math.round(config.weights[key] * 100)}%
              </span>
            </div>
          ))}
        </div>
        <div className={`mt-4 p-3 rounded-lg text-sm ${isValid ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          Somme des poids : <strong>{(totalWeight * 100).toFixed(1)}%</strong> {isValid ? '✓' : '✗ doit faire 100%'}
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={() => reset(2)} variant="outline" disabled={saving}>Restaurer v2</Button>
          <Button onClick={() => reset(1)} variant="outline" disabled={saving}>Restaurer v1 (legacy)</Button>
        </div>
      </Card>

      {/* Section 2 : Décroissance temporelle */}
      <Card>
        <h3 className="font-display text-lg mb-2">Décroissance temporelle (sub-score "ancienneté")</h3>
        <p className="text-sm text-gray-500 mb-4">
          Comment le score d'un produit décroît avec son temps en rayon.
        </p>
        <div className="space-y-3">
          <div>
            <label className="text-sm text-black mb-1 block">Courbe de décroissance</label>
            <div className="flex gap-2">
              {(['linear', 'exponential', 'step'] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => setDecayField('curve', c)}
                  className={`px-3 py-2 rounded-lg text-sm min-h-[44px] ${
                    config.age_decay.curve === c
                      ? 'bg-teal text-white'
                      : 'bg-white border border-gray-200 text-gray-600'
                  }`}
                >
                  {c === 'linear' ? 'Linéaire' : c === 'exponential' ? 'Exponentielle' : 'Par paliers'}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Score max jusqu'à J+</label>
              <input
                type="number"
                min={0}
                max={60}
                value={config.age_decay.max_score_days}
                onChange={(e) => setDecayField('max_score_days', parseInt(e.target.value))}
                className="w-full p-2 border rounded"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Score min atteint à J+</label>
              <input
                type="number"
                min={30}
                max={365}
                value={config.age_decay.min_score_days}
                onChange={(e) => setDecayField('min_score_days', parseInt(e.target.value))}
                className="w-full p-2 border rounded"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Saturation totale à J+</label>
              <input
                type="number"
                min={60}
                max={365}
                value={config.age_decay.saturation_days}
                onChange={(e) => setDecayField('saturation_days', parseInt(e.target.value))}
                className="w-full p-2 border rounded"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Section 3 : Boost saisonnier */}
      <Card>
        <h3 className="font-display text-lg mb-2">Boost saisonnier (mois favorables par catégorie)</h3>
        <div className="flex items-center gap-3 mb-4">
          <label className="text-sm text-black">Activé</label>
          <input
            type="checkbox"
            checked={config.season_boost.enabled}
            onChange={(e) => {
              setConfig({
                ...config,
                season_boost: { ...config.season_boost, enabled: e.target.checked },
              });
            }}
          />
        </div>
        {config.season_boost.enabled && (
          <div className="space-y-2">
            {Object.keys(config.season_boost.category_calendar).map((cat) => (
              <div key={cat} className="flex items-center gap-2">
                <span className="w-28 text-sm text-black flex-shrink-0">{cat}</span>
                <div className="flex gap-1">
                  {MONTH_LABELS.map((label, i) => {
                    const month = i + 1;
                    const active = config.season_boost.category_calendar[cat]?.includes(month);
                    return (
                      <button
                        key={i}
                        onClick={() => toggleMonth(cat, month)}
                        className={`w-7 h-7 text-[10px] min-h-0 min-w-0 rounded ${
                          active ? 'bg-teal text-white' : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Section 4 : Seuil de consignation */}
      <Card>
        <h3 className="font-display text-lg mb-2">Seuil de consignation longue</h3>
        <p className="text-sm text-gray-500 mb-3">
          Au-delà de N jours en rayon, l'action est forcée à RETIRER quel que soit le score.
        </p>
        <div className="flex items-center gap-3 mb-3">
          <label className="text-sm text-black">Activé</label>
          <input
            type="checkbox"
            checked={config.consignment_threshold.enabled}
            onChange={(e) => {
              setConfig({
                ...config,
                consignment_threshold: { ...config.consignment_threshold, enabled: e.target.checked },
              });
            }}
          />
        </div>
        {config.consignment_threshold.enabled && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Seuil (jours)</label>
              <input
                type="number"
                min={60}
                max={365}
                value={config.consignment_threshold.max_days}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    consignment_threshold: { ...config.consignment_threshold, max_days: parseInt(e.target.value) },
                  })
                }
                className="w-full p-2 border rounded"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Action après seuil</label>
              <select
                value={config.consignment_threshold.action_after}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    consignment_threshold: { ...config.consignment_threshold, action_after: e.target.value },
                  })
                }
                className="w-full p-2 border rounded min-h-[44px]"
              >
                <option value="RETURNED_TO_SORTING">Retour centre de tri</option>
                <option value="DONATED">Don</option>
              </select>
            </div>
          </div>
        )}
      </Card>

      {/* Section 5 : Aperçu impact */}
      <Card>
        <h3 className="font-display text-lg mb-2">Aperçu de l'impact</h3>
        <p className="text-sm text-gray-500 mb-3">
          Simule la nouvelle config sur 10 produits aléatoires (sans sauvegarder).
        </p>
        <Button onClick={runPreview} disabled={previewing || !isValid}>
          {previewing ? 'Simulation…' : 'Simuler'}
        </Button>
        {preview && preview.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Produit</th>
                  <th className="text-right py-2">Avant</th>
                  <th className="text-right py-2">Après</th>
                  <th className="text-right py-2">Δ</th>
                  <th className="text-left py-2">Action après</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((s) => (
                  <tr key={s.product_id} className="border-b border-gray-100">
                    <td className="py-2 text-black">{s.name.slice(0, 40)}</td>
                    <td className="py-2 text-right tabular-nums text-gray-500">{s.score_before.toFixed(1)}</td>
                    <td className="py-2 text-right tabular-nums font-medium text-black">{s.score_after.toFixed(1)}</td>
                    <td
                      className={`py-2 text-right tabular-nums font-bold ${
                        s.delta > 0 ? 'text-green-600' : s.delta < 0 ? 'text-red-600' : 'text-gray-400'
                      }`}
                    >
                      {s.delta > 0 ? '+' : ''}{s.delta.toFixed(1)}
                    </td>
                    <td className="py-2 text-xs text-gray-500">{s.action_after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Section 6 : Sauvegarde */}
      <div className="flex justify-between items-center">
        <p className="text-xs text-gray-400">
          {config.updated_by && `Dernière modif : ${config.updated_by} — ${config.updated_at?.slice(0, 16)}`}
        </p>
        <Button onClick={save} disabled={!isValid || saving}>
          {saving ? 'Sauvegarde…' : 'Enregistrer'}
        </Button>
      </div>
    </div>
  );
}
