'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface SegmentRow {
  segment: string;
  count: number;
}

interface SegmentsResponse {
  total_segmented: number;
  segments: SegmentRow[];
}

const SEGMENT_LABELS: Record<string, string> = {
  champion: 'Champions',
  loyal: 'Fidèles',
  new: 'Nouvelles',
  promising: 'Prometteuses',
  cant_lose: 'À ne pas perdre',
  at_risk: 'À risque',
  hibernating: 'En sommeil',
  lost: 'Perdues',
  regular: 'Régulières',
};

const SEGMENT_COLORS: Record<string, string> = {
  champion: 'bg-vz-teal text-white',
  loyal: 'bg-vz-accent-soft text-black',
  new: 'bg-yellow-100 text-yellow-800',
  promising: 'bg-blue-100 text-blue-800',
  cant_lose: 'bg-orange-200 text-orange-900',
  at_risk: 'bg-orange-100 text-orange-700',
  hibernating: 'bg-gray-200 text-gray-700',
  lost: 'bg-red-100 text-red-700',
  regular: 'bg-gray-100 text-gray-600',
};

export default function RfmSegmentsCard() {
  const [data, setData] = useState<SegmentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/crm/segments');
      if (res.ok) {
        setData(await res.json());
        setError('');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const runNow = async () => {
    setRunning(true);
    try {
      const res = await api.post('/api/admin/rfm/run', {});
      if (res.ok) await load();
    } catch { /* silent */ }
    setRunning(false);
  };

  const total = data?.total_segmented || 0;

  return (
    <Card title="Segmentation RFM (P4-007)">
      <div className="flex justify-between items-center mb-4">
        <p className="text-xs text-gray-500">
          Récence × Fréquence × Montant — segmentation mensuelle automatique.
        </p>
        <Button size="sm" variant="secondary" onClick={runNow} disabled={running}>
          {running ? 'Calcul…' : 'Recalculer maintenant'}
        </Button>
      </div>

      {error && (
        <div className="p-2 bg-red-50 text-red-700 rounded text-sm mb-3">
          {error}
        </div>
      )}

      {loading || !data ? (
        <p className="text-sm text-gray-400 text-center py-6">Chargement…</p>
      ) : total === 0 ? (
        <div className="text-sm text-gray-500 text-center py-6">
          Aucune cliente segmentée.{' '}
          <button onClick={runNow} className="text-vz-teal underline">
            Lancer un premier calcul
          </button>
          .
        </div>
      ) : (
        <ul className="space-y-2">
          {data.segments.map((seg) => {
            const pct = total > 0 ? (seg.count / total) * 100 : 0;
            return (
              <li key={seg.segment} className="flex items-center gap-3">
                <span
                  className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium min-w-[120px] text-center ${
                    SEGMENT_COLORS[seg.segment] || 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {SEGMENT_LABELS[seg.segment] || seg.segment}
                </span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-vz-teal h-2 rounded-full"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-sm text-black font-medium min-w-[60px] text-right">
                  {seg.count} ({pct.toFixed(0)}%)
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {data && total > 0 && (
        <p className="mt-3 text-xs text-gray-400">
          Total clientes segmentées : <strong>{total}</strong> · refresh
          automatique le 1<sup>er</sup> du mois à 04:00.
        </p>
      )}
    </Card>
  );
}
