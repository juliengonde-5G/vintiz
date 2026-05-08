'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

const statusLabels: Record<string, { label: string; variant: 'stock' | 'display' | 'sold' | 'returned' }> = {
  stock: { label: 'En stock', variant: 'stock' },
  display: { label: 'En vitrine', variant: 'display' },
  sold: { label: 'Vendu', variant: 'sold' },
  returned: { label: 'Retourne', variant: 'returned' },
};

interface Category {
  id: string;
  name: string;
}

interface Product {
  id: string;
  barcode: string;
  name: string;
  category_id: string;
  category?: { id: string; name: string };
  size: string | null;
  color: string | null;
  brand: string | null;
  purchase_price: number;
  sale_price: number;
  status: string;
  trend_score: number | null;
  week_number: number | null;
  shelf_date: string | null;
  zone_name: string | null;
  photo_url?: string | null;
}

function formatShelfDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return '-';
  }
}


export default function InventoryPage() {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const pageSize = 20;

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(currentPage),
        page_size: String(pageSize),
      });
      if (search) params.set('search', search);
      if (categoryFilter) params.set('category_id', categoryFilter);
      if (statusFilter) params.set('status', statusFilter);

      const res = await api.get(`/api/inventory/products?${params}`);
      if (res.ok) {
        const data = await res.json();
        setProducts(data.items || []);
        setTotal(data.total || 0);
        setTotalPages(data.pages || 1);
        setError('');
      } else {
        setError('Impossible de charger les produits');
      }
    } catch (e) {
      console.error('inventory fetch failed', e);
      setError('Erreur réseau — vérifiez votre connexion');
    } finally {
      setLoading(false);
    }
  }, [currentPage, search, categoryFilter, statusFilter]);

  useEffect(() => {
    let cancelled = false;
    api
      .get('/api/inventory/categories')
      .then(async (res) => {
        if (cancelled) return;
        if (res.ok) {
          setCategories(await res.json());
        }
      })
      .catch((e) => {
        if (!cancelled) console.error('categories fetch failed', e);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const timer = setTimeout(fetchProducts, 300);
    return () => clearTimeout(timer);
  }, [fetchProducts]);

  const handleDelete = async (id: string) => {
    if (!confirm('Supprimer ce produit ?')) return;
    const res = await api.delete(`/api/inventory/products/${id}`);
    if (res.ok) fetchProducts();
  };

  const getCategoryName = (p: Product) => {
    if (p.category?.name) return p.category.name;
    const cat = categories.find(c => c.id === p.category_id);
    return cat?.name || '-';
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-black">Inventaire</h1>
            <p className="text-gray-500 mt-1">{total} produit{total > 1 ? 's' : ''}</p>
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

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
        )}

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1">
            <Input
              placeholder="Rechercher par nom, code-barres, marque..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              }
            />
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setCurrentPage(1); }}
            className="min-h-[48px] px-4 py-2 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
          >
            <option value="">Toutes les categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
            className="min-h-[48px] px-4 py-2 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
          >
            <option value="">Tous les statuts</option>
            <option value="stock">En stock</option>
            <option value="display">En vitrine</option>
            <option value="sold">Vendu</option>
            <option value="returned">Retourne</option>
          </select>
        </div>

        {/* Table */}
        {loading ? (
          <Card>
            <p className="text-gray-400 text-center py-8">Chargement...</p>
          </Card>
        ) : products.length === 0 ? (
          <Card>
            <p className="text-gray-400 text-center py-8">Aucun produit trouve</p>
          </Card>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-3 py-3 text-sm font-semibold text-gray-600 w-14">Photo</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Nom</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Code</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Categorie</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Marque</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Taille</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600 text-right">Prix achat</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600 text-right">Prix vente</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Statut</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Mise en rayon</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Emplacement</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600 text-right">Score</th>
                  <th className="px-4 py-3 text-sm font-semibold text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const s = statusLabels[p.status] || statusLabels.stock;
                  return (
                    <tr
                      key={p.id}
                      className="border-b border-gray-100 hover:bg-vz-accent-soft transition-colors cursor-pointer"
                      onClick={() => router.push('/inventory/' + p.id)}
                    >
                      <td className="px-3 py-2">
                        <div className="w-12 h-12 rounded-lg overflow-hidden bg-gray-100 flex items-center justify-center flex-shrink-0">
                          {p.photo_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={p.photo_url} alt={p.name}
                              className="w-full h-full object-cover"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                          ) : (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" strokeWidth="1.5">
                              <rect x="3" y="3" width="18" height="18" rx="2"/>
                              <circle cx="8.5" cy="8.5" r="1.5"/>
                              <polyline points="21 15 16 10 5 21"/>
                            </svg>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-black">{p.name}</td>
                      <td className="px-4 py-3 text-sm text-gray-500 font-mono text-xs">{p.barcode}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{getCategoryName(p)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{p.brand || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{p.size || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-500 text-right">{formatCurrency(p.purchase_price)}</td>
                      <td className="px-4 py-3 text-sm font-medium text-vz-teal text-right">{formatCurrency(p.sale_price)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={s.variant}>{s.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{formatShelfDate(p.shelf_date)}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{p.zone_name || '-'}</td>
                      <td className="px-4 py-3 text-sm text-right">
                        {p.trend_score != null ? (
                          <span className={`font-medium ${p.trend_score >= 70 ? 'text-green-600' : p.trend_score >= 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {p.trend_score}
                          </span>
                        ) : (
                          <span className="text-gray-300">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDelete(p.id); }}
                            className="min-h-[36px] min-w-[36px] flex items-center justify-center rounded-lg hover:bg-red-50 transition-colors text-gray-400 hover:text-red-600"
                            title="Supprimer"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <p className="text-sm text-gray-500">
              Page {currentPage} sur {totalPages} ({total} produits)
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
        )}
      </main>
    </div>
  );
}
