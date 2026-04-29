'use client';

import React, { useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';

type OfferType =
  | 'end_of_series'
  | 'birthday'
  | 'shoes_third_free'
  | 'progressive_voucher'
  | 'bundle_3_for_2'
  | 'seasonal_gift';

interface Offer {
  id: string;
  name: string;
  type: OfferType;
  active: boolean;
  valid_from: string | null;
  valid_until: string | null;
  requires_loyalty: boolean;
  config: Record<string, unknown>;
  priority: number;
  notes?: string | null;
}

const TYPE_LABEL: Record<OfferType, string> = {
  end_of_series:        'Fin de série (semaine 6 −20% si combiné)',
  birthday:             'Anniversaire fidélité (−10%)',
  shoes_third_free:     '3 paires de chaussures, la 3e offerte',
  progressive_voucher:  'Bons sur cumul d’achats',
  bundle_3_for_2:       '3 pour le prix de 2',
  seasonal_gift:        'Cadeau saisonnier (cat. A → cat. B offert)',
};

const TEMPLATES: { type: OfferType; label: string; build: () => Partial<Offer> }[] = [
  {
    type: 'end_of_series',
    label: 'Offre fin de série (−20% sur produit semaine 6 si combiné)',
    build: () => ({
      name: 'Fin de série −20% (combiné)',
      type: 'end_of_series',
      requires_loyalty: false,
      priority: 50,
      config: { discount_pct: 20, min_weeks_on_shelf: 6 },
    }),
  },
  {
    type: 'birthday',
    label: 'Offre anniversaire fidélité (−10%)',
    build: () => ({
      name: 'Anniversaire fidélité −10%',
      type: 'birthday',
      requires_loyalty: true,
      priority: 60,
      config: { discount_pct: 10, window_days: 5 },
    }),
  },
  {
    type: 'shoes_third_free',
    label: 'Offre 3 paires de chaussures (la 3e offerte)',
    build: () => ({
      name: '3 paires achetées, la 3e offerte',
      type: 'shoes_third_free',
      requires_loyalty: true,
      priority: 70,
      config: { category_filter: ['chaussures'], min_items: 3, free_strategy: 'cheapest' },
    }),
  },
  {
    type: 'progressive_voucher',
    label: 'Bons progressifs (paliers 200 € → 10 €, 500 € → 30 €)',
    build: () => ({
      name: 'Bons d’achat progressifs',
      type: 'progressive_voucher',
      requires_loyalty: true,
      priority: 80,
      config: {
        tiers: [
          { cumul: 200, voucher: 10 },
          { cumul: 500, voucher: 30 },
        ],
        period_start: new Date().toISOString().slice(0, 10),
        period_end: new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10),
        voucher_valid_days: 60,
      },
    }),
  },
  {
    type: 'bundle_3_for_2',
    label: '3 pour le prix de 2 sur sélection',
    build: () => ({
      name: '3 pour le prix de 2',
      type: 'bundle_3_for_2',
      requires_loyalty: false,
      priority: 90,
      config: { product_ids: [], category_ids: [], n_paid: 2, n_free: 1 },
    }),
  },
  {
    type: 'seasonal_gift',
    label: 'Offre saisonnière (manteau > 30 € → bonnet/gants offert)',
    build: () => ({
      name: 'Manteau > 30 € → bonnet/gants offert',
      type: 'seasonal_gift',
      requires_loyalty: false,
      priority: 100,
      config: {
        trigger_category: 'Manteau',
        min_amount: 30,
        gift_categories: ['Gants', 'Bonnet'],
        n_gifts: 1,
      },
    }),
  },
];

const DEFAULT_DRAFT: Offer = {
  id: '',
  name: '',
  type: 'birthday',
  active: true,
  valid_from: null,
  valid_until: null,
  requires_loyalty: false,
  config: {},
  priority: 100,
  notes: null,
};

export default function OperationsPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [draft, setDraft] = useState<Offer | null>(null);
  const [configText, setConfigText] = useState('{}');

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/admin/offers');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setOffers(data.offers || []);
    } catch (e: any) {
      setError(`Chargement échoué : ${e?.message || e}`);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const openTemplate = (idx: number) => {
    const tmpl = TEMPLATES[idx].build();
    const merged: Offer = { ...DEFAULT_DRAFT, ...tmpl } as Offer;
    setDraft(merged);
    setConfigText(JSON.stringify(merged.config || {}, null, 2));
  };

  const openExisting = (offer: Offer) => {
    setDraft(offer);
    setConfigText(JSON.stringify(offer.config || {}, null, 2));
  };

  const closeDraft = () => { setDraft(null); setError(''); };

  const save = async () => {
    if (!draft) return;
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(configText);
    } catch (e: any) {
      setError(`Config JSON invalide : ${e.message}`);
      return;
    }
    const body = { ...draft, config: parsed };
    const isCreate = !draft.id;
    const url = isCreate ? '/api/admin/offers' : `/api/admin/offers/${draft.id}`;
    try {
      const res = isCreate ? await api.post(url, body) : await api.put(url, body);
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`HTTP ${res.status} ${t}`);
      }
      setMessage(isCreate ? 'Offre créée' : 'Offre mise à jour');
      setTimeout(() => setMessage(''), 3000);
      closeDraft();
      load();
    } catch (e: any) {
      setError(e?.message || 'Erreur de sauvegarde');
    }
  };

  const remove = async (id: string) => {
    if (!confirm('Désactiver cette offre ?')) return;
    try {
      const res = await api.delete(`/api/admin/offers/${id}`);
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
      load();
    } catch (e: any) {
      setError(e?.message);
    }
  };

  const toggleActive = async (offer: Offer) => {
    try {
      const res = await api.put(`/api/admin/offers/${offer.id}`, {
        ...offer,
        active: !offer.active,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      load();
    } catch (e: any) {
      setError(e?.message);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 space-y-6">
        <header>
          <h1 className="font-display text-2xl">Opérations commerciales</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-2xl">
            Définis les règles d’offres appliquées en caisse. Les offres ne baissent jamais
            le prix de vente unitaire — elles ajoutent une remise au panier ou émettent un
            bon d’achat. Cumul fidélité : 1 € = 1 pt, palier 100 pts = bon de 8 € (auto, 2 mois).
          </p>
        </header>

        {message && <div className="p-3 bg-green-50 text-green-700 rounded-lg text-sm">{message}</div>}
        {error && <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

        <Card title="Modèles d’offres">
          <p className="text-xs text-gray-400 mb-3">Cliquez sur un modèle pour pré-remplir les paramètres.</p>
          <div className="grid md:grid-cols-2 gap-2">
            {TEMPLATES.map((t, i) => (
              <button
                key={t.type + i}
                onClick={() => openTemplate(i)}
                className="text-left p-3 rounded-lg border border-vz-accent-soft/30 hover:bg-vz-bg/40 transition-colors"
              >
                <div className="text-xs uppercase tracking-wider text-vz-teal mb-1">{t.type.replace(/_/g, ' ')}</div>
                <div className="text-sm font-medium">{t.label}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card title="Offres configurées">
          {loading && <p className="text-sm text-gray-500">Chargement…</p>}
          {!loading && offers.length === 0 && (
            <p className="text-sm text-gray-500">Aucune offre — sélectionnez un modèle ci-dessus.</p>
          )}
          {offers.length > 0 && (
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-400 uppercase">
                <tr>
                  <th className="text-left py-2">Nom</th>
                  <th className="text-left">Type</th>
                  <th className="text-center">Fidélité</th>
                  <th className="text-center">Priorité</th>
                  <th className="text-center">Actif</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {offers.map((o) => (
                  <tr key={o.id} className="border-t border-gray-100">
                    <td className="py-2">{o.name}</td>
                    <td className="text-xs text-gray-500">{TYPE_LABEL[o.type]}</td>
                    <td className="text-center">{o.requires_loyalty ? '✓' : '—'}</td>
                    <td className="text-center font-mono">{o.priority}</td>
                    <td className="text-center">
                      <button onClick={() => toggleActive(o)}
                        className={`text-xs px-2 py-0.5 rounded ${o.active ? 'bg-vz-teal/10 text-vz-teal' : 'bg-gray-100 text-gray-500'}`}>
                        {o.active ? 'Actif' : 'Inactif'}
                      </button>
                    </td>
                    <td className="text-right space-x-2">
                      <button className="text-xs text-vz-teal hover:underline" onClick={() => openExisting(o)}>Éditer</button>
                      <button className="text-xs text-red-600 hover:underline" onClick={() => remove(o.id)}>Désactiver</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {draft && (
          <Modal isOpen onClose={closeDraft}
            title={draft.id ? `Éditer · ${draft.name}` : 'Nouvelle offre'}>
            <div className="space-y-3 text-sm">
              <div>
                <label className="text-xs text-gray-500">Nom</label>
                <input
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500">Type</label>
                  <select
                    value={draft.type}
                    onChange={(e) => setDraft({ ...draft, type: e.target.value as OfferType })}
                    className="w-full px-3 py-2 border border-gray-200 rounded"
                  >
                    {Object.entries(TYPE_LABEL).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Priorité (plus bas = appliqué en premier)</label>
                  <input
                    type="number"
                    value={draft.priority}
                    onChange={(e) => setDraft({ ...draft, priority: Number(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-200 rounded"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500">Valide du</label>
                  <input
                    type="date"
                    value={draft.valid_from?.slice(0, 10) || ''}
                    onChange={(e) => setDraft({ ...draft, valid_from: e.target.value || null })}
                    className="w-full px-3 py-2 border border-gray-200 rounded"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">… au</label>
                  <input
                    type="date"
                    value={draft.valid_until?.slice(0, 10) || ''}
                    onChange={(e) => setDraft({ ...draft, valid_until: e.target.value || null })}
                    className="w-full px-3 py-2 border border-gray-200 rounded"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.requires_loyalty}
                  onChange={(e) => setDraft({ ...draft, requires_loyalty: e.target.checked })}
                />
                Réservée aux clientes fidélité
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.active}
                  onChange={(e) => setDraft({ ...draft, active: e.target.checked })}
                />
                Offre active
              </label>
              <div>
                <label className="text-xs text-gray-500">Configuration (JSON)</label>
                <textarea
                  value={configText}
                  onChange={(e) => setConfigText(e.target.value)}
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-200 rounded font-mono text-xs"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={closeDraft}>Annuler</Button>
                <Button onClick={save}>{draft.id ? 'Enregistrer' : 'Créer'}</Button>
              </div>
            </div>
          </Modal>
        )}
      </main>
    </div>
  );
}
