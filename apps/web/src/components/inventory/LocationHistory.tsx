'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface LocationEvent {
  id: string;
  occurred_at: string | null;
  move_type: 'to_floor' | 'to_stock' | 'zone_change' | 'exit' | 'intake' | string;
  from_status: string | null;
  to_status: string | null;
  from_zone_name: string | null;
  to_zone_name: string | null;
  source: string | null;
  reason: string | null;
}

interface LocationHistoryProps {
  productId: string;
  /** Hook so the parent can re-fetch when the product moves. */
  refreshKey?: number;
}

const MOVE_LABELS: Record<string, { label: string; dot: string }> = {
  to_floor: { label: 'Mise en rayon', dot: 'bg-vz-teal' },
  to_stock: { label: 'Retour réserve', dot: 'bg-amber-500' },
  zone_change: { label: 'Changement de zone', dot: 'bg-blue-500' },
  exit: { label: 'Sortie', dot: 'bg-red-500' },
  intake: { label: 'Arrivée', dot: 'bg-green-500' },
};

const SOURCE_LABELS: Record<string, string> = {
  scan: 'scan douchette',
  manual: 'saisie manuelle',
  import: 'import',
  system: 'automatique',
  pos: 'caisse',
};

function formatDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }) +
    ' · ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

export default function LocationHistory({ productId, refreshKey }: LocationHistoryProps) {
  const [events, setEvents] = useState<LocationEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/inventory/products/${productId}/location-history`);
      if (res.ok) {
        setEvents(await res.json());
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
        Chargement des emplacements…
      </div>
    );
  }

  if (error) {
    return <div className="p-2 bg-red-50 text-red-700 rounded text-sm">{error}</div>;
  }

  if (events.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-4">
        Aucun déplacement enregistré.
      </p>
    );
  }

  return (
    <ol className="relative ml-2 border-l-2 border-vz-line space-y-4">
      {events.map((ev) => {
        const cfg = MOVE_LABELS[ev.move_type] ?? {
          label: ev.move_type,
          dot: 'bg-gray-400',
        };
        const source =
          ev.source ? SOURCE_LABELS[ev.source] || ev.source : null;
        return (
          <li key={ev.id} className="ml-4">
            <span
              className={`absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full ring-2 ring-white ${cfg.dot}`}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-vz-ink">{cfg.label}</span>
              <span className="text-xs text-gray-400">{formatDate(ev.occurred_at)}</span>
            </div>
            {ev.move_type === 'zone_change' && (
              <p className="text-xs text-gray-600 mt-0.5">
                de <span className="font-medium">{ev.from_zone_name || 'Sans zone'}</span>
                {' → '}
                <span className="font-medium text-vz-teal">{ev.to_zone_name || 'Sans zone'}</span>
              </p>
            )}
            {ev.move_type !== 'zone_change' && (ev.from_zone_name || ev.to_zone_name) && (
              <p className="text-xs text-gray-600 mt-0.5">
                {ev.to_zone_name ? (
                  <>vers <span className="font-medium text-vz-teal">{ev.to_zone_name}</span></>
                ) : ev.from_zone_name ? (
                  <>depuis <span className="font-medium">{ev.from_zone_name}</span></>
                ) : null}
              </p>
            )}
            <p className="text-[11px] text-gray-400 mt-0.5">
              {source && <>Source&nbsp;: {source}</>}
              {source && ev.reason && ' · '}
              {ev.reason}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
