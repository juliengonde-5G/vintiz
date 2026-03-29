'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface DashboardData {
  today: { revenue: number; transaction_count: number; avg_basket: number };
  stock: { count: number; value: number };
  top_products_week: { name: string; quantity: number; revenue: number }[];
  recent_transactions: {
    id: string;
    transaction_number: number;
    total_ttc: number;
    type: string;
    created_at: string;
  }[];
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

function SkeletonBlock({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded-lg ${className}`} />
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await api.get('/api/reports/dashboard');
      if (!res.ok) throw new Error('Erreur lors du chargement');
      const json = await res.json();
      setData(json);
      setError('');
    } catch {
      setError('Impossible de charger le tableau de bord. Verifiez votre connexion.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 60000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const kpis = data
    ? [
        {
          label: 'CA du jour',
          value: formatCurrency(data.today.revenue),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="1" x2="12" y2="23" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          ),
        },
        {
          label: 'Articles en stock',
          value: String(data.stock.count),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            </svg>
          ),
        },
        {
          label: "Transactions aujourd'hui",
          value: String(data.today.transaction_count),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
          ),
        },
        {
          label: 'Panier moyen',
          value: formatCurrency(data.today.avg_basket),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
            </svg>
          ),
        },
      ]
    : [];

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-black">Tableau de bord</h1>
          <p className="text-gray-500 mt-1">Bienvenue sur Vintiz</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <Card key={i} className="flex items-start gap-4">
                  <SkeletonBlock className="w-14 h-14 shrink-0" />
                  <div className="flex-1 space-y-2">
                    <SkeletonBlock className="h-4 w-24" />
                    <SkeletonBlock className="h-8 w-20" />
                  </div>
                </Card>
              ))
            : kpis.map((kpi) => (
                <Card key={kpi.label} className="flex items-start gap-4">
                  <div className="p-3 bg-teal-50 rounded-lg shrink-0">{kpi.icon}</div>
                  <div>
                    <p className="text-sm text-gray-500">{kpi.label}</p>
                    <p className="text-2xl font-bold text-black mt-1">{kpi.value}</p>
                  </div>
                </Card>
              ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Top 5 Products */}
          <Card title="Top 5 produits cette semaine">
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <SkeletonBlock key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : data && data.top_products_week && data.top_products_week.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="pb-2 text-sm font-semibold text-gray-600">Produit</th>
                      <th className="pb-2 text-sm font-semibold text-gray-600 text-right">Qte</th>
                      <th className="pb-2 text-sm font-semibold text-gray-600 text-right">CA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_products_week.slice(0, 5).map((p, i) => (
                      <tr key={i} className="border-b border-gray-50">
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
              <p className="text-gray-400 text-center py-4">Aucune donnee</p>
            )}
          </Card>

          {/* Recent Transactions */}
          <Card title="Dernieres transactions">
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <SkeletonBlock key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : data && data.recent_transactions && data.recent_transactions.length > 0 ? (
              <div className="space-y-2">
                {data.recent_transactions.slice(0, 10).map((tx) => (
                  <div
                    key={tx.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="text-sm font-medium text-black">
                        Ticket #{tx.transaction_number}
                      </p>
                      <p className="text-xs text-gray-500">{tx.created_at ? formatDate(tx.created_at) : ''}</p>
                    </div>
                    <p className="font-bold text-teal">{formatCurrency(tx.total_ttc)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 text-center py-4">Aucune transaction</p>
            )}
          </Card>
        </div>

        {/* Quick Actions */}
        <Card title="Actions rapides">
          <div className="flex flex-wrap gap-4">
            <Link href="/pos">
              <Button size="lg">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                  <circle cx="9" cy="21" r="1" />
                  <circle cx="20" cy="21" r="1" />
                  <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                </svg>
                Nouvelle vente
              </Button>
            </Link>
            <Link href="/inventory/new">
              <Button variant="secondary" size="lg">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Ajouter un produit
              </Button>
            </Link>
          </div>
        </Card>
      </main>
    </div>
  );
}
