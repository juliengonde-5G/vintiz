'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface EarningConfig {
  euro_per_point: number;
  voucher_value_cents: number;
  voucher_threshold: number;
  voucher_valid_days: number;
  points_expiry_days: number;
}

/**
 * Paramétrage de la carte de fidélité (#1) : règles de cumul + bon d'achat.
 * Persisté en base (app_settings) via /api/admin/loyalty/earning-config.
 */
export default function LoyaltyCardConfig() {
  const [cfg, setCfg] = useState<EarningConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/loyalty/earning-config');
      if (res.ok) setCfg(await res.json());
      else if (res.status === 403) setError('Accès réservé aux administrateurs.');
      else setError('Impossible de charger la configuration.');
    } catch {
      setError('Erreur réseau.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = (field: keyof EarningConfig, value: number) => {
    setCfg((prev) => (prev ? { ...prev, [field]: value } : prev));
  };

  const save = async () => {
    if (!cfg) return;
    setSaving(true);
    setFlash('');
    setError('');
    try {
      const res = await api.put('/api/admin/loyalty/earning-config', cfg);
      if (res.ok) {
        setCfg(await res.json());
        setFlash('Configuration de la carte de fidélité enregistrée.');
      } else {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || "Échec de l'enregistrement.");
      }
    } catch {
      setError('Erreur réseau.');
    }
    setSaving(false);
  };

  if (loading) return <Card title="Carte de fidélité"><p className="text-sm text-gray-500">Chargement…</p></Card>;
  if (!cfg) return <Card title="Carte de fidélité"><p className="text-sm text-red-600">{error}</p></Card>;

  const euros = (cfg.voucher_value_cents / 100).toFixed(2).replace('.', ',');

  return (
    <Card title="Carte de fidélité">
      <p className="text-xs text-gray-400 mb-4">
        Règles de cumul des points et de génération du bon d&apos;achat. Appliquées
        immédiatement aux nouvelles ventes.
      </p>

      {flash && <div className="p-2 mb-3 bg-green-50 text-green-700 rounded-lg text-sm">{flash}</div>}
      {error && <div className="p-2 mb-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

      <div className="grid sm:grid-cols-2 gap-4">
        <Field
          label="1 point tous les … €"
          suffix="€ dépensés"
          value={cfg.euro_per_point}
          min={1}
          onChange={(v) => patch('euro_per_point', v)}
        />
        <Field
          label="Points pour générer un bon"
          suffix="points"
          value={cfg.voucher_threshold}
          min={1}
          onChange={(v) => patch('voucher_threshold', v)}
        />
        <Field
          label="Valeur du bon d'achat"
          suffix="centimes (€ × 100)"
          value={cfg.voucher_value_cents}
          min={0}
          onChange={(v) => patch('voucher_value_cents', v)}
        />
        <Field
          label="Validité du bon d'achat"
          suffix="jours"
          value={cfg.voucher_valid_days}
          min={1}
          onChange={(v) => patch('voucher_valid_days', v)}
        />
        <Field
          label="Validité des points (sans activité)"
          suffix="jours"
          value={cfg.points_expiry_days}
          min={1}
          onChange={(v) => patch('points_expiry_days', v)}
        />
      </div>

      <p className="text-xs text-gray-500 mt-4">
        Résumé : 1 point tous les <strong>{cfg.euro_per_point} €</strong> ·{' '}
        bon de <strong>{euros} €</strong> tous les{' '}
        <strong>{cfg.voucher_threshold} points</strong> ·{' '}
        bon valable <strong>{cfg.voucher_valid_days} jours</strong> ·{' '}
        points expirés après <strong>{cfg.points_expiry_days} jours</strong> sans activité.
      </p>

      <div className="mt-4">
        <Button onClick={save} disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </div>
    </Card>
  );
}

function Field({
  label,
  suffix,
  value,
  min,
  onChange,
}: {
  label: string;
  suffix: string;
  value: number;
  min: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-600 mb-1">{label}</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={min}
          value={value}
          onChange={(e) => onChange(Math.max(min, Number(e.target.value) || min))}
          className="w-28 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
        />
        <span className="text-xs text-gray-400">{suffix}</span>
      </div>
    </label>
  );
}
