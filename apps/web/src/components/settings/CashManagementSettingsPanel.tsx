'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface Config {
  allowed_discrepancy_eur: number;
  default_detail_mode: boolean;
  comptable_email: string;
}

const EMPTY: Config = {
  allowed_discrepancy_eur: 2,
  default_detail_mode: true,
  comptable_email: '',
};

/**
 * Cash management settings — surfaced in /settings &gt; Caisse.
 *
 * Drives the defaults the new POS modals use:
 *  - ``allowed_discrepancy_eur`` — tolerance shown in the close modal
 *    before the cashier is forced to enter a note
 *  - ``default_detail_mode`` — whether the denomination grid or the
 *    quick numpad is the default at open / close
 *  - ``comptable_email`` — pre-fills the Z-report email destination
 *
 * Persisted in ``app_config.cash_management``; consumed via
 * ``GET /api/admin/cash-management/config`` on app boot (PR 6 wires the
 * read into the wizard / drawer modals through ``usePosPayment``).
 */
export default function CashManagementSettingsPanel() {
  const [draft, setDraft] = useState<Config>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [flash, setFlash] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/cash-management/config');
      if (res.ok) {
        const data = await res.json();
        setDraft({
          allowed_discrepancy_eur:
            typeof data.allowed_discrepancy_eur === 'number'
              ? data.allowed_discrepancy_eur
              : 2,
          default_detail_mode:
            typeof data.default_detail_mode === 'boolean'
              ? data.default_detail_mode
              : true,
          comptable_email: data.comptable_email || '',
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
      const res = await api.put('/api/admin/cash-management/config', {
        allowed_discrepancy_eur: draft.allowed_discrepancy_eur,
        default_detail_mode: draft.default_detail_mode,
        comptable_email: draft.comptable_email,
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
          Routine de caisse
        </h2>
        <p className="text-sm text-vz-ink-mute">
          Préférences par défaut pour l'ouverture / clôture caisse et
          l'envoi du rapport Z.
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
        <p className="py-6 text-center text-sm text-vz-ink-mute">
          Chargement…
        </p>
      ) : (
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Écart autorisé par défaut (€)
            </span>
            <input
              type="number"
              min={0}
              max={1000}
              step={0.5}
              value={draft.allowed_discrepancy_eur}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  allowed_discrepancy_eur:
                    parseFloat(e.target.value || '0') || 0,
                })
              }
              className="w-32 rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-right font-mono text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
            />
            <p className="mt-1 text-xs text-vz-ink-mute">
              Au-delà, le cashier doit saisir une note de clôture
              obligatoire (NF525).
            </p>
          </label>

          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-vz-line bg-vz-surface px-3 py-3 hover:bg-vz-bg-alt">
            <input
              type="checkbox"
              checked={draft.default_detail_mode}
              onChange={(e) =>
                setDraft({ ...draft, default_detail_mode: e.target.checked })
              }
              className="h-5 w-5 accent-vz-teal"
            />
            <div>
              <div className="text-sm font-semibold text-vz-ink">
                Mode « détail dénominations » par défaut
              </div>
              <div className="text-xs text-vz-ink-mute">
                Désactive pour ouvrir directement en mode rapide (un seul
                montant total).
              </div>
            </div>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Adresse comptable (envoi Z report)
            </span>
            <input
              type="email"
              value={draft.comptable_email}
              onChange={(e) =>
                setDraft({ ...draft, comptable_email: e.target.value })
              }
              placeholder="comptable@example.fr"
              className="w-full max-w-md rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
            />
            <p className="mt-1 text-xs text-vz-ink-mute">
              Pré-rempli quand le manager clique « Envoyer par mail » sur
              un rapport Z.
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
