'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface BagConfig {
  label: string;
  price_eur: number;
}

const MAX_BAGS = 10;

const FALLBACK_BAGS: BagConfig[] = [
  { label: 'Sac boutique Vintiz', price_eur: 0.25 },
];

function normalizeBags(input: unknown): BagConfig[] {
  if (!Array.isArray(input)) return [];
  const out: BagConfig[] = [];
  for (const entry of input) {
    if (!entry || typeof entry !== 'object') continue;
    const label = String((entry as { label?: unknown }).label ?? '').trim();
    if (!label) continue;
    const raw = (entry as { price_eur?: unknown }).price_eur;
    const price = typeof raw === 'number' ? raw : parseFloat(String(raw)) || 0;
    out.push({ label, price_eur: price });
  }
  return out;
}

/**
 * POS quick-add settings — surfaced in /settings &gt; Caisse.
 *
 * Configures the reusable shopping bags rendered as quick-add buttons at the
 * till (one button per bag). Each is a manual line item (no stock impact,
 * unlimited quantity); the cashier can still edit the price per sale. The list
 * is persisted in ``app_config.pos.bags`` via ``/api/admin/pos-config``.
 */
export default function PosQuickAddPanel() {
  const [bags, setBags] = useState<BagConfig[]>(FALLBACK_BAGS);
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
        const resolved = normalizeBags(data.bags);
        setBags(resolved.length > 0 ? resolved : FALLBACK_BAGS);
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

  const updateBag = (idx: number, patch: Partial<BagConfig>) => {
    setBags((prev) => prev.map((b, i) => (i === idx ? { ...b, ...patch } : b)));
  };

  const addBag = () => {
    if (bags.length >= MAX_BAGS) return;
    setBags((prev) => [...prev, { label: '', price_eur: 0.25 }]);
  };

  const removeBag = (idx: number) => {
    setBags((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));
  };

  const save = async (): Promise<void> => {
    setBusy(true);
    setFlash('');
    // Empty labels and NaN prices are caught here so the user gets a clear
    // message instead of a 400 from the API.
    const cleaned = bags.map((b) => ({
      label: b.label.trim(),
      price_eur: Number.isFinite(b.price_eur) ? b.price_eur : 0,
    }));
    if (cleaned.length === 0 || cleaned.some((b) => !b.label)) {
      setBusy(false);
      alert('Chaque sac doit avoir un libellé.');
      return;
    }
    try {
      const res = await api.put('/api/admin/pos-config', { bags: cleaned });
      if (res.ok) {
        setFlash('Préférences enregistrées.');
        const data = await res.json();
        const resolved = normalizeBags(data.bags);
        if (resolved.length > 0) setBags(resolved);
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
          Articles « Sac »
        </h2>
        <p className="text-sm text-vz-ink-mute">
          Chaque sac apparaît comme un bouton de paiement-rapide au POS (ajout
          en quantité illimitée, sans impact stock). Le prix reste modifiable à
          la volée au panier — ci-dessous le libellé et le prix par défaut.
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
        <div className="space-y-3">
          <div className="grid grid-cols-[1fr_8rem_2.5rem] gap-3 pb-1 text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
            <span>Libellé</span>
            <span className="text-right">Prix par défaut (€)</span>
            <span />
          </div>
          {bags.map((bag, idx) => (
            <div key={idx} className="grid grid-cols-[1fr_8rem_2.5rem] items-center gap-3">
              <input
                type="text"
                value={bag.label}
                onChange={(e) => updateBag(idx, { label: e.target.value })}
                placeholder="Sac Kraft"
                className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
              />
              <input
                type="number"
                min={0}
                max={1000}
                step={0.05}
                value={bag.price_eur}
                onChange={(e) =>
                  updateBag(idx, {
                    price_eur: parseFloat(e.target.value || '0') || 0,
                  })
                }
                className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-right font-mono text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
              />
              <button
                type="button"
                onClick={() => removeBag(idx)}
                disabled={bags.length <= 1}
                title={bags.length <= 1 ? 'Au moins un sac requis' : 'Supprimer'}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-vz-ink-mute hover:bg-red-50 hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                aria-label="Supprimer ce sac"
              >
                ×
              </button>
            </div>
          ))}

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <Button
              variant="outline"
              onClick={addBag}
              disabled={bags.length >= MAX_BAGS}
            >
              + Ajouter un sac
            </Button>
            <p className="text-xs text-vz-ink-mute">
              {bags.length}/{MAX_BAGS} sacs · le caissier peut écraser ces prix
              au panier.
            </p>
            <Button onClick={() => void save()} disabled={busy}>
              {busy ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
