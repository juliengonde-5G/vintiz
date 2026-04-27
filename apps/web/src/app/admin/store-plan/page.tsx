'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';

interface ZoneRow {
  id: string;
  name: string;
  description: string | null;
  capacity: number;
  product_types: string | null;
  color_code: string | null;
  icon: string | null;
  is_window: boolean;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  shape: string;
  n_products: number;
  occupancy_pct: number | null;
  avg_score: number | null;
  score_bucket: 'hot' | 'warm' | 'slow' | 'cold' | 'unknown';
}

interface WindowProposalItem {
  product_id: string;
  barcode: string;
  name: string;
  brand: string | null;
  color: string | null;
  sale_price: number;
  trend_score: number | null;
  position: string;
  rationale: string;
}

interface WindowProposal {
  id: string;
  iso_week: string;
  used_llm: boolean;
  accepted_at: string | null;
  proposal: {
    theme: string;
    color_palette: string[];
    items: WindowProposalItem[];
    next_review_date: string;
  };
}

const BUCKET_COLORS: Record<ZoneRow['score_bucket'], string> = {
  hot: '#16a34a',
  warm: '#65a30d',
  slow: '#f59e0b',
  cold: '#dc2626',
  unknown: '#9ca3af',
};

const BUCKET_LABEL: Record<ZoneRow['score_bucket'], string> = {
  hot: 'Hot (≥75)',
  warm: 'Warm (50-74)',
  slow: 'Slow (25-49)',
  cold: 'Cold (<25)',
  unknown: 'Sans score',
};

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + ' €';
}

export default function StorePlanPage() {
  const [zones, setZones] = useState<ZoneRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeZone, setActiveZone] = useState<ZoneRow | null>(null);

  const [windowProposal, setWindowProposal] = useState<WindowProposal | null>(null);
  const [windowLoading, setWindowLoading] = useState(false);
  const [windowError, setWindowError] = useState('');
  const [windowBusy, setWindowBusy] = useState(false);

  const loadZones = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/admin/store-plan');
      if (res.ok) {
        const data = await res.json();
        setZones(data.zones || []);
        setError('');
      } else if (res.status === 403) {
        setError('Accès réservé aux managers.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  const loadWindow = useCallback(async () => {
    setWindowLoading(true);
    setWindowError('');
    try {
      const res = await api.get('/api/admin/window-display/current');
      if (res.ok) {
        setWindowProposal(await res.json());
      } else if (res.status === 404) {
        setWindowProposal(null);
      } else if (res.status === 403) {
        setWindowError('Accès réservé.');
      } else {
        setWindowError('Erreur de chargement de la vitrine.');
      }
    } catch {
      setWindowError('Erreur réseau.');
    }
    setWindowLoading(false);
  }, []);

  useEffect(() => {
    loadZones();
    loadWindow();
  }, [loadZones, loadWindow]);

  const regenerateWindow = async () => {
    setWindowBusy(true);
    setWindowError('');
    try {
      const res = await api.post('/api/admin/window-display/regenerate', {});
      if (res.ok) {
        await loadWindow();
      } else {
        setWindowError('Échec de la régénération.');
      }
    } catch {
      setWindowError('Erreur réseau.');
    }
    setWindowBusy(false);
  };

  const acceptWindow = async () => {
    if (!windowProposal) return;
    setWindowBusy(true);
    try {
      const res = await api.post(
        `/api/admin/window-display/${windowProposal.id}/accept`,
        {},
      );
      if (res.ok) {
        await loadWindow();
      }
    } catch { /* silent */ }
    setWindowBusy(false);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-cream">
      <Sidebar />
      <main className="flex-1 overflow-y-auto md:ml-64 p-4 md:p-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-black font-display">
            Plan boutique
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Vue d&apos;ensemble des 11 zones avec densité de produits, score moyen
            et proposition vitrine de la semaine.
          </p>
        </header>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Plan SVG */}
          <div className="lg:col-span-2">
            <Card title="Plan 2D — boutique 184 m² (Lot N°2)">
              {loading ? (
                <div className="text-center text-gray-400 py-12">Chargement…</div>
              ) : zones.length === 0 ? (
                <div className="text-center text-gray-400 py-12">
                  Aucune zone configurée.
                </div>
              ) : (
                <div className="w-full">
                  <svg
                    viewBox="0 0 100 100"
                    preserveAspectRatio="xMidYMid meet"
                    className="w-full h-auto bg-white border border-gray-200 rounded-lg"
                    style={{ minHeight: '420px' }}
                  >
                    <rect
                      x="0" y="0" width="100" height="100"
                      fill="#fafafa" stroke="#e5e7eb" strokeWidth="0.3"
                    />
                    {zones.map((zone) => {
                      const fill = BUCKET_COLORS[zone.score_bucket] + '33'; // 20% alpha
                      const stroke = BUCKET_COLORS[zone.score_bucket];
                      return (
                        <g
                          key={zone.id}
                          onClick={() => setActiveZone(zone)}
                          style={{ cursor: 'pointer' }}
                        >
                          <rect
                            x={zone.pos_x}
                            y={zone.pos_y}
                            width={zone.width}
                            height={zone.height}
                            rx={zone.shape === 'rounded' ? 1.5 : 0}
                            fill={fill}
                            stroke={stroke}
                            strokeWidth="0.4"
                          />
                          <text
                            x={zone.pos_x + zone.width / 2}
                            y={zone.pos_y + zone.height / 2 - 1}
                            textAnchor="middle"
                            fontSize="2"
                            fontWeight="600"
                            fill="#111827"
                          >
                            {zone.name}
                          </text>
                          <text
                            x={zone.pos_x + zone.width / 2}
                            y={zone.pos_y + zone.height / 2 + 2.2}
                            textAnchor="middle"
                            fontSize="1.6"
                            fill="#374151"
                          >
                            {zone.n_products}/{zone.capacity}
                          </text>
                        </g>
                      );
                    })}
                  </svg>

                  {/* Legend */}
                  <div className="flex flex-wrap gap-3 mt-4 text-xs">
                    {(['hot','warm','slow','cold','unknown'] as const).map(b => (
                      <div key={b} className="flex items-center gap-1.5">
                        <span
                          className="w-3 h-3 rounded"
                          style={{ background: BUCKET_COLORS[b] + '66', borderColor: BUCKET_COLORS[b], borderWidth: 1 }}
                        />
                        <span className="text-gray-600">{BUCKET_LABEL[b]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>

          {/* Vitrine de la semaine */}
          <div className="space-y-6">
            <Card title="Vitrine de la semaine">
              {windowLoading ? (
                <div className="text-center text-gray-400 py-6">Chargement…</div>
              ) : !windowProposal ? (
                <div className="text-center text-sm text-gray-500 py-6 space-y-3">
                  <p>Aucune proposition pour la semaine en cours.</p>
                  <Button onClick={regenerateWindow} disabled={windowBusy}>
                    {windowBusy ? 'Génération…' : 'Générer maintenant'}
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-gray-500">{windowProposal.iso_week}</p>
                    <p className="font-display text-lg text-black">
                      {windowProposal.proposal.theme}
                    </p>
                    <div className="flex gap-1.5 mt-2">
                      {windowProposal.proposal.color_palette.map((hex, i) => (
                        <span
                          key={i}
                          className="w-6 h-6 rounded-full border border-gray-200"
                          style={{ background: hex }}
                          title={hex}
                        />
                      ))}
                    </div>
                  </div>

                  <ul className="divide-y divide-gray-100">
                    {windowProposal.proposal.items.map((item) => (
                      <li key={item.product_id} className="py-2 text-sm">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="font-medium text-black truncate">
                            {item.name}
                          </span>
                          <span className="text-teal font-bold">
                            {formatCurrency(item.sale_price)}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          <span className="inline-block px-1.5 py-0.5 rounded bg-pink-50 text-pink-700 mr-1.5">
                            {item.position}
                          </span>
                          {item.rationale}
                        </p>
                      </li>
                    ))}
                  </ul>

                  <div className="flex gap-2 flex-wrap pt-2 border-t border-gray-100">
                    <Button
                      variant="secondary"
                      onClick={regenerateWindow}
                      disabled={windowBusy}
                    >
                      Régénérer
                    </Button>
                    <Button
                      onClick={acceptWindow}
                      disabled={windowBusy || !!windowProposal.accepted_at}
                    >
                      {windowProposal.accepted_at
                        ? 'Validée ✓'
                        : 'Valider la vitrine'}
                    </Button>
                  </div>

                  <p className="text-xs text-gray-400">
                    {windowProposal.used_llm
                      ? 'Générée avec Claude Haiku'
                      : 'Génération déterministe (sélection score + diversité)'}
                  </p>
                </div>
              )}
              {windowError && (
                <div className="mt-3 p-2 bg-red-50 text-red-700 rounded text-xs">
                  {windowError}
                </div>
              )}
            </Card>

            {/* Locate widget */}
            <LocateCard />
          </div>
        </div>

        {activeZone && (
          <Modal
            open={true}
            onClose={() => setActiveZone(null)}
            title={activeZone.name}
          >
            <div className="space-y-3 text-sm">
              {activeZone.description && (
                <p className="text-gray-600">{activeZone.description}</p>
              )}
              <dl className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-gray-500 text-xs">Capacité</dt>
                  <dd className="font-medium">{activeZone.capacity} pièces</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Occupation</dt>
                  <dd className="font-medium">
                    {activeZone.n_products} (
                    {activeZone.occupancy_pct ?? '—'}
                    {activeZone.occupancy_pct != null ? '%' : ''})
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Score moyen</dt>
                  <dd className="font-medium">
                    {activeZone.avg_score ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Bucket</dt>
                  <dd className="font-medium capitalize">
                    {BUCKET_LABEL[activeZone.score_bucket]}
                  </dd>
                </div>
              </dl>
              {activeZone.product_types && (
                <div>
                  <dt className="text-gray-500 text-xs mb-1">Types attendus</dt>
                  <dd className="text-gray-700">{activeZone.product_types}</dd>
                </div>
              )}
              {activeZone.is_window && (
                <p className="px-3 py-2 bg-pink-50 text-pink-700 rounded text-xs">
                  Zone vitrine — réservée aux pièces Hot.
                </p>
              )}
            </div>
          </Modal>
        )}
      </main>
    </div>
  );
}


function LocateCard() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<{
    id: string; name: string; barcode: string; status: string;
    sale_price: number; zone_name: string | null;
  }[]>([]);
  const [busy, setBusy] = useState(false);

  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    try {
      const res = await api.get(
        `/api/inventory/locate?q=${encodeURIComponent(query.trim())}`,
      );
      if (res.ok) {
        setResults(await res.json());
      }
    } catch { /* silent */ }
    setBusy(false);
  };

  return (
    <Card title="Où est cette pièce ?">
      <form onSubmit={search} className="space-y-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Code-barres ou nom du produit"
          className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal"
        />
        <Button type="submit" size="sm" disabled={busy || !query.trim()}>
          {busy ? 'Recherche…' : 'Localiser'}
        </Button>
      </form>

      {results.length > 0 && (
        <ul className="mt-3 divide-y divide-gray-100 text-sm">
          {results.map((r) => (
            <li key={r.id} className="py-2">
              <p className="font-medium text-black">{r.name}</p>
              <p className="text-xs text-gray-500">
                {r.barcode} · {r.status}
              </p>
              <p className="text-xs">
                {r.zone_name ? (
                  <span className="text-teal font-medium">→ {r.zone_name}</span>
                ) : (
                  <span className="text-orange-600">Aucune zone assignée</span>
                )}
              </p>
            </li>
          ))}
        </ul>
      )}
      {results.length === 0 && query && !busy && (
        <p className="mt-3 text-xs text-gray-400">Aucun résultat.</p>
      )}
    </Card>
  );
}
