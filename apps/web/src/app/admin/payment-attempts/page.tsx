'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';

import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

interface PaymentAttempt {
  id: string;
  method: 'cash' | 'card' | 'cheque' | 'avoir' | 'transfer';
  amount: number;
  status: 'pending' | 'succeeded' | 'failed' | 'cancelled';
  transaction_id: string | null;
  drawer_id: string | null;
  cashier_id: string | null;
  sumup_checkout_id: string | null;
  error_detail: string | null;
  cancelled_reason: string | null;
  created_at: string | null;
  updated_at: string | null;
}

const STATUS_LABEL: Record<PaymentAttempt['status'], string> = {
  pending: 'En attente',
  succeeded: 'Réussi',
  failed: 'Échec',
  cancelled: 'Annulé',
};

const STATUS_PALETTE: Record<PaymentAttempt['status'], string> = {
  pending: 'bg-vz-bg-alt text-vz-ink-soft',
  succeeded: 'bg-vz-teal-soft text-vz-teal-deep',
  failed: 'bg-vz-accent-soft text-vz-ink',
  cancelled: 'bg-vz-bg-alt text-vz-ink-mute',
};

function formatDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

export default function AdminPaymentAttemptsPage() {
  const [rows, setRows] = useState<PaymentAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] =
    useState<PaymentAttempt['status'] | 'all'>('failed');
  const [methodFilter, setMethodFilter] =
    useState<PaymentAttempt['method'] | 'all'>('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (methodFilter !== 'all') params.set('method', methodFilter);
      params.set('limit', '200');
      const res = await api.get(`/api/admin/payment-attempts?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setRows(data.attempts || []);
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [statusFilter, methodFilter]);

  useEffect(() => {
    load();
  }, [load]);

  /** Aggregate by ``error_detail`` to surface the top-N CB failures. */
  const topErrors = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) {
      if (r.status !== 'failed') continue;
      const key = r.error_detail || '(sans détail)';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
  }, [rows]);

  return (
    <div className="flex min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="flex-1 p-6 lg:p-8">
        <header className="mb-6">
          <h1 className="font-display text-3xl font-semibold text-vz-ink">
            Tentatives de paiement
          </h1>
          <p className="text-sm text-vz-ink-mute">
            Toutes les tentatives — succès, échecs et abandons. Les CB
            refusées sont regroupées par <code>error_detail</code> pour
            identifier rapidement les causes (TPE injoignable, carte
            refusée…).
          </p>
        </header>

        <Card>
          <div className="flex flex-wrap items-end gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
                Statut
              </span>
              <select
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(e.target.value as typeof statusFilter)
                }
                className="rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
              >
                <option value="all">Tous</option>
                <option value="failed">Échec</option>
                <option value="cancelled">Annulé</option>
                <option value="pending">En attente</option>
                <option value="succeeded">Réussi</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
                Méthode
              </span>
              <select
                value={methodFilter}
                onChange={(e) =>
                  setMethodFilter(e.target.value as typeof methodFilter)
                }
                className="rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
              >
                <option value="all">Toutes</option>
                <option value="card">CB</option>
                <option value="cash">Espèces</option>
                <option value="cheque">Chèque</option>
                <option value="avoir">Avoir</option>
              </select>
            </label>
          </div>
        </Card>

        {topErrors.length > 0 && (
          <Card className="mt-4">
            <h2 className="mb-3 font-display text-lg font-semibold text-vz-ink">
              Top causes d'échec
            </h2>
            <ul className="space-y-1.5">
              {topErrors.map(([msg, count], i) => (
                <li
                  key={i}
                  className="flex items-center justify-between border-b border-vz-line pb-1.5 text-sm last:border-b-0 last:pb-0"
                >
                  <span className="truncate pr-3 font-mono text-xs text-vz-ink">
                    {msg}
                  </span>
                  <span className="rounded-full bg-vz-accent-soft px-2 py-0.5 font-mono text-xs font-bold text-vz-ink">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card className="mt-4">
          {error && (
            <p className="rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
              {error}
            </p>
          )}
          {loading ? (
            <p className="py-12 text-center text-vz-ink-mute">Chargement…</p>
          ) : rows.length === 0 ? (
            <p className="py-12 text-center text-vz-ink-mute">
              Aucune tentative ne correspond aux filtres.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-vz-line text-xs uppercase tracking-wide text-vz-ink-mute">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Méthode</th>
                    <th className="px-3 py-2 text-right">Montant</th>
                    <th className="px-3 py-2">Statut</th>
                    <th className="px-3 py-2">Détail</th>
                    <th className="px-3 py-2">Vente</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr
                      key={a.id}
                      className="border-b border-vz-line last:border-b-0"
                    >
                      <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                        {formatDate(a.created_at)}
                      </td>
                      <td className="px-3 py-3">{a.method.toUpperCase()}</td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {formatCurrency(a.amount)}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_PALETTE[a.status]}`}
                        >
                          {STATUS_LABEL[a.status]}
                        </span>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                        {a.error_detail || a.cancelled_reason || '—'}
                      </td>
                      <td className="px-3 py-3">
                        {a.transaction_id ? (
                          <a
                            href={`/admin?tx=${a.transaction_id}`}
                            className="text-xs text-vz-teal underline hover:text-vz-teal-deep"
                          >
                            Voir
                          </a>
                        ) : (
                          <span className="text-xs text-vz-ink-mute">
                            (abandonnée)
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
