'use client';

/**
 * Grille tarifaire de référence (admin, manager only).
 *
 * Pour chaque catégorie : un prix plancher « standard » (marques standards) et
 * un prix plancher « premium » (marques premium/luxe, "à partir de"). La grille
 * est consultative — à la création/réévaluation d'un article, une notification
 * signale un prix de vente sous la grille.
 *
 * Pré-remplie depuis la charte Vintiz au 1ᵉʳ chargement ; éditable par ligne.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface Row {
  category_id: string;
  category_name: string;
  standard_price: number | null;
  premium_price: number | null;
  note: string | null;
  configured: boolean;
  default_standard: number | null;
  default_premium: number | null;
  default_note: string | null;
  has_default: boolean;
}

function numOrNull(v: string): number | null {
  const t = v.trim();
  if (t === '') return null;
  const n = parseFloat(t.replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

export default function PriceReferencePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [edits, setEdits] = useState<Record<string, { standard: string; premium: string; note: string }>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [query, setQuery] = useState('');
  const [toast, setToast] = useState<{ msg: string; kind: 'success' | 'error' } | null>(null);

  const notify = useCallback((msg: string, kind: 'success' | 'error' = 'success') => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const hydrate = (data: Row[]) => {
    setRows(data);
    const e: Record<string, { standard: string; premium: string; note: string }> = {};
    for (const r of data) {
      e[r.category_id] = {
        standard: r.standard_price != null ? String(r.standard_price) : '',
        premium: r.premium_price != null ? String(r.premium_price) : '',
        note: r.note ?? '',
      };
    }
    setEdits(e);
  };

  const refresh = useCallback(async () => {
    try {
      const res = await api.get('/api/admin/price-reference');
      if (res.ok) hydrate((await res.json()).rows || []);
    } catch {
      notify('Erreur de chargement', 'error');
    }
    setLoading(false);
  }, [notify]);

  useEffect(() => { refresh(); }, [refresh]);

  const saveRow = async (r: Row) => {
    const e = edits[r.category_id];
    setSavingId(r.category_id);
    try {
      const res = await api.put(`/api/admin/price-reference/${r.category_id}`, {
        standard_price: numOrNull(e.standard),
        premium_price: numOrNull(e.premium),
        note: e.note.trim() || null,
      });
      if (res.ok) { notify(`« ${r.category_name} » enregistré`); refresh(); }
      else notify('Échec de l\'enregistrement', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSavingId(null);
  };

  const applyDefault = (r: Row) => {
    setEdits((prev) => ({
      ...prev,
      [r.category_id]: {
        standard: r.default_standard != null ? String(r.default_standard) : '',
        premium: r.default_premium != null ? String(r.default_premium) : '',
        note: r.default_note ?? '',
      },
    }));
  };

  const seedAll = async () => {
    if (!confirm('Pré-remplir toutes les catégories correspondantes depuis la charte Vintiz ? Les valeurs déjà saisies ne sont pas écrasées.')) return;
    setSeeding(true);
    try {
      const res = await api.post('/api/admin/price-reference/seed-defaults', {});
      const data = await res.json().catch(() => ({}));
      if (res.ok) { notify(`${data.written ?? 0} catégorie(s) pré-remplie(s)`); refresh(); }
      else notify('Échec du pré-remplissage', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSeeding(false);
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => r.category_name.toLowerCase().includes(q));
  }, [rows, query]);

  const matchedCount = rows.filter((r) => r.has_default).length;

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-10 md:p-8">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold text-vz-ink">Grille tarifaire de référence</h1>
              <p className="text-sm text-vz-ink-mute">
                Prix planchers par catégorie. Une notification alerte si un prix de vente passe sous la grille.
              </p>
            </div>
            <Button variant="outline" onClick={seedAll} disabled={seeding}>
              {seeding ? 'Pré-remplissage…' : '↺ Pré-remplir (charte Vintiz)'}
            </Button>
          </div>

          {toast && (
            <div role="status" className={`px-4 py-3 rounded-xl text-sm font-medium ${toast.kind === 'success' ? 'bg-vz-teal text-white' : 'bg-red-600 text-white'}`}>
              {toast.msg}
            </div>
          )}

          <Card>
            <div className="flex items-start gap-3 text-sm text-vz-ink-soft">
              <span className="text-lg leading-none">ℹ️</span>
              <div>
                <p><strong>Standard</strong> = marques standards (milieu / basique).{' '}
                <strong>Premium</strong> = marques premium &amp; luxe (« à partir de »).</p>
                <p className="text-vz-ink-mute mt-1">
                  Le rattachement d&apos;une marque à un palier se règle dans <em>Marques</em>.
                  {matchedCount > 0 && ` ${matchedCount} catégorie(s) reconnues dans la charte Vintiz.`}
                </p>
              </div>
            </div>
          </Card>

          {loading ? (
            <div className="flex justify-center py-16">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-vz-teal" />
            </div>
          ) : (
            <Card title="Catégories">
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher une catégorie…"
                className="w-full mb-4 px-3 py-2 rounded-lg border border-vz-line text-sm bg-vz-surface focus:outline-none focus:ring-2 focus:ring-vz-teal"
              />
              {filtered.length === 0 ? (
                <p className="text-sm text-vz-ink-mute py-6 text-center">
                  {rows.length === 0
                    ? 'Aucune catégorie. Créez vos catégories produits d\'abord.'
                    : 'Aucune catégorie ne correspond à la recherche.'}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-vz-ink-mute border-b border-vz-line">
                        <th className="py-2 pr-3">Catégorie</th>
                        <th className="py-2 px-2 w-28">Standard (€)</th>
                        <th className="py-2 px-2 w-28">Premium (€)</th>
                        <th className="py-2 px-2">Note</th>
                        <th className="py-2 pl-2 text-right w-40">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r) => {
                        const e = edits[r.category_id] || { standard: '', premium: '', note: '' };
                        const dirty = r.standard_price !== numOrNull(e.standard)
                          || r.premium_price !== numOrNull(e.premium)
                          || (r.note ?? '') !== e.note.trim();
                        return (
                          <tr key={r.category_id} className="border-b border-vz-line/60 align-top">
                            <td className="py-2 pr-3 font-medium text-vz-ink">
                              {r.category_name}
                              {!r.configured && r.has_default && (
                                <span className="block text-[10px] text-vz-ink-mute">charte : {r.default_standard} / {r.default_premium} €</span>
                              )}
                            </td>
                            <td className="py-2 px-2">
                              <input type="number" min="0" step="0.5" value={e.standard}
                                onChange={(ev) => setEdits({ ...edits, [r.category_id]: { ...e, standard: ev.target.value } })}
                                className="w-24 px-2 py-1.5 rounded-lg border border-vz-line text-center font-mono focus:outline-none focus:ring-2 focus:ring-vz-teal" />
                            </td>
                            <td className="py-2 px-2">
                              <input type="number" min="0" step="0.5" value={e.premium}
                                onChange={(ev) => setEdits({ ...edits, [r.category_id]: { ...e, premium: ev.target.value } })}
                                className="w-24 px-2 py-1.5 rounded-lg border border-vz-line text-center font-mono focus:outline-none focus:ring-2 focus:ring-vz-teal" />
                            </td>
                            <td className="py-2 px-2">
                              <input type="text" value={e.note}
                                onChange={(ev) => setEdits({ ...edits, [r.category_id]: { ...e, note: ev.target.value } })}
                                placeholder="—"
                                className="w-full min-w-[140px] px-2 py-1.5 rounded-lg border border-vz-line text-xs focus:outline-none focus:ring-2 focus:ring-vz-teal" />
                            </td>
                            <td className="py-2 pl-2 text-right whitespace-nowrap">
                              {r.has_default && (
                                <button onClick={() => applyDefault(r)} className="text-vz-ink-mute hover:text-vz-teal text-xs mr-3">Charte</button>
                              )}
                              <button onClick={() => saveRow(r)} disabled={savingId === r.category_id || !dirty}
                                className="text-vz-teal hover:underline text-sm disabled:opacity-40 disabled:no-underline">
                                {savingId === r.category_id ? '…' : 'Enregistrer'}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
