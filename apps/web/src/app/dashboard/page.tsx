'use client';

import React from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';

const kpis = [
  {
    label: 'CA du jour',
    value: '0\u00A0\u20AC',
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="1" x2="12" y2="23" />
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
  },
  {
    label: 'Articles en stock',
    value: '0',
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      </svg>
    ),
  },
  {
    label: "Transactions aujourd'hui",
    value: '0',
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
        <line x1="1" y1="10" x2="23" y2="10" />
      </svg>
    ),
  },
  {
    label: 'Panier moyen',
    value: '0\u00A0\u20AC',
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="9" cy="21" r="1" />
        <circle cx="20" cy="21" r="1" />
        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
      </svg>
    ),
  },
];

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-black">Tableau de bord</h1>
          <p className="text-gray-500 mt-1">Bienvenue sur Vintiz</p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
          {kpis.map((kpi) => (
            <Card key={kpi.label} className="flex items-start gap-4">
              <div className="p-3 bg-teal-50 rounded-lg shrink-0">{kpi.icon}</div>
              <div>
                <p className="text-sm text-gray-500">{kpi.label}</p>
                <p className="text-2xl font-bold text-black mt-1">{kpi.value}</p>
              </div>
            </Card>
          ))}
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
