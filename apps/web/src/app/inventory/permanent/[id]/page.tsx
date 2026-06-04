'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
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
  updated_at: string | null;
}

interface Sale {
  transaction_id: string;
  transaction_number: number;
  transaction_type: string;
  created_at: string | null;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  line_total: number;
}

interface SalesPayload {
  sales: Sale[];
  summary: {
    units_sold: number;
    total_revenue: number;
    last_sold_at: string | null;
  };
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function PermanentItemDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const itemId = params?.id;

  const [item, setItem] = useState<PermanentItem | null>(null);
  const [sales, setSales] = useState<SalesPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [editingPrice, setEditingPrice] = useState(false);
  const [priceDraft, setPriceDraft] = useState('');
  const [savingPrice, setSavingPrice] = useState(false);

  const load = useCallback(async () => {
    if (!itemId) return;
    setLoading(true);
    try {
      const [itemRes, salesRes] = await Promise.all([
        api.get(`/api/inventory/permanent/${itemId}`),
        api.get(`/api/inventory/permanent/${itemId}/sales`),
      ]);
      if (itemRes.ok) setItem(await itemRes.json());
      else setError('Article introuvable');
      if (salesRes.ok) setSales(await salesRes.json());
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onPhotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f || !itemId) return;
    const fd = new FormData();
    fd.append('file', f);
    const res = await api.upload(`/api/inventory/permanent/${itemId}/photo`, fd);
    if (res.ok) await load();
  };

  const savePrice = async () => {
    if (!itemId) return;
    const value = parseFloat(priceDraft.replace(',', '.'));
    if (!Number.isFinite(value) || value < 0) {
      setError('Prix invalide');
      return;
    }
    setSavingPrice(true);
    const res = await api.put(`/api/inventory/permanent/${itemId}/price`, {
      sale_price: value,
    });
    setSavingPrice(false);
    if (res.ok) {
      setEditingPrice(false);
      setPriceDraft('');
      await load();
    } else {
      setError('Erreur lors de la mise à jour du tarif');
    }
  };

  const toggleActive = async () => {
    if (!itemId) return;
    const res = await api.post(`/api/inventory/permanent/${itemId}/toggle-active`, {});
    if (res.ok) await load();
  };

  const regenerateStorefront = async () => {
    if (!itemId) return;
    const res = await api.post(
      `/api/inventory/permanent/${itemId}/storefront-regenerate`,
      {},
    );
    if (res.ok) await load();
  };

  const removeItem = async () => {
    if (!itemId) return;
    if (!confirm('Supprimer définitivement cet article permanent ?')) return;
    const res = await api.delete(`/api/inventory/permanent/${itemId}`);
    if (res.ok) {
      router.push('/inventory/permanent');
    } else {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || 'Suppression refusée');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-vz-bg">
        <Sidebar />
        <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 flex items-center justify-center">
          <p className="text-vz-ink-mute">Chargement…</p>
        </main>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="min-h-screen bg-vz-bg">
        <Sidebar />
        <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
          <p className="text-vz-ink-mute">{error || 'Article introuvable'}</p>
        </main>
      </div>
    );
  }

  const imgSrc = item.storefront_photo_url || item.photo_url;

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="flex items-start gap-4 flex-wrap">
            <Link
              href="/inventory/permanent"
              className="text-vz-ink-mute hover:text-vz-ink text-sm pt-2"
            >
              ← Retour
            </Link>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-display font-semibold text-vz-ink">
                  {item.name}
                </h1>
                {item.is_active ? (
                  <Badge variant="display">Actif</Badge>
                ) : (
                  <Badge variant="returned">Désactivé</Badge>
                )}
              </div>
              <p className="text-vz-ink-soft mt-1 text-sm font-mono">
                {item.barcode} · {item.category || '—'} · Zone Vente Caisse
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" onClick={toggleActive}>
                {item.is_active ? 'Désactiver' : 'Réactiver'}
              </Button>
              <Button variant="outline" onClick={removeItem}>
                Supprimer
              </Button>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{error}</p>
          )}

          <div className="grid md:grid-cols-3 gap-5">
            {/* Photo */}
            <Card>
              <p className="text-xs uppercase tracking-wider text-vz-ink-mute mb-2">
                Photo vitrine
              </p>
              {imgSrc ? (
                <img
                  src={mediaUrl(imgSrc)}
                  alt={item.name}
                  className="w-full aspect-square object-cover rounded border border-vz-line bg-white"
                />
              ) : (
                <div className="w-full aspect-square rounded border border-dashed border-vz-line flex items-center justify-center text-vz-ink-mute text-4xl bg-white">
                  ∞
                </div>
              )}
              <div className="mt-3 flex flex-col gap-2">
                <label className="block">
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={onPhotoChange}
                    className="hidden"
                  />
                  <span className="inline-block w-full text-center cursor-pointer rounded border border-vz-line py-2 text-sm hover:bg-vz-bg-alt">
                    {imgSrc ? 'Changer la photo' : 'Ajouter une photo'}
                  </span>
                </label>
                {item.photo_url && (
                  <button
                    onClick={regenerateStorefront}
                    className="text-xs text-vz-teal underline text-left"
                  >
                    Recalculer la copie vitrine
                  </button>
                )}
              </div>
            </Card>

            {/* Infos */}
            <Card className="md:col-span-2">
              <p className="text-xs uppercase tracking-wider text-vz-ink-mute mb-3">
                Tarification
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-vz-ink-mute">Prix de vente</p>
                  {editingPrice ? (
                    <div className="flex items-center gap-2 mt-1">
                      <Input
                        type="text"
                        inputMode="decimal"
                        value={priceDraft}
                        onChange={(e) => setPriceDraft(e.target.value)}
                        autoFocus
                        className="w-24"
                      />
                      <span className="text-vz-ink-mute">€</span>
                      <Button size="sm" onClick={savePrice} disabled={savingPrice}>
                        {savingPrice ? '…' : 'OK'}
                      </Button>
                      <button
                        onClick={() => {
                          setEditingPrice(false);
                          setPriceDraft('');
                        }}
                        className="text-xs text-vz-ink-mute underline"
                      >
                        Annuler
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-baseline gap-2 mt-1">
                      <p className="text-2xl font-display font-semibold text-vz-ink">
                        {formatCurrency(item.sale_price)}
                      </p>
                      <button
                        onClick={() => {
                          setPriceDraft(String(item.sale_price));
                          setEditingPrice(true);
                        }}
                        className="text-xs text-vz-teal underline"
                      >
                        Modifier
                      </button>
                    </div>
                  )}
                </div>
                <div>
                  <p className="text-xs text-vz-ink-mute">TVA appliquée</p>
                  <p className="text-2xl font-display font-semibold text-vz-ink mt-1">
                    {item.tva_rate}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-vz-ink-mute">Date de mise en vente</p>
                  <p className="text-sm text-vz-ink mt-1">
                    {item.available_from
                      ? new Date(item.available_from).toLocaleDateString('fr-FR', {
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric',
                        })
                      : 'Immédiate'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-vz-ink-mute">Créé le</p>
                  <p className="text-sm text-vz-ink mt-1">{formatDate(item.created_at)}</p>
                </div>
              </div>
              {item.description && (
                <>
                  <p className="text-xs uppercase tracking-wider text-vz-ink-mute mb-2 mt-5">
                    Description
                  </p>
                  <p className="text-sm text-vz-ink-soft whitespace-pre-line">
                    {item.description}
                  </p>
                </>
              )}
            </Card>
          </div>

          {/* Historique des ventes */}
          <Card>
            <p className="text-xs uppercase tracking-wider text-vz-ink-mute mb-3">
              Historique des ventes
            </p>
            <div className="grid grid-cols-3 gap-4 mb-4 pb-4 border-b border-vz-line">
              <div>
                <p className="text-xs text-vz-ink-mute">Unités vendues</p>
                <p className="text-xl font-display font-semibold text-vz-ink mt-1">
                  {sales?.summary.units_sold ?? 0}
                </p>
              </div>
              <div>
                <p className="text-xs text-vz-ink-mute">CA cumulé</p>
                <p className="text-xl font-display font-semibold text-vz-teal mt-1">
                  {formatCurrency(sales?.summary.total_revenue ?? 0)}
                </p>
              </div>
              <div>
                <p className="text-xs text-vz-ink-mute">Dernière vente</p>
                <p className="text-sm text-vz-ink mt-2">
                  {formatDate(sales?.summary.last_sold_at ?? null)}
                </p>
              </div>
            </div>

            {!sales || sales.sales.length === 0 ? (
              <p className="text-center text-vz-ink-mute py-6 text-sm">
                Aucune vente enregistrée pour cet article.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-vz-line">
                      <th className="text-left py-2 text-vz-ink-soft font-medium">Date</th>
                      <th className="text-left py-2 text-vz-ink-soft font-medium">N°</th>
                      <th className="text-right py-2 text-vz-ink-soft font-medium">Qté</th>
                      <th className="text-right py-2 text-vz-ink-soft font-medium">PU</th>
                      <th className="text-right py-2 text-vz-ink-soft font-medium">Remise</th>
                      <th className="text-right py-2 text-vz-ink-soft font-medium">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sales.sales.map((s) => (
                      <tr key={`${s.transaction_id}`} className="border-b border-vz-line">
                        <td className="py-2 text-vz-ink-soft text-xs">
                          {formatDate(s.created_at)}
                        </td>
                        <td className="py-2 font-mono text-xs">#{s.transaction_number}</td>
                        <td className="py-2 text-right">{s.quantity}</td>
                        <td className="py-2 text-right font-mono">
                          {formatCurrency(s.unit_price)}
                        </td>
                        <td className="py-2 text-right text-xs text-vz-ink-mute">
                          {s.discount_percent > 0 ? `-${s.discount_percent}%` : '—'}
                        </td>
                        <td className="py-2 text-right font-mono font-semibold">
                          {s.transaction_type === 'refund' ? '−' : ''}
                          {formatCurrency(Math.abs(s.line_total))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </main>
    </div>
  );
}
