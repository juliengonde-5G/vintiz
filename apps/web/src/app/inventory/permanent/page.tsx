'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import { api } from '@/lib/api';
import { formatCurrency, mediaUrl } from '@/lib/format';

interface PermanentItem {
  id: string;
  name: string;
  barcode: string;
  category_id: string;
  category: string | null;
  sale_price: number;
  tva_rate: number;
  photo_url: string | null;
  storefront_photo_url: string | null;
  available_from: string | null;
  is_active: boolean;
  description: string | null;
  created_at: string | null;
}

interface ZoneStats {
  period_days: number;
  zone_name: string;
  units_sold: number;
  total_revenue: number;
  transaction_count: number;
  avg_basket_per_tx: number;
  top_items: { id: string; name: string; units: number; revenue: number }[];
}

export default function PermanentItemsPage() {
  const [items, setItems] = useState<PermanentItem[]>([]);
  const [stats, setStats] = useState<ZoneStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showInactive, setShowInactive] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, statsRes] = await Promise.all([
        api.get(
          `/api/inventory/permanent?include_inactive=${showInactive ? 'true' : 'false'}`,
        ),
        api.get('/api/inventory/permanent/stats/zone?period_days=30'),
      ]);
      if (listRes.ok) setItems(await listRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = items.filter((it) => {
    if (!search.trim()) return true;
    const needle = search.trim().toLowerCase();
    return (
      it.name.toLowerCase().includes(needle) ||
      it.barcode.toLowerCase().includes(needle) ||
      (it.category || '').toLowerCase().includes(needle)
    );
  });

  const activeCount = items.filter((it) => it.is_active).length;
  const inactiveCount = items.length - activeCount;

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-display font-semibold text-vz-ink">
                Articles Permanents
              </h1>
              <p className="text-vz-ink-soft mt-1 max-w-2xl text-sm">
                Catalogue à quantité illimitée — sacs réutilisables, papier cadeau,
                petits accessoires neufs. Chaque code-barres peut être scanné
                autant de fois qu'on veut en caisse. Les ventes sont attribuées
                à la zone <strong>Vente Caisse</strong> dans le reporting.
              </p>
            </div>
            <Link href="/inventory/permanent/new">
              <Button>+ Créer un nouvel article</Button>
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <Card>
              <p className="text-xs text-vz-ink-mute">Articles totaux</p>
              <p className="text-2xl font-display font-semibold text-vz-ink mt-1">
                {items.length}
              </p>
              <p className="text-[11px] text-vz-ink-mute mt-1">
                {activeCount} actifs · {inactiveCount} désactivés
              </p>
            </Card>
            <Card>
              <p className="text-xs text-vz-ink-mute">CA 30 j · Vente Caisse</p>
              <p className="text-2xl font-display font-semibold text-vz-teal mt-1">
                {formatCurrency(stats?.total_revenue ?? 0)}
              </p>
              <p className="text-[11px] text-vz-ink-mute mt-1">
                {stats?.units_sold ?? 0} unité{(stats?.units_sold ?? 0) > 1 ? 's' : ''} vendue
                {(stats?.units_sold ?? 0) > 1 ? 's' : ''}
              </p>
            </Card>
            <Card>
              <p className="text-xs text-vz-ink-mute">Tickets avec un article</p>
              <p className="text-2xl font-display font-semibold text-vz-ink mt-1">
                {stats?.transaction_count ?? 0}
              </p>
              <p className="text-[11px] text-vz-ink-mute mt-1">
                Panier moy. {formatCurrency(stats?.avg_basket_per_tx ?? 0)}
              </p>
            </Card>
            <Card>
              <p className="text-xs text-vz-ink-mute">Top vente · 30 j</p>
              {stats?.top_items && stats.top_items.length > 0 ? (
                <>
                  <p className="text-sm font-semibold text-vz-ink mt-1 truncate">
                    {stats.top_items[0].name}
                  </p>
                  <p className="text-[11px] text-vz-ink-mute mt-1">
                    {stats.top_items[0].units} × ·{' '}
                    {formatCurrency(stats.top_items[0].revenue)}
                  </p>
                </>
              ) : (
                <p className="text-sm text-vz-ink-mute mt-2">Aucune vente</p>
              )}
            </Card>
          </div>

          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <Input
              type="text"
              placeholder="Rechercher (nom, code-barres, catégorie)…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 min-w-[240px]"
            />
            <label className="flex items-center gap-2 text-sm text-vz-ink-soft">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
              />
              Inclure les articles désactivés
            </label>
          </div>

          {loading ? (
            <p className="text-vz-ink-mute text-center py-12">Chargement…</p>
          ) : filtered.length === 0 ? (
            <Card>
              <p className="text-center text-vz-ink-mute py-10">
                {items.length === 0
                  ? "Aucun article permanent — créez-en un pour démarrer."
                  : 'Aucun article ne correspond à votre recherche.'}
              </p>
            </Card>
          ) : (
            <div className="bg-white rounded-xl border border-vz-line overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vz-line bg-vz-bg-alt">
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Article</th>
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Code-barres</th>
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Catégorie</th>
                    <th className="text-right px-3 py-3 text-vz-ink-soft font-medium">Prix</th>
                    <th className="text-center px-3 py-3 text-vz-ink-soft font-medium">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr
                      key={it.id}
                      className="border-b border-vz-line hover:bg-vz-bg-alt/40 transition-colors"
                    >
                      <td className="px-3 py-2">
                        <Link
                          href={`/inventory/permanent/${it.id}`}
                          className="flex items-center gap-3 group"
                        >
                          {it.storefront_photo_url || it.photo_url ? (
                            <img
                              src={mediaUrl(it.storefront_photo_url || it.photo_url)}
                              alt=""
                              className="w-10 h-10 rounded object-cover bg-vz-bg-alt"
                            />
                          ) : (
                            <div className="w-10 h-10 rounded bg-vz-bg-alt flex items-center justify-center text-vz-ink-mute text-xs">
                              ∞
                            </div>
                          )}
                          <span className="font-medium text-vz-ink group-hover:text-vz-teal">
                            {it.name}
                          </span>
                        </Link>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-vz-ink-soft">
                        {it.barcode}
                      </td>
                      <td className="px-3 py-2 text-vz-ink-soft">{it.category || '—'}</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-vz-ink">
                        {formatCurrency(it.sale_price)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {it.is_active ? (
                          <Badge variant="display">Actif</Badge>
                        ) : (
                          <Badge variant="returned">Désactivé</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
