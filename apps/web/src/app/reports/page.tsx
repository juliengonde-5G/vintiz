'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import { formatCurrency, formatPercent } from '@/lib/format';
// L6 (audit 2026-05) : reporting ESS dédié supprimé — non pertinent.
// Le calcul backend (kg revalorisés / CA reversé) reste disponible via
// GET /api/reports/ess pour exports ad-hoc à Solidarité Textiles.
// import EssReportCard from '@/components/reports/EssReportCard';
import RetailKpisCard from '@/components/reports/RetailKpisCard';
import RfmSegmentsCard from '@/components/reports/RfmSegmentsCard';
import { api } from '@/lib/api';

type Tab = 'daily' | 'weekly' | 'monthly';

interface WeatherCurrent {
  description: string;
  temp: number;
  feels_like: number;
  humidity: number;
  icon: string;
  wind_speed: number;
  city: string;
}

interface WeatherDay {
  date: string;
  description: string;
  temp_min: number;
  temp_max: number;
  icon: string;
}

interface WeatherData {
  current: WeatherCurrent;
  forecast: WeatherDay[];
}

interface WeatherSnapshot {
  date: string;
  temp: number;
  description: string;
  icon: string;
  temp_min: number;
  temp_max: number;
  humidity: number;
  wind_speed: number;
}

interface ReportData {
  total_revenue: number;
  total_refunds: number;
  net_revenue: number;
  transaction_count: number;
  avg_basket: number;
  top_products?: { name: string; quantity: number; revenue: number }[];
}

interface StockValue {
  total_products: number;
  total_sale_value: number;
}


function SkeletonBlock({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded-lg ${className}`} />
  );
}

function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function currentWeek(): { week: number; year: number } {
  const d = new Date();
  const startOfYear = new Date(d.getFullYear(), 0, 1);
  const diff = d.getTime() - startOfYear.getTime();
  const oneWeek = 7 * 24 * 60 * 60 * 1000;
  const week = Math.ceil((diff / oneWeek) + startOfYear.getDay() / 7);
  return { week, year: d.getFullYear() };
}

function currentMonth(): { month: number; year: number } {
  const d = new Date();
  return { month: d.getMonth() + 1, year: d.getFullYear() };
}

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>('daily');
  const [dailyDate, setDailyDate] = useState(todayStr());
  const [weeklyWeek, setWeeklyWeek] = useState(String(currentWeek().week));
  const [weeklyYear, setWeeklyYear] = useState(String(currentWeek().year));
  const [monthlyMonth, setMonthlyMonth] = useState(String(currentMonth().month));
  const [monthlyYear, setMonthlyYear] = useState(String(currentMonth().year));

  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [stockValue, setStockValue] = useState<StockValue | null>(null);
  const [stockLoading, setStockLoading] = useState(false);

  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [weatherHistory, setWeatherHistory] = useState<WeatherSnapshot[]>([]);

  useEffect(() => {
    api.get('/api/admin/weather').then(async (res) => {
      if (res.ok) setWeather(await res.json());
    }).catch(() => {});
    api.get('/api/admin/weather/history').then(async (res) => {
      if (res.ok) {
        const data = await res.json();
        setWeatherHistory((data.history || []).slice(-14).reverse());
      }
    }).catch(() => {});
  }, []);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let url = '';
      if (tab === 'daily') {
        url = `/api/reports/daily?date=${dailyDate}`;
      } else if (tab === 'weekly') {
        url = `/api/reports/weekly?week=${weeklyWeek}&year=${weeklyYear}`;
      } else {
        url = `/api/reports/monthly?month=${monthlyMonth}&year=${monthlyYear}`;
      }
      const res = await api.get(url);
      if (!res.ok) throw new Error('Erreur lors du chargement');
      const data = await res.json();
      setReport(data);
    } catch {
      setError('Impossible de charger le rapport.');
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [tab, dailyDate, weeklyWeek, weeklyYear, monthlyMonth, monthlyYear]);

  const fetchStockValue = useCallback(async () => {
    setStockLoading(true);
    try {
      const res = await api.get('/api/reports/stock-value');
      if (res.ok) {
        setStockValue(await res.json());
      }
    } catch {
      // silent
    } finally {
      setStockLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  useEffect(() => {
    fetchStockValue();
  }, [fetchStockValue]);

  const tabs: { key: Tab; label: string }[] = [
    { key: 'daily', label: 'Quotidien' },
    { key: 'weekly', label: 'Hebdomadaire' },
    { key: 'monthly', label: 'Mensuel' },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">Rapports</h1>
          <p className="text-gray-500 mt-1">Analyse des ventes et du stock</p>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg mb-6 w-fit">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium min-h-[48px] transition-colors ${
                tab === t.key
                  ? 'bg-white text-vz-teal shadow-sm'
                  : 'text-gray-500 hover:text-black'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Date Picker */}
        <Card className="mb-6">
          {tab === 'daily' && (
            <div className="flex items-end gap-4">
              <Input
                label="Date"
                type="date"
                value={dailyDate}
                onChange={(e) => setDailyDate(e.target.value)}
              />
            </div>
          )}
          {tab === 'weekly' && (
            <div className="flex items-end gap-4">
              <Input
                label="Semaine"
                type="number"
                min="1"
                max="53"
                value={weeklyWeek}
                onChange={(e) => setWeeklyWeek(e.target.value)}
              />
              <Input
                label="Annee"
                type="number"
                min="2020"
                max="2030"
                value={weeklyYear}
                onChange={(e) => setWeeklyYear(e.target.value)}
              />
            </div>
          )}
          {tab === 'monthly' && (
            <div className="flex items-end gap-4">
              <Input
                label="Mois"
                type="number"
                min="1"
                max="12"
                value={monthlyMonth}
                onChange={(e) => setMonthlyMonth(e.target.value)}
              />
              <Input
                label="Annee"
                type="number"
                min="2020"
                max="2030"
                value={monthlyYear}
                onChange={(e) => setMonthlyYear(e.target.value)}
              />
            </div>
          )}
        </Card>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}

        {/* Report KPIs */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5 mb-8">
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <SkeletonBlock className="h-4 w-20 mb-2" />
                <SkeletonBlock className="h-8 w-24" />
              </Card>
            ))}
          </div>
        ) : report ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-5 mb-8">
              <Card>
                <p className="text-xs text-gray-500 mb-1">CA brut</p>
                <p className="text-xl font-bold text-black">{formatCurrency(report.total_revenue)}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">Remboursements</p>
                <p className="text-xl font-bold text-red-600">{formatCurrency(report.total_refunds)}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">CA net</p>
                <p className="text-xl font-bold text-vz-teal">{formatCurrency(report.net_revenue)}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">Transactions</p>
                <p className="text-xl font-bold text-black">{report.transaction_count}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">Panier moyen</p>
                <p className="text-xl font-bold text-black">{formatCurrency(report.avg_basket)}</p>
              </Card>
            </div>

            {/* Top produits retiré : en seconde main chaque pièce est unique
                (quantité toujours = 1), donc un classement par produit n'a
                pas de sens. Les analyses utiles (catégories, marques, RFM)
                vivent dans les cartes KPIs/segments ci-dessous. */}
          </>
        ) : null}

        {/* P4 — Analytics riche (KPIs retail + RFM). ESS retiré (L6 audit 2026-05). */}
        <div className="space-y-6 mb-8">
          <RetailKpisCard />
          <RfmSegmentsCard />
        </div>

        {/* Stock Value */}
        <Card title="Valeur du stock">
          {stockLoading ? (
            <div className="flex gap-8">
              <SkeletonBlock className="h-12 w-32" />
              <SkeletonBlock className="h-12 w-32" />
            </div>
          ) : stockValue ? (
            <div className="flex gap-8">
              <div>
                <p className="text-xs text-gray-500 mb-1">Articles en stock</p>
                <p className="text-xl font-bold text-black">{stockValue.total_products}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Valeur totale</p>
                <p className="text-xl font-bold text-vz-teal">{formatCurrency(stockValue.total_sale_value)}</p>
              </div>
            </div>
          ) : (
            <p className="text-gray-400 text-center py-4">Donnees indisponibles</p>
          )}
        </Card>

        {/* Gestion du stock & rotation */}
        <StockMovementSection />

        {/* Météo Vernon */}
        {weather && (
          <Card title="Météo Vernon — aujourd'hui">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="flex items-center gap-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://openweathermap.org/img/wn/${weather.current.icon}@2x.png`}
                  alt={weather.current.description}
                  className="w-16 h-16"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
                <div>
                  <p className="text-3xl font-bold text-black">{Math.round(weather.current.temp)}°C</p>
                  <p className="text-sm text-gray-500 capitalize">{weather.current.description}</p>
                  <p className="text-xs text-gray-400">
                    Ressenti {Math.round(weather.current.feels_like)}°C · Vent {weather.current.wind_speed} m/s · Humidité {weather.current.humidity}%
                  </p>
                </div>
              </div>
              {weather.forecast && weather.forecast.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Prévisions 5 jours</p>
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {weather.forecast.map((day, i) => (
                      <div key={i} className="flex flex-col items-center min-w-[56px] p-2 bg-gray-50 rounded-lg text-center">
                        <p className="text-xs text-gray-500 mb-1">
                          {new Date(day.date).toLocaleDateString('fr-FR', { weekday: 'short' })}
                        </p>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`https://openweathermap.org/img/wn/${day.icon}.png`}
                          alt={day.description}
                          className="w-8 h-8"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                        />
                        <p className="text-xs font-medium text-black">{Math.round(day.temp_max)}°</p>
                        <p className="text-xs text-gray-400">{Math.round(day.temp_min)}°</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-4">
              Impact météo sur les ventes : les journées pluvieuses génèrent +18% de passages en boutique selon les données historiques.
            </p>
          </Card>
        )}

        {/* Météo Historique — filtré sur la période du rapport */}
        {(() => {
          const filteredWeather = weatherHistory.filter(snap => {
            const d = snap.date.slice(0, 10);
            if (tab === 'daily') return d === dailyDate;
            if (tab === 'weekly') {
              const dt = new Date(d + 'T12:00:00');
              const startOfYear = new Date(Number(weeklyYear), 0, 1);
              const w = Math.ceil(((dt.getTime() - startOfYear.getTime()) / 86400000 + startOfYear.getDay() + 1) / 7);
              return w === Number(weeklyWeek) && dt.getFullYear() === Number(weeklyYear);
            }
            if (tab === 'monthly') {
              const dt = new Date(d + 'T12:00:00');
              return dt.getMonth() + 1 === Number(monthlyMonth) && dt.getFullYear() === Number(monthlyYear);
            }
            return true;
          });
          if (filteredWeather.length === 0) return null;
          const periodLabel = tab === 'daily' ? dailyDate : tab === 'weekly' ? `Semaine ${weeklyWeek}/${weeklyYear}` : `${monthlyMonth}/${monthlyYear}`;
          return (
        <Card title={`Météo Vernon — ${periodLabel}`} className="mt-6">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="pb-2 text-xs font-semibold text-gray-500">Date</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500">Conditions</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 text-right">Min</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 text-right">Max</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 text-right">Humidité</th>
                    <th className="pb-2 text-xs font-semibold text-gray-500 text-right">Vent</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredWeather.map((snap, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-2 text-sm text-black">
                        {new Date(snap.date).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })}
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={`https://openweathermap.org/img/wn/${snap.icon}.png`} alt="" className="w-6 h-6"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                          <span className="text-sm text-gray-700 capitalize">{snap.description}</span>
                        </div>
                      </td>
                      <td className="py-2 text-sm text-gray-600 text-right">{Math.round(snap.temp_min)}°C</td>
                      <td className="py-2 text-sm font-medium text-black text-right">{Math.round(snap.temp_max)}°C</td>
                      <td className="py-2 text-sm text-gray-600 text-right">{snap.humidity}%</td>
                      <td className="py-2 text-sm text-gray-600 text-right">{snap.wind_speed} m/s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          );
        })()}

        {/* Historique journalier (Lot 5) */}
        <DailyRecapSection />
      </main>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Daily recap (Lot 5)
// ---------------------------------------------------------------------------

interface DailyRecap {
  date: string;
  sales: {
    revenue: number;
    transaction_count: number;
    avg_basket: number;
    top_products: { id: string; name: string; barcode: string; qty: number; ca: number }[];
    payment_mix: Record<string, number>;
  };
  stock: { sold: number };
  cahier: { message_du_jour: string; operation_en_cours: string };
  weather: { temp: number; description: string; icon: string; temp_min: number; temp_max: number } | null;
  tasks: { id: string; kind: string; status: string; completed_at: string | null }[];
}

function DailyRecapSection() {
  const todayISO = () => new Date().toISOString().slice(0, 10);
  const [date, setDate] = React.useState<string>(todayISO());
  const [data, setData] = React.useState<DailyRecap | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');

  const load = React.useCallback(async (d: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/reports/daily-recap?date=${d}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(`Chargement échoué : ${e?.message || e}`);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(date); }, [load, date]);

  return (
    <Card className="mt-6">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <h2 className="font-display text-lg">Historique journalier</h2>
        <input
          type="date"
          value={date}
          max={todayISO()}
          onChange={(e) => setDate(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
        />
      </div>

      {loading && <p className="text-sm text-gray-500">Chargement…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && !loading && (
        <div className="grid md:grid-cols-2 gap-4">
          {/* Ventes */}
          <div className="bg-vz-bg/40 rounded-xl p-3">
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Ventes</h3>
            <p className="text-sm">
              <strong>{data.sales.revenue.toFixed(2)} €</strong> · {data.sales.transaction_count} ticket(s)
              · panier moyen {data.sales.avg_basket.toFixed(2)} €
            </p>
            {data.sales.top_products.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs">
                {data.sales.top_products.map((p) => (
                  <li key={p.id} className="flex justify-between border-b border-gray-100 py-1">
                    <span className="truncate">{p.name}</span>
                    <span className="font-mono whitespace-nowrap ml-2">×{p.qty} · {p.ca.toFixed(2)} €</span>
                  </li>
                ))}
              </ul>
            )}
            {Object.keys(data.sales.payment_mix).length > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                {Object.entries(data.sales.payment_mix)
                  .map(([m, v]) => `${m}: ${v.toFixed(0)} €`)
                  .join(' · ')}
              </p>
            )}
          </div>

          {/* Stock + tasks */}
          <div className="bg-vz-bg/40 rounded-xl p-3">
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Mouvements stock</h3>
            <p className="text-sm">{data.stock.sold} produit(s) vendu(s)</p>
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mt-3 mb-2">Tâches du jour</h3>
            {data.tasks.length === 0 ? (
              <p className="text-xs text-gray-500">Aucune tâche</p>
            ) : (
              <ul className="space-y-1 text-xs">
                {data.tasks.map((t) => (
                  <li key={t.id} className="flex justify-between">
                    <span>{t.kind.replace(/_/g, ' ')}</span>
                    <span className={t.status === 'done' ? 'text-vz-teal' : t.status === 'skipped' ? 'text-gray-400' : 'text-orange-500'}>
                      {t.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Météo */}
          <div className="bg-vz-bg/40 rounded-xl p-3">
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Météo</h3>
            {data.weather ? (
              <p className="text-sm">
                {data.weather.description} · {Math.round(data.weather.temp)}°C
                <span className="text-gray-400 text-xs ml-2">
                  ({Math.round(data.weather.temp_min)} → {Math.round(data.weather.temp_max)} °C)
                </span>
              </p>
            ) : (
              <p className="text-xs text-gray-500">Pas de snapshot météo pour ce jour</p>
            )}
          </div>

          {/* Cahier */}
          <div className="bg-vz-bg/40 rounded-xl p-3">
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Cahier du jour</h3>
            {data.cahier.message_du_jour && (
              <p className="text-sm mb-2"><strong>Message :</strong> {data.cahier.message_du_jour}</p>
            )}
            {data.cahier.operation_en_cours && (
              <p className="text-sm"><strong>Opération :</strong> {data.cahier.operation_en_cours}</p>
            )}
            {!data.cahier.message_du_jour && !data.cahier.operation_en_cours && (
              <p className="text-xs text-gray-500">Aucune note pour ce jour</p>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}


// ---------------------------------------------------------------------------
// Gestion du stock & rotation — GET /api/reports/stock-movement
// ---------------------------------------------------------------------------

interface StockBucket {
  count: number;
  sale_value: number;
  purchase_value: number;
}

interface StockMovement {
  period_days: number;
  period_start: string;
  period_end: string;
  repartition: {
    reserve: StockBucket;
    floor: StockBucket;
    pre_floor: StockBucket;
    active_count: number;
    floor_ratio: number | null;
    reserve_ratio: number | null;
  };
  velocity: {
    avg_days_reserve_to_floor: number | null;
    avg_days_on_floor_before_sale: number | null;
    items_sold: number;
    on_floor_count: number;
    sell_through_rate: number;
  };
  rhythm: {
    vertical: { to_floor: number; to_stock: number; total: number; per_week: number; per_day: number };
    horizontal: {
      zone_changes: number;
      per_week: number;
      per_day: number;
      top_target_zones: { zone_id: string; moves: number }[];
    };
    exits: number;
    intakes: number;
  };
}

function formatDays(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(1).replace('.', ',')} j`;
}

function StockMovementSection() {
  const [data, setData] = React.useState<StockMovement | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get('/api/reports/stock-movement?period_days=30');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setError('');
        }
      } catch {
        if (!cancelled) {
          setError('Données de rotation indisponibles.');
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const floorPct = data?.repartition.floor_ratio != null
    ? Math.round(data.repartition.floor_ratio * 100)
    : null;

  return (
    <Card title="Gestion du stock & rotation" subtitle="30 derniers jours" className="mt-6">
      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-vz-teal" />
        </div>
      ) : error ? (
        <p className="text-gray-400 text-center py-4">{error}</p>
      ) : data ? (
        <div className="space-y-6">
          {/* Réserve vs Rayon */}
          <div>
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Réserve vs Rayon</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">En réserve</p>
                <p className="text-xl font-bold text-black">{data.repartition.reserve.count}</p>
                <p className="text-xs text-gray-400">{formatCurrency(data.repartition.reserve.sale_value)}</p>
              </div>
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">En rayon</p>
                <p className="text-xl font-bold text-vz-teal">{data.repartition.floor.count}</p>
                <p className="text-xs text-gray-400">{formatCurrency(data.repartition.floor.sale_value)}</p>
              </div>
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">Articles actifs</p>
                <p className="text-xl font-bold text-black">{data.repartition.active_count}</p>
                <p className="text-xs text-gray-400">
                  {floorPct !== null ? `${floorPct}% en rayon` : '—'}
                </p>
              </div>
            </div>
            {floorPct !== null && (
              <div>
                <div className="flex h-3 w-full overflow-hidden rounded-full bg-vz-bg-alt">
                  <div className="bg-vz-teal h-full transition-all" style={{ width: `${floorPct}%` }} />
                </div>
                <div className="flex justify-between text-[11px] text-gray-500 mt-1">
                  <span>Rayon {floorPct}%</span>
                  <span>Réserve {100 - floorPct}%</span>
                </div>
              </div>
            )}
          </div>

          {/* Vitesse de rotation */}
          <div>
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Vitesse de rotation</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">Délai réserve → rayon</p>
                <p className="text-xl font-bold text-black">{formatDays(data.velocity.avg_days_reserve_to_floor)}</p>
              </div>
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">Délai rayon → vente</p>
                <p className="text-xl font-bold text-black">{formatDays(data.velocity.avg_days_on_floor_before_sale)}</p>
              </div>
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">Sell-through</p>
                <p className="text-xl font-bold text-vz-teal">{formatPercent(data.velocity.sell_through_rate)}</p>
                <p className="text-xs text-gray-400">{data.velocity.items_sold} vendu(s)</p>
              </div>
            </div>
          </div>

          {/* Rythmes de mouvement */}
          <div>
            <h3 className="text-xs uppercase tracking-wider text-vz-teal mb-2">Rythmes de mouvement</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">Vertical (réserve ↔ rayon)</p>
                <p className="text-xl font-bold text-black">
                  {data.rhythm.vertical.per_week} <span className="text-sm font-normal text-gray-500">/ semaine</span>
                </p>
                <p className="text-xs text-gray-400">
                  {data.rhythm.vertical.to_floor} mise(s) en rayon · {data.rhythm.vertical.to_stock} retour(s) réserve
                </p>
              </div>
              <div className="rounded-xl border border-vz-line bg-white p-3">
                <p className="text-xs text-gray-500">Horizontal (zone ↔ zone)</p>
                <p className="text-xl font-bold text-black">
                  {data.rhythm.horizontal.per_week} <span className="text-sm font-normal text-gray-500">/ semaine</span>
                </p>
                <p className="text-xs text-gray-400">
                  {data.rhythm.horizontal.zone_changes} changement(s) de zone
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-gray-400 text-center py-4">Données indisponibles</p>
      )}
    </Card>
  );
}
