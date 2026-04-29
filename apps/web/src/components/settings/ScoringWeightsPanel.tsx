'use client';

import React, { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

// ============================================================
// Types — must match apps/api/app/services/scoring_config.py
// ============================================================

type WeightKey = 'attractivity' | 'season' | 'age' | 'trend' | 'price';

type Weights = Record<WeightKey, number>;

type ScoringConfig = {
  version: number;
  weights: Weights;
  age_weeks_table: number[];
  max_weeks_on_shelf: number;
  season_calendar: Record<string, number[]>;
  price_thresholds: number[];
  price_points: number[];
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

type BreakdownStats = {
  top_categories_velocity: { category_id: string; category_name: string; sales_per_week: number }[];
  top_brands_90d: { brand: string; sales_90d: number }[];
  category_trends_snapshot: Record<string, number>;
  shelf_distribution: Record<string, number>;
};

const CRITERIA: { key: WeightKey; label: string; sub: string }[] = [
  { key: 'attractivity', label: 'Attractivité',         sub: 'Vitesse de rotation 90j (catégorie + marque + état)' },
  { key: 'season',       label: 'Saison',               sub: 'Calendrier mensuel par catégorie' },
  { key: 'age',          label: 'Ancienneté',           sub: 'Décroissance hebdomadaire sur 6 semaines' },
  { key: 'trend',        label: 'Tendance',             sub: 'Tendance catégorie + signal fashion-watch' },
  { key: 'price',        label: 'Positionnement prix',  sub: 'Comparaison Vinted/LBC (Claude)' },
];

const MONTH_SHORT = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

// ============================================================
// Component
// ============================================================

export default function ScoringWeightsPanel() {
  const [config, setConfig] = useState<ScoringConfig | null>(null);
  const [original, setOriginal] = useState<ScoringConfig | null>(null);
  const [stats, setStats] = useState<BreakdownStats | null>(null);
  const [openCard, setOpenCard] = useState<WeightKey | null>('attractivity');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<PreviewSample[] | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/scoring-config');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ScoringConfig = await res.json();
      setConfig(data);
      setOriginal(data);
      const s = await api.get('/api/admin/scoring-config/breakdown-stats');
      if (s.ok) setStats(await s.json());
    } catch (e: any) {
      setError(e.message || 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading || !config) {
    return <Card title="Moteur de notation"><p>Chargement…</p></Card>;
  }

  const totalPct = Math.round(
    Object.values(config.weights).reduce((s, v) => s + v, 0) * 100,
  );
  const weightsValid = Math.abs(totalPct - 100) <= 1;

  const setWeight = (key: WeightKey, pct: number) => {
    setConfig({
      ...config,
      weights: { ...config.weights, [key]: pct / 100 },
    });
  };

  const setAgeWeek = (idx: number, pts: number) => {
    const next = [...config.age_weeks_table];
    next[idx] = Math.max(0, Math.min(20, pts));
    setConfig({ ...config, age_weeks_table: next });
  };

  const toggleSeasonMonth = (category: string, month: number) => {
    const cur = config.season_calendar[category] || [];
    const next = cur.includes(month)
      ? cur.filter((m) => m !== month)
      : [...cur, month].sort((a, b) => a - b);
    setConfig({
      ...config,
      season_calendar: { ...config.season_calendar, [category]: next },
    });
  };

  const setPriceCutoff = (idx: number, value: number) => {
    const next = [...config.price_thresholds];
    next[idx] = value;
    setConfig({ ...config, price_thresholds: next });
  };

  const save = async () => {
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const res = await api.put('/api/admin/scoring-config', config);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setConfig(data);
      setOriginal(data);
      setMessage('Configuration enregistrée');
    } catch (e: any) {
      setError(e.message || 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const restore = async () => {
    if (!confirm('Restaurer la configuration par défaut ?')) return;
    setSaving(true);
    try {
      const res = await api.post('/api/admin/scoring-config/reset', {});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setConfig(data);
      setOriginal(data);
      setMessage('Configuration restaurée');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
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
      setError(e.message);
    } finally {
      setPreviewing(false);
    }
  };

  const dirty = JSON.stringify(config) !== JSON.stringify(original);

  return (
    <div className="space-y-6">
      <Card title="Moteur de notation Vintiz — 5 critères">
        <p className="text-sm text-gray-500 mb-4">
          Le score (0-100) est mis à jour chaque lundi à 04h00 (jour de fermeture).
          Modifie les poids puis enregistre. Les détails de chaque critère sont
          consultables dans les cartes ci-dessous.
        </p>

        <div className="space-y-3">
          {CRITERIA.map(({ key, label, sub }) => (
            <div key={key} className="flex items-center gap-3 py-1.5">
              <div className="w-44 shrink-0">
                <p className="text-sm font-medium text-black">{label}</p>
                <p className="text-xs text-gray-400">{sub}</p>
              </div>
              <input
                type="range"
                min={0}
                max={50}
                step={1}
                value={Math.round(config.weights[key] * 100)}
                onChange={(e) => setWeight(key, Number(e.target.value))}
                className="flex-1"
              />
              <input
                type="number"
                min={0}
                max={50}
                step={1}
                value={Math.round(config.weights[key] * 100)}
                onChange={(e) => setWeight(key, Number(e.target.value))}
                className="w-16 px-2 py-1 text-sm border border-gray-200 rounded text-right"
              />
              <span className="w-4 text-sm text-gray-400">%</span>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
          <span className={`text-sm font-medium ${weightsValid ? 'text-vz-teal' : 'text-red-600'}`}>
            Total : {totalPct}% {weightsValid ? '✓' : '— doit valoir 100% ±1'}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={runPreview} disabled={!weightsValid || previewing}>
              {previewing ? 'Aperçu…' : 'Aperçu sur 10 produits'}
            </Button>
            <Button variant="outline" onClick={restore} disabled={saving}>Restaurer défaut</Button>
            <Button onClick={save} disabled={!weightsValid || saving || !dirty}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>

        {message && <p className="mt-3 text-sm text-vz-teal">{message}</p>}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>

      {/* Detail card 1 — Attractivité */}
      <DetailCard
        open={openCard === 'attractivity'}
        onToggle={() => setOpenCard(openCard === 'attractivity' ? null : 'attractivity')}
        title="Détail : Attractivité"
        intro="Mesurée sur les 90 derniers jours de ventes. Combine vitesse de rotation par catégorie + tier marque + état."
      >
        {stats?.top_categories_velocity?.length ? (
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Top catégories (90j)</h4>
              <ul className="space-y-1 text-sm">
                {stats.top_categories_velocity.map((c) => (
                  <li key={c.category_id} className="flex justify-between border-b border-gray-100 py-1">
                    <span>{c.category_name}</span>
                    <span className="font-mono">{c.sales_per_week.toFixed(2)}/sem.</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Top marques (90j)</h4>
              <ul className="space-y-1 text-sm">
                {stats.top_brands_90d.map((b) => (
                  <li key={b.brand} className="flex justify-between border-b border-gray-100 py-1">
                    <span>{b.brand}</span>
                    <span className="font-mono">{b.sales_90d}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Pas encore de ventes sur 90 jours.</p>
        )}
      </DetailCard>

      {/* Detail card 2 — Saison */}
      <DetailCard
        open={openCard === 'season'}
        onToggle={() => setOpenCard(openCard === 'season' ? null : 'season')}
        title="Détail : Saison"
        intro="Calendrier mois-en-saison par catégorie. En saison = 20 pts, ±1 mois = 12, hors saison = 5, pas de calendrier = 10."
      >
        <div className="space-y-2">
          {Object.keys(config.season_calendar).map((category) => (
            <div key={category} className="flex items-center gap-2">
              <span className="w-24 text-sm font-medium">{category}</span>
              <div className="flex gap-1">
                {MONTH_SHORT.map((m, idx) => {
                  const month = idx + 1;
                  const active = (config.season_calendar[category] || []).includes(month);
                  return (
                    <button
                      key={idx}
                      onClick={() => toggleSeasonMonth(category, month)}
                      className={`w-7 h-7 text-xs font-medium rounded ${
                        active ? 'bg-vz-teal text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}
                    >
                      {m}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </DetailCard>

      {/* Detail card 3 — Ancienneté */}
      <DetailCard
        open={openCard === 'age'}
        onToggle={() => setOpenCard(openCard === 'age' ? null : 'age')}
        title="Détail : Ancienneté"
        intro="Points par semaine en rayon. Au-delà de la dernière case, le produit est sorti automatiquement le jeudi."
      >
        <div className="grid grid-cols-6 gap-2">
          {config.age_weeks_table.map((pts, i) => (
            <div key={i} className="text-center">
              <p className="text-xs text-gray-500 mb-1">
                {i === config.age_weeks_table.length - 1 ? `S${i + 1}+` : `S${i + 1}`}
              </p>
              <input
                type="number"
                min={0}
                max={20}
                step={1}
                value={pts}
                onChange={(e) => setAgeWeek(i, Number(e.target.value))}
                className="w-full px-2 py-1 text-sm border border-gray-200 rounded text-center"
              />
            </div>
          ))}
        </div>
        {stats?.shelf_distribution && (
          <div className="mt-4 text-sm">
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
              Produits actuellement en rayon, par semaine
            </h4>
            <div className="grid grid-cols-7 gap-2">
              {Object.entries(stats.shelf_distribution).map(([bucket, count]) => (
                <div key={bucket} className="text-center bg-gray-50 rounded p-2">
                  <p className="text-xs text-gray-400">{bucket.replace('week_', 'S').replace('_plus', '+')}</p>
                  <p className="font-mono">{count}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </DetailCard>

      {/* Detail card 4 — Tendance */}
      <DetailCard
        open={openCard === 'trend'}
        onToggle={() => setOpenCard(openCard === 'trend' ? null : 'trend')}
        title="Détail : Tendance"
        intro="Snapshot des tendances catégorie (4 dernières semaines de ventes) + signal fashion-watch."
      >
        {stats?.category_trends_snapshot ? (
          <ul className="space-y-1 text-sm">
            {Object.entries(stats.category_trends_snapshot)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 10)
              .map(([catId, value]) => (
                <li key={catId} className="flex justify-between border-b border-gray-100 py-1">
                  <span className="font-mono text-xs text-gray-400">{catId.slice(0, 8)}…</span>
                  <span className="font-mono">{Math.round(value)}/100</span>
                </li>
              ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">Snapshot tendances indisponible.</p>
        )}
      </DetailCard>

      {/* Detail card 5 — Prix */}
      <DetailCard
        open={openCard === 'price'}
        onToggle={() => setOpenCard(openCard === 'price' ? null : 'price')}
        title="Détail : Positionnement prix"
        intro="Ratio prix de vente / prix marché estimé par Claude (Vinted/LBC). Plus le ratio est bas, plus le score est haut."
      >
        <div className="space-y-2 text-sm">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="w-32 text-gray-500">Ratio ≤</span>
              <input
                type="number"
                step={0.05}
                min={0}
                max={2}
                value={config.price_thresholds[i]}
                onChange={(e) => setPriceCutoff(i, Number(e.target.value))}
                className="w-24 px-2 py-1 border border-gray-200 rounded"
              />
              <span className="text-gray-500">→</span>
              <span className="font-mono">{config.price_points[i]} pts</span>
            </div>
          ))}
          <div className="flex items-center gap-3">
            <span className="w-32 text-gray-500">Sinon</span>
            <span className="font-mono">{config.price_points[4]} pts</span>
          </div>
        </div>
      </DetailCard>

      {/* Preview output */}
      {preview && preview.length > 0 && (
        <Card title={`Aperçu — ${preview.length} produits`}>
          <table className="w-full text-sm">
            <thead className="text-xs text-gray-500 uppercase">
              <tr><th className="text-left py-1">Produit</th>
                <th className="text-right">Avant</th>
                <th className="text-right">Après</th>
                <th className="text-right">Δ</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {preview.map((p) => (
                <tr key={p.product_id} className="border-t border-gray-100">
                  <td className="py-1">{p.name}</td>
                  <td className="text-right font-mono">{p.score_before.toFixed(0)}</td>
                  <td className="text-right font-mono">{p.score_after.toFixed(0)}</td>
                  <td className={`text-right font-mono ${p.delta >= 0 ? 'text-vz-teal' : 'text-red-600'}`}>
                    {p.delta >= 0 ? '+' : ''}{p.delta.toFixed(1)}
                  </td>
                  <td className="text-xs">{p.action_after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Reusable detail card with chevron + intro
// ----------------------------------------------------------------------------

function DetailCard({
  open,
  onToggle,
  title,
  intro,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  title: string;
  intro: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-2xl border border-vz-accent-soft/20 overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-3 hover:bg-vz-bg/40"
      >
        <div className="text-left">
          <h3 className="font-display text-base text-black">{title}</h3>
          <p className="text-xs text-gray-400 mt-0.5">{intro}</p>
        </div>
        <span className={`text-vz-teal transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {open && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}
