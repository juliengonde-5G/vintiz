'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

interface CategoryAgg {
  category_id: string;
  category_name?: string;
  revenue: number;
  qty_sold: number;
}

interface RetailKpis {
  period_days: number;
  revenue: number;
  net_revenue: number;
  refunds: number;
  transactions: number;
  items_sold: number;
  ait: number;
  ca_per_m2_per_month: number;
  sell_through_rate: number;
  days_on_hand: number;
  gmroi: number | null;
  on_floor_count: number;
  prev_period: { revenue: number; transactions: number; items_sold: number };
  change_pct: { revenue: number | null; transactions: number | null; items_sold: number | null };
  top_categories: CategoryAgg[];
  bottom_categories: CategoryAgg[];
  config: { store_surface_m2: number };
}


function ChangeBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-gray-400">—</span>;
  const positive = value >= 0;
  return (
    <span
      className={`text-xs font-medium ${
        positive ? 'text-green-600' : 'text-red-600'
      }`}
    >
      {positive ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

const PERIODS = [7, 30, 90];

export default function RetailKpisCard() {
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<RetailKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/reports/retail-kpis?period_days=${period}`);
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
    <Card title="KPIs retail (P4-001)">
      <div className="flex justify-between items-center mb-4">
        <p className="text-xs text-gray-500">
          Sell-through, GMROI, jours sur étagère sur {period} jours.
        </p>
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-xs font-medium ${
                period === p ? 'bg-white text-vz-teal shadow-sm' : 'text-gray-500'
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
              <p className="text-xs text-gray-500 mb-1">CA net</p>
              <p className="text-lg font-bold text-vz-teal">
                {formatCurrency(data.net_revenue)}
              </p>
              <ChangeBadge value={data.change_pct.revenue} />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Articles vendus</p>
              <p className="text-lg font-bold text-black">{data.items_sold}</p>
              <ChangeBadge value={data.change_pct.items_sold} />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Panier moyen (AIT)</p>
              <p className="text-lg font-bold text-black">
                {data.ait.toFixed(2)}{' '}
                <span className="text-xs text-gray-400">art./ticket</span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">CA / m² / mois</p>
              <p className="text-lg font-bold text-black">
                {formatCurrency(data.ca_per_m2_per_month)}
              </p>
              <p className="text-xs text-gray-400">
                {data.config.store_surface_m2} m²
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-2 pt-3 border-t border-gray-100">
            <div>
              <p className="text-xs text-gray-500 mb-1">Sell-through</p>
              <p className="text-base font-semibold text-black">
                {(data.sell_through_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Jours sur étagère</p>
              <p className="text-base font-semibold text-black">
                {data.days_on_hand.toFixed(0)} j
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">GMROI</p>
              <p className="text-base font-semibold text-black">
                {data.gmroi !== null ? data.gmroi.toFixed(2) : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Stock vitrine</p>
              <p className="text-base font-semibold text-black">
                {data.on_floor_count} pièces
              </p>
            </div>
          </div>

          {data.top_categories.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Top catégories
              </p>
              <ul className="space-y-1">
                {data.top_categories.slice(0, 5).map((c) => (
                  <li
                    key={c.category_id}
                    className="flex justify-between text-sm"
                  >
                    <span className="text-gray-700 truncate max-w-[200px]">
                      {c.category_name || `${c.category_id.slice(0, 8)}…`}
                    </span>
                    <span className="text-vz-teal font-medium">
                      {formatCurrency(c.revenue)} · {c.qty_sold} pièces
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
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
