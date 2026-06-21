'use client';

/**
 * Feature toggles (manager) — pour l'instant la gestion des zones.
 *
 * Désactiver le zonage fait fonctionner la boutique « sans zones » : l'assistant
 * d'ajout n'affiche plus l'étape zone, le moteur d'aménagement IA et les KPI par
 * zone sont neutralisés, et le menu « Espaces » est masqué. Réactivable à tout
 * moment.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

export default function FeaturesPanel() {
  const [zoningEnabled, setZoningEnabled] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind: 'success' | 'error' } | null>(null);

  const notify = useCallback((msg: string, kind: 'success' | 'error' = 'success') => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    api.get('/api/admin/features')
      .then(async (res) => { if (res.ok) setZoningEnabled((await res.json()).zoning_enabled !== false); })
      .catch(() => setZoningEnabled(true));
  }, []);

  const toggleZoning = async (next: boolean) => {
    setSaving(true);
    const prev = zoningEnabled;
    setZoningEnabled(next);
    try {
      const res = await api.put('/api/admin/features', { zoning_enabled: next });
      if (res.ok) {
        const data = await res.json();
        setZoningEnabled(data.zoning_enabled !== false);
        notify(next ? 'Gestion des zones activée' : 'Gestion des zones désactivée');
      } else {
        setZoningEnabled(prev);
        notify('Échec de l\'enregistrement', 'error');
      }
    } catch {
      setZoningEnabled(prev);
      notify('Erreur réseau', 'error');
    }
    setSaving(false);
  };

  return (
    <Card title="Fonctionnalités">
      {toast && (
        <div role="status" className={`mb-3 px-3 py-2 rounded-lg text-sm font-medium ${toast.kind === 'success' ? 'bg-vz-teal text-white' : 'bg-red-600 text-white'}`}>
          {toast.msg}
        </div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-vz-ink">Gestion des zones</p>
          <p className="text-xs text-vz-ink-mute mt-1 max-w-prose">
            Placement des produits par zone, plan boutique 2D, moteur d&apos;aménagement IA,
            objectifs et KPI par zone. Désactivez pour une boutique sans zonage : l&apos;assistant
            d&apos;ajout passe l&apos;étape zone, le menu « Espaces » est masqué et les indicateurs par
            zone sont neutralisés. Rien n&apos;est supprimé — réactivable à tout moment.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={!!zoningEnabled}
          disabled={zoningEnabled === null || saving}
          onClick={() => toggleZoning(!zoningEnabled)}
          className={`relative inline-flex h-7 w-12 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${zoningEnabled ? 'bg-vz-teal' : 'bg-gray-300'}`}
        >
          <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${zoningEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
      </div>
    </Card>
  );
}
