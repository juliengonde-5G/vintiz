'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface Reservation {
  id: string;
  client_id: string;
  client_name: string;
  client_email: string | null;
  product_id: string;
  product_name: string;
  product_barcode: string;
  sale_price: number;
  status: string;
  expires_at: string | null;
  created_at: string | null;
  notes: string | null;
}

interface ClientLite {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
}

interface ProductLite {
  id: string;
  name: string;
  barcode: string;
  sale_price: number;
  status: string;
  reserved?: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  redeemed: 'Encaissée',
  cancelled: 'Annulée',
  expired: 'Expirée',
};

const STATUS_COLOR: Record<string, string> = {
  active: 'bg-teal text-white',
  redeemed: 'bg-pink text-black',
  cancelled: 'bg-gray-200 text-gray-700',
  expired: 'bg-orange-100 text-orange-700',
};

function formatDate(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCurrency(v: number): string {
  return v.toFixed(2).replace('.', ',') + ' €';
}

export default function ReservationsPage() {
  const [items, setItems] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [onlyActive, setOnlyActive] = useState(true);

  const [clientQuery, setClientQuery] = useState('');
  const [clientResults, setClientResults] = useState<ClientLite[]>([]);
  const [client, setClient] = useState<ClientLite | null>(null);

  const [productQuery, setProductQuery] = useState('');
  const [productResults, setProductResults] = useState<ProductLite[]>([]);
  const [product, setProduct] = useState<ProductLite | null>(null);

  const [holdHours, setHoldHours] = useState(48);
  const [notes, setNotes] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/reservations?only_active=${onlyActive}`);
      if (res.ok) {
        setItems(await res.json());
        setError('');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [onlyActive]);

  useEffect(() => { load(); }, [load]);

  // Client search debounced.
  useEffect(() => {
    if (clientQuery.length < 2) { setClientResults([]); return; }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const res = await api.get(`/api/crm/clients?search=${encodeURIComponent(clientQuery)}`);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        const arr: ClientLite[] = Array.isArray(data) ? data : (data.items || []);
        setClientResults(arr.slice(0, 8));
      } catch { /* silent */ }
    }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [clientQuery]);

  // Product search debounced.
  useEffect(() => {
    if (productQuery.length < 2) { setProductResults([]); return; }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const res = await api.get(`/api/inventory/products/search?q=${encodeURIComponent(productQuery)}`);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        setProductResults(Array.isArray(data) ? data.slice(0, 8) : []);
      } catch { /* silent */ }
    }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [productQuery]);

  const submit = async () => {
    if (!client || !product) return;
    setCreating(true);
    setCreateError('');
    try {
      const res = await api.post('/api/reservations', {
        client_id: client.id,
        product_id: product.id,
        hold_hours: holdHours,
        notes: notes || null,
      });
      if (res.ok) {
        setClient(null); setProduct(null); setNotes('');
        setClientQuery(''); setProductQuery('');
        await load();
      } else {
        const body = await res.json().catch(() => ({}));
        setCreateError(body?.detail || 'Erreur lors de la création.');
      }
    } catch {
      setCreateError('Erreur réseau.');
    }
    setCreating(false);
  };

  const cancel = async (id: string) => {
    if (!window.confirm('Annuler cette réservation ?')) return;
    try {
      const res = await api.post(`/api/reservations/${id}/cancel`, { reason: null });
      if (res.ok) await load();
    } catch { /* silent */ }
  };

  const stats = useMemo(() => {
    const active = items.filter((i) => i.status === 'active').length;
    const total = items.length;
    return { active, total };
  }, [items]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-black">Réservations 48h</h1>
          <p className="text-gray-500 mt-1">
            Hold pour les clientes — {stats.active} active{stats.active > 1 ? 's' : ''}
            {' '}sur {stats.total} affichée{stats.total > 1 ? 's' : ''}.
          </p>
        </div>

        <Card title="Nouvelle réservation">
          {createError && (
            <div className="mb-3 p-2 bg-red-50 text-red-700 rounded text-sm">
              {createError}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
            <div>
              <Input
                label="Cliente (nom, email)"
                value={clientQuery}
                onChange={(e) => { setClientQuery(e.target.value); setClient(null); }}
                placeholder="Rechercher…"
              />
              {!client && clientResults.length > 0 && (
                <ul className="mt-1 max-h-40 overflow-y-auto bg-white border border-gray-200 rounded text-sm">
                  {clientResults.map((c) => (
                    <li
                      key={c.id}
                      onClick={() => { setClient(c); setClientResults([]); setClientQuery(`${c.first_name} ${c.last_name}`); }}
                      className="px-3 py-2 cursor-pointer hover:bg-gray-50"
                    >
                      {c.first_name} {c.last_name}
                      {c.email && <span className="text-gray-400 ml-2">{c.email}</span>}
                    </li>
                  ))}
                </ul>
              )}
              {client && (
                <p className="text-xs text-teal mt-1">
                  ✓ {client.first_name} {client.last_name}
                </p>
              )}
            </div>
            <div>
              <Input
                label="Article (nom, code-barres)"
                value={productQuery}
                onChange={(e) => { setProductQuery(e.target.value); setProduct(null); }}
                placeholder="Rechercher…"
              />
              {!product && productResults.length > 0 && (
                <ul className="mt-1 max-h-40 overflow-y-auto bg-white border border-gray-200 rounded text-sm">
                  {productResults.map((p) => (
                    <li
                      key={p.id}
                      onClick={() => { if (p.reserved) return; setProduct(p); setProductResults([]); setProductQuery(`${p.name} (${p.barcode})`); }}
                      className={`px-3 py-2 ${p.reserved ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-gray-50'}`}
                    >
                      {p.name} <span className="text-gray-400">{p.barcode}</span>
                      <span className="ml-2 text-teal">{formatCurrency(p.sale_price)}</span>
                      {p.reserved && <span className="ml-2 text-orange-600 text-xs">déjà réservé</span>}
                    </li>
                  ))}
                </ul>
              )}
              {product && (
                <p className="text-xs text-teal mt-1">
                  ✓ {product.name} — {formatCurrency(product.sale_price)}
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
            <Input
              label="Durée du hold (heures)"
              type="number"
              min="1"
              max="168"
              value={String(holdHours)}
              onChange={(e) => setHoldHours(Math.max(1, Math.min(168, Number(e.target.value) || 48)))}
            />
            <Input
              label="Note interne (optionnel)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex: rappellera demain"
            />
          </div>

          <Button
            onClick={submit}
            disabled={!client || !product || creating}
          >
            {creating ? 'Création…' : 'Réserver 48h'}
          </Button>
        </Card>

        <Card title="Réservations">
          <div className="flex justify-between items-center mb-3">
            <label className="text-sm text-gray-600 flex items-center gap-2">
              <input
                type="checkbox"
                checked={onlyActive}
                onChange={(e) => setOnlyActive(e.target.checked)}
              />
              Uniquement les actives
            </label>
            <Button size="sm" variant="secondary" onClick={load}>
              Rafraîchir
            </Button>
          </div>

          {error && (
            <div className="mb-3 p-2 bg-red-50 text-red-700 rounded text-sm">{error}</div>
          )}

          {loading ? (
            <p className="text-sm text-gray-400 text-center py-6">Chargement…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">
              Aucune réservation.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="py-2">Cliente</th>
                    <th className="py-2">Article</th>
                    <th className="py-2 text-right">Prix</th>
                    <th className="py-2">Statut</th>
                    <th className="py-2">Expire</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id} className="border-b border-gray-50">
                      <td className="py-2">
                        <p className="font-medium text-black">{r.client_name}</p>
                        {r.client_email && (
                          <p className="text-xs text-gray-400">{r.client_email}</p>
                        )}
                      </td>
                      <td className="py-2">
                        <p>{r.product_name}</p>
                        <p className="text-xs text-gray-400">{r.product_barcode}</p>
                      </td>
                      <td className="py-2 text-right text-teal font-medium">
                        {formatCurrency(r.sale_price)}
                      </td>
                      <td className="py-2">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${
                          STATUS_COLOR[r.status] || 'bg-gray-100'
                        }`}>
                          {STATUS_LABEL[r.status] || r.status}
                        </span>
                      </td>
                      <td className="py-2 text-gray-600">{formatDate(r.expires_at)}</td>
                      <td className="py-2 text-right">
                        {r.status === 'active' && (
                          <Button size="sm" variant="secondary" onClick={() => cancel(r.id)}>
                            Annuler
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
