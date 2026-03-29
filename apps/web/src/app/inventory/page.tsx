'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';

const statusLabels: Record<string, { label: string; variant: 'stock' | 'display' | 'sold' | 'returned' }> = {
  stock: { label: 'En stock', variant: 'stock' },
  display: { label: 'En vitrine', variant: 'display' },
  sold: { label: 'Vendu', variant: 'sold' },
  returned: { label: 'Retourne', variant: 'returned' },
};

const categories = ['Toutes', 'Robes', 'Hauts', 'Bas', 'Accessoires', 'Chaussures'];
const statuses = ['Tous', 'stock', 'display', 'sold', 'returned'];

export default function InventoryPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('Toutes');
  const [status, setStatus] = useState('Tous');
  const [currentPage, setCurrentPage] = useState(1);

  // Placeholder data
  const data: Record<string, unknown>[] = [];
  const totalPages = 1;

  const columns = [
    {
      key: 'photo',
      header: 'Photo',
      className: 'w-16',
      render: () => (
        <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
        </div>
      ),
    },
    { key: 'name', header: 'Nom' },
    { key: 'category', header: 'Categorie' },
    { key: 'size', header: 'Taille' },
    {
      key: 'price',
      header: 'Prix',
      render: (value: unknown) => `${value}\u00A0\u20AC`,
    },
    {
      key: 'status',
      header: 'Statut',
      render: (value: unknown) => {
        const s = statusLabels[value as string] || statusLabels.stock;
        return <Badge variant={s.variant}>{s.label}</Badge>;
      },
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-black">Inventaire</h1>
            <p className="text-gray-500 mt-1">Gestion des produits</p>
          </div>
          <Link href="/inventory/new">
            <Button size="lg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Ajouter un produit
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1">
            <Input
              placeholder="Rechercher un produit..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              }
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="min-h-[44px] px-4 py-2 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal focus:border-teal"
          >
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="min-h-[44px] px-4 py-2 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal focus:border-teal"
          >
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s === 'Tous' ? 'Tous les statuts' : statusLabels[s]?.label || s}
              </option>
            ))}
          </select>
        </div>

        {/* Table */}
        <DataTable
          columns={columns}
          data={data}
          emptyMessage="Aucun produit trouve"
          actions={() => (
            <div className="flex gap-2">
              <button className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors text-gray-500 hover:text-teal" title="Modifier">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
              <button className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-red-50 transition-colors text-gray-500 hover:text-red-600" title="Supprimer">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
              </button>
            </div>
          )}
        />

        {/* Pagination */}
        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-gray-500">
            Page {currentPage} sur {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              Precedent
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            >
              Suivant
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
