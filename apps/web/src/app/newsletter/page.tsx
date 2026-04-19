'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface Subscriber {
  id: string;
  email: string;
  consent_date: string;
  consent_ip: string | null;
  source: string;
  is_active: boolean;
  unsubscribed_at: string | null;
  created_at: string;
}

interface ListResponse {
  total: number;
  active: number;
  unsubscribed: number;
  results: Subscriber[];
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function NewsletterPage() {
  const [data, setData] = useState<ListResponse | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'active' | 'unsubscribed'>('active');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ status: filter });
      if (search.trim()) params.set('search', search.trim());
      const res = await api.get(`/api/newsletter/subscribers?${params.toString()}`);
      if (!res.ok) throw new Error('Erreur chargement');
      const json: ListResponse = await res.json();
      setData(json);
      setError('');
    } catch {
      setError('Impossible de charger la liste des abonnées.');
    } finally {
      setLoading(false);
    }
  }, [search, filter]);

  useEffect(() => {
    const t = setTimeout(fetchData, 250);
    return () => clearTimeout(t);
  }, [fetchData]);

  async function handleExport() {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const url = `${process.env.NEXT_PUBLIC_API_URL}/api/newsletter/subscribers/export?active_only=true`;
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      alert('Export impossible.');
      return;
    }
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `vintiz-newsletter-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function handleDelete(sub: Subscriber) {
    const confirmed = window.confirm(
      `Supprimer définitivement ${sub.email} ?\n\n` +
      `Cette action exerce le droit à l'effacement (RGPD art. 17). ` +
      `Toutes les données liées (y compris le trail de consentement) seront effacées.`
    );
    if (!confirmed) return;
    const res = await api.delete(`/api/newsletter/subscribers/${sub.id}`);
    if (res.ok) {
      fetchData();
    } else {
      alert('Suppression impossible.');
    }
  }

  return (
    <div className="min-h-screen bg-cream">
      <Sidebar />
      <main className="md:ml-64 px-4 py-6 md:px-8 md:py-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-6">
            <div>
              <h1 className="font-display text-2xl text-black">Newsletter</h1>
              <p className="text-sm text-black/60 mt-1">
                Abonnées à la communication du site (RGPD — consentement explicite).
              </p>
            </div>
            <Button variant="outline" onClick={handleExport}>
              Exporter CSV (actives)
            </Button>
          </div>

          <div className="grid grid-cols-3 gap-3 mb-6">
            <Card>
              <p className="text-xs uppercase tracking-wider text-black/50">Total</p>
              <p className="text-3xl font-display text-black mt-1">{data?.total ?? '—'}</p>
            </Card>
            <Card>
              <p className="text-xs uppercase tracking-wider text-black/50">Actives</p>
              <p className="text-3xl font-display text-teal mt-1">{data?.active ?? '—'}</p>
            </Card>
            <Card>
              <p className="text-xs uppercase tracking-wider text-black/50">Désinscrites</p>
              <p className="text-3xl font-display text-black/60 mt-1">{data?.unsubscribed ?? '—'}</p>
            </Card>
          </div>

          <Card>
            <div className="flex flex-col md:flex-row gap-3 mb-4">
              <Input
                placeholder="Rechercher un email…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1"
              />
              <div className="flex gap-2">
                {(['active', 'all', 'unsubscribed'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      filter === f
                        ? 'bg-teal text-white'
                        : 'bg-white border border-black/10 text-black/70 hover:bg-black/5'
                    }`}
                  >
                    {f === 'active' ? 'Actives' : f === 'all' ? 'Toutes' : 'Désinscrites'}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
                {error}
              </div>
            )}

            {loading && !data ? (
              <p className="text-sm text-black/50 py-8 text-center">Chargement…</p>
            ) : !data || data.results.length === 0 ? (
              <p className="text-sm text-black/50 py-8 text-center">
                Aucune abonnée ne correspond aux critères.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-black/50 border-b border-black/10">
                      <th className="py-2 pr-4">Email</th>
                      <th className="py-2 pr-4">Consentement</th>
                      <th className="py-2 pr-4">IP</th>
                      <th className="py-2 pr-4">Source</th>
                      <th className="py-2 pr-4">Statut</th>
                      <th className="py-2 pr-4">Désinscription</th>
                      <th className="py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((sub) => (
                      <tr key={sub.id} className="border-b border-black/5">
                        <td className="py-3 pr-4 font-medium text-black">{sub.email}</td>
                        <td className="py-3 pr-4 text-black/60">{formatDate(sub.consent_date)}</td>
                        <td className="py-3 pr-4 text-black/50 font-mono text-xs">
                          {sub.consent_ip || '—'}
                        </td>
                        <td className="py-3 pr-4 text-black/60 text-xs">{sub.source}</td>
                        <td className="py-3 pr-4">
                          {sub.is_active ? (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-teal/15 text-teal">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-black/10 text-black/60">
                              Désinscrite
                            </span>
                          )}
                        </td>
                        <td className="py-3 pr-4 text-black/60 text-xs">
                          {formatDate(sub.unsubscribed_at)}
                        </td>
                        <td className="py-3 text-right">
                          <button
                            onClick={() => handleDelete(sub)}
                            className="text-xs text-red-600 hover:underline"
                            title="Supprimer définitivement (RGPD art. 17)"
                          >
                            Supprimer
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <p className="text-xs text-black/40 mt-4">
            Rétention : 3 ans sans interaction ou jusqu&apos;à désinscription.
            Les données sont chiffrées au repos (PostgreSQL + backup chiffré).
          </p>
        </div>
      </main>
    </div>
  );
}
