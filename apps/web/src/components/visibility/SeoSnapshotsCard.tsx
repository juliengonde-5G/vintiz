'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface Snapshot {
  id: string;
  score: number;
  response_ms: number | null;
  fetched_at: string;
}

function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
  });
}

function colorFor(score: number): string {
  if (score >= 85) return '#16a34a';
  if (score >= 60) return '#f59e0b';
  return '#dc2626';
}

export default function SeoSnapshotsCard() {
  const [snaps, setSnaps] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/seo/snapshots?days=30');
      if (res.ok) {
        setSnaps(await res.json());
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
    setBusy(true);
    try {
      const res = await api.post('/api/seo/snapshots/run', {});
      if (res.ok) await load();
    } catch { /* silent */ }
    setBusy(false);
  };

  const max = Math.max(100, ...snaps.map(s => s.score));
  const min = Math.min(0, ...snaps.map(s => s.score));
  const range = Math.max(1, max - min);

  return (
    <Card title="Évolution score SEO (30 derniers jours)">
      <div className="flex justify-between items-center mb-3">
        <p className="text-xs text-gray-500">
          {snaps.length} snapshot{snaps.length > 1 ? 's' : ''} — refresh quotidien automatique 05:00.
        </p>
        <Button size="sm" variant="secondary" onClick={runNow} disabled={busy}>
          {busy ? 'Snapshot…' : 'Snapshot maintenant'}
        </Button>
      </div>

      {error && <div className="p-2 bg-red-50 text-red-700 rounded text-sm mb-3">{error}</div>}

      {loading ? (
        <p className="text-sm text-gray-400 text-center py-6">Chargement…</p>
      ) : snaps.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6">
          Aucun snapshot. Cliquez « Snapshot maintenant » pour démarrer la série.
        </p>
      ) : (
        <div>
          {/* Mini bar chart — pure SVG, no dependency */}
          <svg
            viewBox={`0 0 ${Math.max(snaps.length * 20, 100)} 80`}
            className="w-full h-24"
            preserveAspectRatio="none"
          >
            {snaps.map((s, idx) => {
              const x = idx * 20 + 5;
              const h = ((s.score - min) / range) * 60 + 5;
              return (
                <g key={s.id}>
                  <rect
                    x={x}
                    y={75 - h}
                    width={12}
                    height={h}
                    fill={colorFor(s.score)}
                    rx={1}
                  />
                  <title>{`${dayLabel(s.fetched_at)} — ${s.score}/100`}</title>
                </g>
              );
            })}
          </svg>
          <div className="mt-2 text-xs text-gray-400 flex justify-between">
            <span>{snaps.length > 0 ? dayLabel(snaps[0].fetched_at) : ''}</span>
            <span>
              dernier : <strong className="text-black">{snaps[snaps.length - 1]?.score}/100</strong>
            </span>
            <span>{snaps.length > 0 ? dayLabel(snaps[snaps.length - 1].fetched_at) : ''}</span>
          </div>
        </div>
      )}
    </Card>
  );
}
