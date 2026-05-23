'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface Config {
  bag_label: string;
  bag_default_price_eur: number;
}

const EMPTY: Config = {
  bag_label: 'Sac boutique Vintiz',
  bag_default_price_eur: 0.25,
};

/**
 * POS quick-add settings — surfaced in /settings &gt; Caisse.
 *
 * Configures the reusable shopping bag the « Sac » button adds at the till.
 * The bag is a manual line item: unlimited quantity, no stock impact, and the
 * price is editable per sale at the till — this is just the default.
 * Persisted in ``app_config.pos`` via ``/api/admin/pos-config``.
 */
export default function PosQuickAddPanel() {
  const [draft, setDraft] = useState<Config>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [flash, setFlash] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/pos-config');
      if (res.ok) {
        const data = await res.json();
        setDraft({
          bag_label: data.bag_label || 'Sac boutique Vintiz',
          bag_default_price_eur:
            typeof data.bag_default_price_eur === 'number'
              ? data.bag_default_price_eur
              : 0.25,
        });
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (): Promise<void> => {
    setBusy(true);
    setFlash('');
    try {
      const res = await api.put('/api/admin/pos-config', {
        bag_label: draft.bag_label,
        bag_default_price_eur: draft.bag_default_price_eur,
      });
      if (res.ok) {
        setFlash('Préférences enregistrées.');
      } else {
        const detail = await res.json().catch(() => ({}));
        alert(`Erreur : ${detail.detail || res.statusText}`);
      }
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(false);
  };

  return (
    <Card>
      <div className="mb-4">
        <h2 className="font-display text-lg font-semibold text-vz-ink">
          Article « Sac »
        </h2>
        <p className="text-sm text-vz-ink-mute">
          Le bouton « Sac » au POS ajoute cet article en quantité illimitée
          (sans impact stock). Le prix reste modifiable à la volée au panier ;
          ci-dessous le libellé et le prix par défaut.
        </p>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
          {error}
        </p>
      )}
      {flash && (
        <p className="mb-3 rounded-lg bg-vz-teal-soft px-4 py-3 text-sm text-vz-teal-deep">
          {flash}
        </p>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-vz-ink-mute">Chargement…</p>
      ) : (
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Libellé de l&apos;article
            </span>
            <input
              type="text"
              value={draft.bag_label}
              onChange={(e) => setDraft({ ...draft, bag_label: e.target.value })}
              placeholder="Sac boutique Vintiz"
              className="w-full max-w-md rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Prix par défaut (€)
            </span>
            <input
              type="number"
              min={0}
              max={1000}
              step={0.05}
              value={draft.bag_default_price_eur}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  bag_default_price_eur: parseFloat(e.target.value || '0') || 0,
                })
              }
              className="w-32 rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-right font-mono text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
            />
            <p className="mt-1 text-xs text-vz-ink-mute">
              Le caissier peut écraser ce prix sur chaque vente (le sac apparaît
              avec un prix éditable au panier).
            </p>
          </label>

          <div className="flex justify-end">
            <Button onClick={() => void save()} disabled={busy}>
              {busy ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
