'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface EssReport {
  period_days: number;
  pieces_received: number;
  pieces_sold: number;
  pieces_donated: number;
  pieces_returned_to_sorting: number;
  reuse_rate: number;
  estimated_tonnage_kg: number;
  revenue: number;
  ca_reversed_to_st: number;
  ca_reversed_pct: number;
  unique_clients: number;
  config: {
    avg_piece_weight_kg: number;
    ess_reversed_pct: number;
  };
}

function formatKg(value: number): string {
  if (value >= 1000) return (value / 1000).toFixed(2).replace('.', ',') + ' t';
  return value.toFixed(0) + ' kg';
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + ' €';
}

const PERIODS = [30, 90, 365];

export default function EssReportCard() {
  const [period, setPeriod] = useState(90);
  const [data, setData] = useState<EssReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/reports/ess?period_days=${period}`);
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
  }, [period]);

  useEffect(() => { load(); }, [load]);

  return (
    <Card title="Rapport ESS — Solidarité Textiles (P4-002)">
      <div className="flex justify-between items-center mb-4">
        <p className="text-xs text-gray-500">
          Réemploi, tonnage estimé, CA reversé sur la fenêtre.
        </p>
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-xs font-medium ${
                period === p ? 'bg-white text-teal shadow-sm' : 'text-gray-500'
              }`}
            >
              {p}j
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-2 bg-red-50 text-red-700 rounded text-sm mb-3">
          {error}
        </div>
      )}

      {loading || !data ? (
        <p className="text-sm text-gray-400 text-center py-6">Chargement…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-xs text-gray-500 mb-1">Pièces reçues</p>
              <p className="text-lg font-bold text-black">{data.pieces_received}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Vendues</p>
              <p className="text-lg font-bold text-teal">{data.pieces_sold}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Données</p>
              <p className="text-lg font-bold text-black">{data.pieces_donated}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Retour tri</p>
              <p className="text-lg font-bold text-orange-600">
                {data.pieces_returned_to_sorting}
              </p>
            </div>
          </div>

          <div className="pt-3 border-t border-gray-100 grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-gray-500 mb-1">Taux de réemploi</p>
              <p className="text-lg font-semibold text-teal">
                {(data.reuse_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Tonnage estimé</p>
              <p className="text-lg font-semibold text-black">
                {formatKg(data.estimated_tonnage_kg)}
              </p>
              <p className="text-xs text-gray-400">
                base {data.config.avg_piece_weight_kg} kg/pièce
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">
                CA reversé ({data.ca_reversed_pct.toFixed(1)}%)
              </p>
              <p className="text-lg font-semibold text-pink">
                {formatCurrency(data.ca_reversed_to_st)}
              </p>
            </div>
          </div>
        </>
      )}

      <div className="mt-3 flex justify-end">
        <Button size="sm" variant="secondary" onClick={load}>
          Rafraîchir
        </Button>
      </div>
    </Card>
  );
}
