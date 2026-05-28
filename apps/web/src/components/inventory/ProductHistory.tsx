'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface HistoryEntry {
  id: string;
  action: 'create' | 'update' | 'delete' | string;
  user_id: string | null;
  data: Record<string, unknown> | null;
  created_at: string;
}

interface ProductHistoryProps {
  productId: string;
  /** Hook so the parent can re-fetch when the product mutates. */
  refreshKey?: number;
  /** Map of zone id → human name, so zone moves read as names not UUIDs. */
  zoneNames?: Record<string, string>;
}

const ACTION_LABELS: Record<string, { label: string; cls: string }> = {
  create: { label: 'Créé', cls: 'bg-green-100 text-green-700' },
  update: { label: 'Modifié', cls: 'bg-blue-100 text-blue-700' },
  delete: { label: 'Supprimé', cls: 'bg-red-100 text-red-700' },
};

const FIELD_LABELS: Record<string, string> = {
  sale_price: 'Prix',
  status: 'Statut',
  zone_id: 'Zone',
  brand: 'Marque',
  color: 'Couleur',
};

const STATUS_LABELS: Record<string, string> = {
  stock: 'En stock',
  display: 'En vitrine',
  displayed: 'En rayon',
  sold: 'Vendu',
  returned: 'Retourné',
  returned_to_sorting: 'Retour tri',
  received: 'Reçu',
  sorted: 'Trié',
  tagged: 'Étiqueté',
  discounted: 'Démarqué',
  deep_discounted: 'Démarque -50%',
  donated: 'Donné',
};

function formatPrice(value: unknown): string {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return `${n.toFixed(2).replace('.', ',')} €`;
}

function formatZone(value: unknown, zoneNames?: Record<string, string>): string {
  if (value === null || value === undefined || value === '') return 'Sans zone';
  const id = String(value);
  return zoneNames?.[id] || `Zone ${id.slice(0, 8)}…`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

/** Field-aware rendering so a price reads "29,50 €" and a zone reads its name. */
function formatFieldValue(
  field: string,
  value: unknown,
  zoneNames?: Record<string, string>,
): string {
  if (field === 'sale_price') return formatPrice(value);
  if (field === 'zone_id') return formatZone(value, zoneNames);
  if (field === 'status') {
    return value == null ? '—' : STATUS_LABELS[String(value)] || String(value);
  }
  return formatValue(value);
}

function formatDate(s: string): string {
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

export default function ProductHistory({
  productId,
  refreshKey,
  zoneNames,
}: ProductHistoryProps) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/inventory/products/${productId}/history`);
      if (res.ok) {
        setEntries(await res.json());
        setError('');
      } else if (res.status === 401) {
        setError('Authentification requise.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [productId]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (loading) {
    return (
      <div className="text-center text-gray-400 py-6 text-sm">
        Chargement de l&apos;historique…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-2 bg-red-50 text-red-700 rounded text-sm">{error}</div>
    );
  }

  if (entries.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-4">
        Aucun mouvement enregistré.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => {
        const cfg = ACTION_LABELS[entry.action] ?? {
          label: entry.action,
          cls: 'bg-gray-100 text-gray-600',
        };
        const diff =
          entry.action === 'update' && entry.data
            ? Object.entries(entry.data)
            : [];
        const snapshot =
          entry.action === 'create' && entry.data
            ? Object.entries(entry.data)
            : [];

        return (
          <div
            key={entry.id}
            className="p-3 border border-gray-200 rounded-lg text-sm bg-white"
          >
            <div className="flex items-center justify-between gap-3 mb-1">
              <span
                className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}
              >
                {cfg.label}
              </span>
              <span className="text-xs text-gray-400">
                {formatDate(entry.created_at)}
              </span>
            </div>

            {diff.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs">
                {diff.map(([field, value]) => {
                  const change = value as { before?: unknown; after?: unknown };
                  return (
                    <li key={field} className="flex flex-wrap gap-1">
                      <span className="font-medium text-gray-700">
                        {FIELD_LABELS[field] || field} :
                      </span>
                      <span className="text-red-500 line-through">
                        {formatFieldValue(field, change?.before, zoneNames)}
                      </span>
                      <span className="text-gray-400">→</span>
                      <span className="text-vz-teal font-medium">
                        {formatFieldValue(field, change?.after, zoneNames)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}

            {snapshot.length > 0 && (
              <p className="mt-1 text-xs text-gray-500">
                Création — prix initial{' '}
                <strong className="text-vz-teal">
                  {formatPrice(
                    (entry.data as Record<string, unknown> | null)?.sale_price,
                  )}
                </strong>
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
