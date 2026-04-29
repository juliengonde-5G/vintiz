'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface Product {
  id: string;
  name: string;
  brand: string | null;
  size: string | null;
  sale_price: number;
  photo_url: string | null;
  status?: string;
}

interface CurationItem {
  product_id: string;
  reason: string;
}

const MAX_PICKS = 12;

export default function AdminSelectionPage() {
  const [picks, setPicks] = useState<CurationItem[]>([]);
  const [curatorNote, setCuratorNote] = useState('');
  const [updatedAt, setUpdatedAt] = useState('');

  // Resolved product info per pick (for the table preview)
  const [productsById, setProductsById] = useState<Record<string, Product>>({});

  // Search state
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<Product[]>([]);
  const [searching, setSearching] = useState(false);

  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => { void load(); }, []);

  const load = async () => {
    try {
      const res = await api.get('/api/admin/curation-picks');
      if (res.ok) {
        const data = await res.json();
        const items: CurationItem[] = (data.items || []).map((it: { product_id: string; reason?: string }) => ({
          product_id: it.product_id,
          reason: it.reason || '',
        }));
        setPicks(items);
        setCuratorNote(data.curator_note || '');
        setUpdatedAt(data.updated_at || '');
        if (items.length > 0) await resolveProducts(items.map((p) => p.product_id));
      }
    } catch { setError('Erreur de chargement'); }
  };

  const resolveProducts = async (ids: string[]) => {
    if (ids.length === 0) return;
    const next: Record<string, Product> = { ...productsById };
    await Promise.all(
      ids.map(async (id) => {
        if (next[id]) return;
        const res = await api.get(`/api/inventory/products/${id}`);
        if (res.ok) {
          const p = await res.json();
          next[p.id] = p;
        }
      }),
    );
    setProductsById(next);
  };

  const runSearch = async () => {
    if (!search.trim()) return;
    setSearching(true);
    try {
      const res = await api.get(`/api/inventory/products/search?q=${encodeURIComponent(search.trim())}&limit=12`);
      if (res.ok) {
        const data = await res.json();
        setResults(Array.isArray(data) ? data : data.products || []);
      }
    } catch { setError('Erreur de recherche'); }
    setSearching(false);
  };

  const addPick = async (p: Product) => {
    if (picks.length >= MAX_PICKS) {
      setError(`Maximum ${MAX_PICKS} sélections — retirez-en une avant d'ajouter.`);
      return;
    }
    if (picks.find((x) => x.product_id === p.id)) return;
    setPicks((s) => [...s, { product_id: p.id, reason: '' }]);
    setProductsById((s) => ({ ...s, [p.id]: p }));
  };

  const removePick = (id: string) => setPicks((s) => s.filter((x) => x.product_id !== id));

  const movePick = (id: string, dir: -1 | 1) => {
    setPicks((s) => {
      const i = s.findIndex((x) => x.product_id === id);
      if (i < 0) return s;
      const j = i + dir;
      if (j < 0 || j >= s.length) return s;
      const out = [...s];
      [out[i], out[j]] = [out[j], out[i]];
      return out;
    });
  };

  const updateReason = (id: string, reason: string) => {
    setPicks((s) => s.map((x) => (x.product_id === id ? { ...x, reason } : x)));
  };

  const save = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const res = await api.put('/api/admin/curation-picks', {
        items: picks,
        curator_note: curatorNote,
      });
      if (res.ok) {
        setMessage('Sélection enregistrée');
        setTimeout(() => setMessage(''), 3000);
        await load();
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Erreur enregistrement');
      }
    } catch { setError('Erreur de connexion'); }
    setSaving(false);
  };

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 max-w-5xl">
        <header className="mb-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-teal">
            Curation manager
          </p>
          <h1 className="font-display text-3xl text-vz-ink mt-2">Sélection du moment</h1>
          <p className="text-sm text-vz-ink-mute mt-1 max-w-2xl">
            Choisissez jusqu&apos;à {MAX_PICKS} pièces qui seront mises en avant sur l&apos;espace client&nbsp;
            <Link href="/account/selection" className="text-vz-teal hover:underline">/account/selection</Link>.
            Les pièces vendues sont automatiquement filtrées côté front.
          </p>
          {updatedAt && (
            <p className="text-xs text-vz-ink-mute mt-2 font-mono">
              Dernière mise à jour : {new Date(updatedAt).toLocaleString('fr-FR')}
            </p>
          )}
        </header>

        {message && <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm">{message}</div>}
        {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

        <Card title="Note du curateur">
          <textarea
            value={curatorNote}
            onChange={(e) => setCuratorNote(e.target.value)}
            rows={3}
            placeholder="Une phrase qui pose le ton de la sélection (vue par les clientes en haut de la page)…"
            className="w-full px-4 py-3 rounded-lg border border-vz-line bg-white text-vz-ink focus:outline-none focus:ring-2 focus:ring-vz-teal"
          />
        </Card>

        <Card title={`Sélection actuelle · ${picks.length}/${MAX_PICKS}`} className="mt-4">
          {picks.length === 0 && (
            <p className="text-sm text-vz-ink-mute">
              Aucune pièce sélectionnée. Utilisez la recherche ci-dessous pour ajouter jusqu&apos;à {MAX_PICKS} produits.
            </p>
          )}
          {picks.length > 0 && (
            <ol className="space-y-3">
              {picks.map((pk, i) => {
                const p = productsById[pk.product_id];
                return (
                  <li key={pk.product_id} className="flex items-start gap-3 border-b border-vz-line pb-3 last:border-0">
                    <span className="font-mono text-vz-teal text-xs pt-1">{String(i + 1).padStart(2, '0')}</span>
                    <div className="w-12 h-16 rounded bg-vz-bg-alt flex-shrink-0 overflow-hidden">
                      {p?.photo_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.photo_url} alt={p.name} className="w-full h-full object-cover" />
                      ) : null}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-black truncate">
                        {p?.brand || '—'} · {p?.name || pk.product_id}
                      </p>
                      <p className="text-xs text-vz-ink-mute">
                        {p?.size && `T. ${p.size} · `}{p ? `${p.sale_price.toFixed(0)} €` : ''}
                      </p>
                      <input
                        value={pk.reason}
                        onChange={(e) => updateReason(pk.product_id, e.target.value)}
                        placeholder="Pourquoi ce coup de cœur ? (optionnel, visible côté client)"
                        className="mt-2 w-full text-sm px-3 py-2 rounded border border-vz-line bg-white"
                      />
                    </div>
                    <div className="flex flex-col gap-1 flex-shrink-0">
                      <button onClick={() => movePick(pk.product_id, -1)} disabled={i === 0}
                        className="text-xs px-2 py-1 rounded border border-vz-line text-vz-ink-soft hover:bg-vz-bg-alt disabled:opacity-40">↑</button>
                      <button onClick={() => movePick(pk.product_id, +1)} disabled={i === picks.length - 1}
                        className="text-xs px-2 py-1 rounded border border-vz-line text-vz-ink-soft hover:bg-vz-bg-alt disabled:opacity-40">↓</button>
                      <button onClick={() => removePick(pk.product_id)}
                        className="text-xs px-2 py-1 rounded text-red-600 hover:bg-red-50">×</button>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
          <div className="mt-4 flex justify-end">
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer la sélection'}
            </Button>
          </div>
        </Card>

        <Card title="Ajouter une pièce" className="mt-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Marque, code-barres, nom…"
                onKeyDown={(e) => { if (e.key === 'Enter') runSearch(); }}
              />
            </div>
            <Button onClick={runSearch} disabled={searching}>
              {searching ? 'Recherche…' : 'Chercher'}
            </Button>
          </div>
          {results.length > 0 && (
            <ul className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
              {results.map((p) => {
                const already = picks.some((x) => x.product_id === p.id);
                return (
                  <li key={p.id} className="border border-vz-line rounded-lg p-2 bg-white">
                    <div className="aspect-[4/5] bg-vz-bg-alt rounded mb-2 overflow-hidden">
                      {p.photo_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.photo_url} alt={p.name} className="w-full h-full object-cover" />
                      )}
                    </div>
                    <p className="text-xs font-medium text-black truncate">{p.brand || '—'}</p>
                    <p className="text-xs text-vz-ink-mute truncate">{p.name}</p>
                    <p className="text-sm font-display text-vz-teal mt-1">{p.sale_price.toFixed(0)} €</p>
                    <button
                      onClick={() => addPick(p)}
                      disabled={already || picks.length >= MAX_PICKS}
                      className="mt-2 w-full text-xs px-2 py-1.5 rounded bg-vz-teal text-white disabled:opacity-40 hover:bg-vz-teal-deep transition-colors"
                    >
                      {already ? 'Déjà sélectionnée' : 'Ajouter'}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </main>
    </div>
  );
}
