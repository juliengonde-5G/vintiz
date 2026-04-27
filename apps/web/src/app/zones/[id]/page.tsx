'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import StatCard from '@/components/ui/StatCard';
import SectionHeader from '@/components/ui/SectionHeader';
import EmptyState from '@/components/ui/EmptyState';
import Sparkline from '@/components/ui/Sparkline';
import { api } from '@/lib/api';

type Zone = {
  id: string;
  name: string;
  description: string | null;
  capacity: number;
  product_types: string[] | null;
  color_code: string | null;
  pos_x: number; pos_y: number; width: number; height: number;
  shape: string;
  icon: string | null;
  photo_url: string | null;
  sales_target_monthly: number | null;
  display_order: number;
  product_count?: number;
};

type Analytics = {
  zone_id: string;
  zone_name: string;
  active_products: number;
  capacity: number;
  occupancy_pct: number;
  revenue_30d: number;
  revenue_prev_30d: number;
  revenue_delta_pct: number | null;
  units_30d: number;
  units_prev_30d: number;
  top_products: { id: string; name: string; brand: string | null; units: number; revenue: number }[];
  alerts: { level: string; code: string; message: string }[];
  sparkline_30d: number[];
  sales_target_monthly: number | null;
  target_reached_pct: number | null;
};

type Product = {
  id: string;
  name: string;
  brand: string | null;
  status: string;
  sale_price: number | null;
  shelf_date: string | null;
  photo_url: string | null;
  trend_score: number | null;
};

function formatCurrency(v: number) {
  return `${v.toFixed(2).replace('.', ',')} €`;
}

type Tab = 'overview' | 'products' | 'ai' | 'settings';

export default function ZoneDetailPage() {
  const params = useParams<{ id: string }>();
  const zoneId = params?.id as string;

  const [tab, setTab] = useState<Tab>('overview');
  const [zone, setZone] = useState<Zone | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState<any>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  // Settings form state
  const [form, setForm] = useState<Partial<Zone>>({});
  const [savingForm, setSavingForm] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [zonesRes, analyticsRes, productsRes] = await Promise.all([
        api.get('/api/admin/zones'),
        api.get(`/api/admin/zones/${zoneId}/analytics`),
        api.get(`/api/admin/zones/${zoneId}/products`),
      ]);
      if (zonesRes.ok) {
        const list: Zone[] = await zonesRes.json();
        const z = list.find((x) => x.id === zoneId) || null;
        setZone(z);
        if (z) setForm(z);
      }
      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
      if (productsRes.ok) setProducts(await productsRes.json());
    } finally {
      setLoading(false);
    }
  }, [zoneId]);

  useEffect(() => {
    if (zoneId) loadAll();
  }, [zoneId, loadAll]);

  const askAI = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await api.post('/api/ai/mapping/recommendations', {});
      if (!res.ok) throw new Error('ai failed');
      setAiResponse(await res.json());
    } catch {
      setAiError("L'IA n'a pas pu generer de recommandation (ANTHROPIC_API_KEY manquante ?).");
    } finally {
      setAiLoading(false);
    }
  };

  const saveForm = async () => {
    if (!zone) return;
    setSavingForm(true);
    try {
      const payload: any = {
        name: form.name,
        description: form.description,
        capacity: form.capacity,
        product_types: form.product_types,
        color_code: form.color_code,
        icon: form.icon,
        photo_url: form.photo_url,
        sales_target_monthly: form.sales_target_monthly,
      };
      const res = await api.put(`/api/admin/zones/${zone.id}`, payload);
      if (res.ok) {
        await loadAll();
      }
    } finally {
      setSavingForm(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-cream">
        <Sidebar />
        <main className="md:ml-64 p-8">
          <p className="text-sm text-gray-500">Chargement…</p>
        </main>
      </div>
    );
  }

  if (!zone) {
    return (
      <div className="min-h-screen bg-cream">
        <Sidebar />
        <main className="md:ml-64 p-8">
          <Link href="/zones" className="inline-flex items-center gap-2 text-sm text-teal hover:text-teal-700 mb-4">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Retour au plan
          </Link>
          <Card>
            <h2 className="font-display text-lg mb-2">Zone introuvable</h2>
            <p className="text-sm text-gray-500">
              L'identifiant <code className="text-xs bg-gray-100 px-1 rounded">{zoneId}</code> ne correspond
              à aucun espace de la boutique. Le plan a peut-être été ré-initialisé depuis votre dernière visite.
            </p>
          </Card>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream">
      <Sidebar />
      <main className="md:ml-64 p-4 md:p-8 max-w-7xl">
        {/* Back link */}
        <Link href="/zones" className="inline-flex items-center gap-2 text-sm text-teal hover:text-teal-700 mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Retour au plan
        </Link>

        {/* Header */}
        <div
          className="rounded-3xl p-6 md:p-8 mb-6 shadow-depth text-white relative overflow-hidden"
          style={{ background: `linear-gradient(135deg, ${zone.color_code || '#008678'}, ${zone.color_code || '#008678'}AA 70%, #000)` }}
        >
          <div className="relative z-10 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-90">
                Espace de vente #{zone.display_order}
              </p>
              <h1 className="text-3xl md:text-4xl font-display font-semibold mt-1">{zone.name}</h1>
              <p className="text-sm opacity-90 mt-1 max-w-xl">{zone.description || '—'}</p>
              {zone.product_types && zone.product_types.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {zone.product_types.map((t) => (
                    <span key={t} className="text-[11px] px-2.5 py-1 rounded-full bg-white/20 backdrop-blur-sm">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {zone.photo_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={zone.photo_url}
                alt={zone.name}
                className="h-28 w-40 object-cover rounded-xl shadow-md"
              />
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 mb-5 overflow-x-auto">
          {([
            ['overview', 'Vue d\u2019ensemble'],
            ['products', `Produits (${products.length})`],
            ['ai', 'Suggestions IA'],
            ['settings', 'Reglages'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key as Tab)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors whitespace-nowrap ${
                tab === key
                  ? 'bg-teal text-white shadow-soft'
                  : 'bg-white text-gray-600 hover:bg-teal-50 hover:text-teal'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'overview' && analytics && (
          <div className="space-y-6 animate-slide-up">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                label="Occupation"
                value={`${analytics.occupancy_pct.toFixed(0)}%`}
                hint={`${analytics.active_products} / ${analytics.capacity || '∞'} articles`}
                accent="teal"
                icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="3"/></svg>}
              />
              <StatCard
                label="CA (30 jours)"
                value={formatCurrency(analytics.revenue_30d)}
                delta={analytics.revenue_delta_pct ?? undefined}
                deltaLabel="vs 30j precedents"
                accent="pink"
                icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>}
              />
              <StatCard
                label="Articles vendus"
                value={analytics.units_30d}
                delta={analytics.units_prev_30d > 0 ? ((analytics.units_30d - analytics.units_prev_30d) / analytics.units_prev_30d) * 100 : undefined}
                deltaLabel="sur 30 jours"
                accent="teal"
                icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>}
              />
              <StatCard
                label={analytics.sales_target_monthly ? 'Objectif mensuel' : 'Rotation 30j'}
                value={
                  analytics.sales_target_monthly
                    ? `${(analytics.target_reached_pct ?? 0).toFixed(0)}%`
                    : analytics.active_products > 0
                      ? `${((analytics.units_30d / analytics.active_products) * 100).toFixed(0)}%`
                      : '—'
                }
                hint={
                  analytics.sales_target_monthly
                    ? `Cible ${formatCurrency(analytics.sales_target_monthly)}`
                    : 'Articles vendus / articles presents'
                }
                accent="warm"
                icon={<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Card className="lg:col-span-2" title="Tendance du chiffre d'affaires" subtitle="30 derniers jours">
                <Sparkline values={analytics.sparkline_30d} width={680} height={120} className="w-full h-32" />
                <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                  <span>Il y a 30 jours</span>
                  <span>Aujourd&apos;hui</span>
                </div>
              </Card>

              <Card title="Alertes" subtitle="Points de vigilance de la zone">
                {analytics.alerts.length === 0 ? (
                  <p className="text-sm text-gray-500">Tout va bien — aucune alerte.</p>
                ) : (
                  <ul className="space-y-2">
                    {analytics.alerts.map((a, i) => (
                      <li
                        key={i}
                        className={`flex items-start gap-2 rounded-xl p-3 text-sm ${
                          a.level === 'warning' ? 'bg-pink-50 text-pink-800' : 'bg-teal-50 text-teal'
                        }`}
                      >
                        <span className="mt-0.5">●</span>
                        <span>{a.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <Card title="Top produits vendus (30 jours)" subtitle="Les meilleurs ambassadeurs de la zone">
              {analytics.top_products.length === 0 ? (
                <p className="text-sm text-gray-500">Pas encore de ventes sur cette periode.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs uppercase tracking-wide text-gray-500 border-b border-gray-100">
                        <th className="py-2 pr-4">Produit</th>
                        <th className="py-2 pr-4">Marque</th>
                        <th className="py-2 pr-4 text-right">Vendus</th>
                        <th className="py-2 text-right">CA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.top_products.map((p) => (
                        <tr key={p.id} className="border-b border-gray-50 hover:bg-teal-50/40">
                          <td className="py-2 pr-4 font-medium text-black">
                            <Link href={`/inventory/${p.id}`} className="hover:text-teal">{p.name}</Link>
                          </td>
                          <td className="py-2 pr-4 text-gray-600">{p.brand || '—'}</td>
                          <td className="py-2 pr-4 text-right">{p.units}</td>
                          <td className="py-2 text-right font-medium">{formatCurrency(p.revenue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        )}

        {tab === 'products' && (
          <div className="animate-slide-up">
            {products.length === 0 ? (
              <EmptyState
                title="Aucun article assigne"
                description="Les produits affectes a cette zone apparaitront ici."
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {products.map((p) => (
                  <Link key={p.id} href={`/inventory/${p.id}`}>
                    <div className="rounded-2xl bg-white p-4 shadow-card hover:shadow-soft transition-all flex gap-3">
                      {p.photo_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.photo_url} alt={p.name} className="h-16 w-16 rounded-xl object-cover flex-shrink-0" />
                      ) : (
                        <div className="h-16 w-16 rounded-xl bg-cream flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="font-medium text-sm text-black truncate">{p.name}</p>
                        <p className="text-xs text-gray-500 truncate">{p.brand || '—'}</p>
                        <div className="mt-1 flex items-center gap-2">
                          {p.sale_price != null && (
                            <span className="text-sm font-semibold text-teal">{formatCurrency(p.sale_price)}</span>
                          )}
                          <span className="text-[10px] uppercase tracking-wide text-gray-400">{p.status}</span>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'ai' && (
          <div className="animate-slide-up">
            <Card
              variant="gradient"
              title="Compagnon IA"
              subtitle="Demande une recommandation de rearrangement pour cette zone"
              action={
                <Button onClick={askAI} disabled={aiLoading} size="sm">
                  {aiLoading ? 'Reflexion…' : 'Demander a l\u2019IA'}
                </Button>
              }
            >
              {aiError && <p className="text-sm text-pink-700">{aiError}</p>}
              {!aiResponse && !aiError && (
                <p className="text-sm text-gray-600">
                  Clique sur « Demander a l&apos;IA » pour obtenir des idees de rearrangement,
                  mise en avant, ou corrections basees sur tes donnees de ventes recentes.
                </p>
              )}
              {aiResponse && (
                <pre className="whitespace-pre-wrap text-sm text-gray-800 bg-white rounded-xl p-4 mt-3 max-h-96 overflow-auto">
                  {typeof aiResponse === 'string' ? aiResponse : JSON.stringify(aiResponse, null, 2)}
                </pre>
              )}
            </Card>
          </div>
        )}

        {tab === 'settings' && (
          <div className="animate-slide-up">
            <Card title="Reglages de la zone" subtitle="Modifie les metadonnees, la couleur et l'objectif">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">Nom</span>
                  <input
                    className="mt-1 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:ring-2 focus:ring-teal focus:border-teal"
                    value={form.name || ''}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">Capacite</span>
                  <input
                    type="number"
                    className="mt-1 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:ring-2 focus:ring-teal focus:border-teal"
                    value={form.capacity ?? 0}
                    onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="text-xs font-medium text-gray-600">Description</span>
                  <textarea
                    className="mt-1 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:ring-2 focus:ring-teal focus:border-teal"
                    rows={2}
                    value={form.description || ''}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">Couleur</span>
                  <input
                    type="color"
                    className="mt-1 w-full h-10 rounded-xl border border-gray-200"
                    value={form.color_code || '#008678'}
                    onChange={(e) => setForm({ ...form, color_code: e.target.value })}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">Icone</span>
                  <select
                    className="mt-1 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm"
                    value={form.icon || ''}
                    onChange={(e) => setForm({ ...form, icon: e.target.value || null })}
                  >
                    <option value="">—</option>
                    <option value="sparkles">Vitrine (sparkles)</option>
                    <option value="star">Podium (star)</option>
                    <option value="shirt">Mur vetements (shirt)</option>
                    <option value="cash">Caisse (cash)</option>
                    <option value="bag">Sacs (bag)</option>
                    <option value="grid">Zone centrale (grid)</option>
                    <option value="door">Cabine (door)</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-gray-600">Objectif CA mensuel (€)</span>
                  <input
                    type="number"
                    step="10"
                    className="mt-1 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm"
                    value={form.sales_target_monthly ?? ''}
                    onChange={(e) => setForm({ ...form, sales_target_monthly: e.target.value ? Number(e.target.value) : null })}
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="text-xs font-medium text-gray-600">Photo (URL)</span>
                  <input
                    className="mt-1 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm"
                    value={form.photo_url || ''}
                    placeholder="https://..."
                    onChange={(e) => setForm({ ...form, photo_url: e.target.value || null })}
                  />
                </label>
              </div>
              <div className="mt-4 flex items-center justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setForm(zone)}>Annuler</Button>
                <Button size="sm" onClick={saveForm} disabled={savingForm}>
                  {savingForm ? 'Sauvegarde…' : 'Enregistrer'}
                </Button>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
