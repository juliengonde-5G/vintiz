'use client';

import React, { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

type Forecast = {
  date: string;
  season_coef: number;
  weekday_weight: number;
  school_holiday: { name: string; boost_pct: number } | null;
  events: {
    id: string;
    title: string;
    location: string;
    date_start: string;
    date_end: string;
    boost_pct: number;
    description?: string | null;
  }[];
  operations: {
    id: string;
    name: string;
    op_type: string;
    discount_pct: number;
    date_end: string;
  }[];
  monthly_target: number;
  day_forecast_revenue: number;
  final_coef: number;
};

type Props = { date: string };

export default function CahierForecastPanel({ date }: Props) {
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const res = await api.get(`/api/cahier/${date}/forecast`);
        if (!cancelled && res.ok) setForecast(await res.json());
      } catch { /* silent */ }
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [date]);

  if (loading || !forecast) return null;

  const coefPct = ((forecast.final_coef - 1) * 100).toFixed(0);

  return (
    <Card title="Prévisionnel & contexte local">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Stat label="CA prévu" value={`${forecast.day_forecast_revenue.toFixed(0)} €`} accent />
        <Stat label="Objectif mois" value={`${forecast.monthly_target.toFixed(0)} €`} />
        <Stat
          label="Coefficient jour"
          value={`${forecast.final_coef.toFixed(2)}× (${forecast.final_coef >= 1 ? '+' : ''}${coefPct}%)`}
        />
        <Stat label="Poids jour de la semaine" value={`×${forecast.weekday_weight.toFixed(2)}`} />
      </div>

      {forecast.school_holiday && (
        <div className="mb-3 p-2 rounded-lg bg-yellow-50 text-yellow-800 text-sm">
          🎒 Vacances {forecast.school_holiday.name} (zone B Vernon)
          {forecast.school_holiday.boost_pct ? ` · +${forecast.school_holiday.boost_pct}% trafic estimé` : ''}
        </div>
      )}

      {forecast.events.length > 0 && (
        <div className="mb-3">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
            Événements Vernon / Giverny
          </h4>
          <ul className="space-y-1">
            {forecast.events.map((e) => (
              <li key={e.id} className="text-sm text-black flex items-center gap-2">
                <span>📍 {e.location}</span>
                <span className="font-medium">{e.title}</span>
                {e.boost_pct !== 0 && (
                  <span className={`text-xs ${e.boost_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {e.boost_pct > 0 ? '+' : ''}{e.boost_pct}%
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {forecast.operations.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
            Opérations commerciales en cours
          </h4>
          <ul className="space-y-1">
            {forecast.operations.map((o) => (
              <li key={o.id} className="text-sm text-black">
                🏷️ <span className="font-medium">{o.name}</span> · -{o.discount_pct}%
                <span className="text-xs text-gray-500"> · jusqu'au {o.date_end}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`p-3 rounded-lg ${accent ? 'bg-vz-teal-soft text-vz-teal' : 'bg-gray-50 text-black'}`}>
      <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}
