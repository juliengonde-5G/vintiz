'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

type Tab = 'daily' | 'weekly' | 'monthly';

interface ReportData {
  gross_revenue: number;
  refunds: number;
  net_revenue: number;
  transaction_count: number;
  average_basket: number;
  top_products: { name: string; quantity: number; revenue: number }[];
}

interface StockValue {
  total_items: number;
  total_value: number;
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
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
      <main className="md:ml-64 p-6 md:p-8">
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
              className={`px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] transition-colors ${
                tab === t.key
                  ? 'bg-white text-teal shadow-sm'
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
                <p className="text-xl font-bold text-black">{formatCurrency(report.gross_revenue)}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">Remboursements</p>
                <p className="text-xl font-bold text-red-600">{formatCurrency(report.refunds)}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">CA net</p>
                <p className="text-xl font-bold text-teal">{formatCurrency(report.net_revenue)}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">Transactions</p>
                <p className="text-xl font-bold text-black">{report.transaction_count}</p>
              </Card>
              <Card>
                <p className="text-xs text-gray-500 mb-1">Panier moyen</p>
                <p className="text-xl font-bold text-black">{formatCurrency(report.average_basket)}</p>
              </Card>
            </div>

            {/* Top Products */}
            <Card title="Top 10 produits" className="mb-8">
              {report.top_products && report.top_products.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-2 text-sm font-semibold text-gray-600">#</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Produit</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600 text-right">Quantite</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600 text-right">CA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.top_products.slice(0, 10).map((p, i) => (
                        <tr key={i} className="border-b border-gray-50">
                          <td className="py-2 text-sm text-gray-400">{i + 1}</td>
                          <td className="py-2 text-sm text-black">{p.name}</td>
                          <td className="py-2 text-sm text-gray-600 text-right">{p.quantity}</td>
                          <td className="py-2 text-sm font-medium text-teal text-right">
                            {formatCurrency(p.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-400 text-center py-4">Aucun produit vendu</p>
              )}
            </Card>
          </>
        ) : null}

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
                <p className="text-xl font-bold text-black">{stockValue.total_items}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Valeur totale</p>
                <p className="text-xl font-bold text-teal">{formatCurrency(stockValue.total_value)}</p>
              </div>
            </div>
          ) : (
            <p className="text-gray-400 text-center py-4">Donnees indisponibles</p>
          )}
        </Card>
      </main>
    </div>
  );
}
