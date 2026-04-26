'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import RefundModal from '@/components/pos/RefundModal';
import { api } from '@/lib/api';

interface Transaction {
  id: string;
  transaction_number: number;
  transaction_type: string;
  total_ttc: number;
  created_at: string;
  item_count: number;
  payment_methods: string[];
}

interface CashDrawer {
  id: string;
  opened_at: string;
  closed_at: string | null;
  opening_amount: number;
  closing_amount: number | null;
  expected_amount: number | null;
  difference: number | null;
  is_open: boolean;
}

type AdminTab = 'all' | 'cb' | 'cash' | 'drawers';

function formatCurrency(v: number): string {
  return v.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

function formatDate(s: string): string {
  const d = new Date(s);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function PaymentBadge({ method }: { method: string }) {
  const cfg: Record<string, { label: string; cls: string }> = {
    card:    { label: 'CB', cls: 'bg-blue-100 text-blue-700' },
    cash:    { label: 'Espèces', cls: 'bg-green-100 text-green-700' },
    cheque:  { label: 'Chèque', cls: 'bg-purple-100 text-purple-700' },
  };
  const c = cfg[method] || { label: method, cls: 'bg-gray-100 text-gray-600' };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${c.cls}`}>
      {c.label}
    </span>
  );
}

function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded-lg ${className}`} />;
}

function TransactionTable({
  transactions,
  loading,
  onRefund,
}: {
  transactions: Transaction[];
  loading: boolean;
  onRefund: (txId: string) => void;
}) {
  if (loading) {
    return (
      <div className="space-y-3 p-4">
        {Array.from({ length: 8 }).map((_, i) => <SkeletonBlock key={i} className="h-12 w-full" />)}
      </div>
    );
  }
  if (transactions.length === 0) {
    return <p className="text-gray-400 text-center py-12">Aucune transaction</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="py-3 px-4 font-semibold text-gray-600">#</th>
            <th className="py-3 px-4 font-semibold text-gray-600">Date</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Total TTC</th>
            <th className="py-3 px-4 font-semibold text-gray-600">Paiements</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Articles</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => {
            const isSale = tx.transaction_type !== 'refund';
            return (
              <tr key={tx.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="py-3 px-4 font-mono text-gray-700">
                  #{tx.transaction_number}
                  {!isSale && (
                    <span className="ml-2 px-2 py-0.5 rounded-full text-xs bg-orange-100 text-orange-700">
                      retour
                    </span>
                  )}
                </td>
                <td className="py-3 px-4 text-gray-600">{tx.created_at ? formatDate(tx.created_at) : '-'}</td>
                <td className="py-3 px-4 text-right font-bold text-teal">{formatCurrency(tx.total_ttc)}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1 flex-wrap">
                    {(tx.payment_methods || []).map((m, i) => <PaymentBadge key={i} method={m} />)}
                  </div>
                </td>
                <td className="py-3 px-4 text-right text-gray-600">{tx.item_count}</td>
                <td className="py-3 px-4 text-right">
                  {isSale ? (
                    <button
                      type="button"
                      onClick={() => onRefund(tx.id)}
                      className="px-3 py-1 text-xs rounded bg-orange-50 text-orange-700 hover:bg-orange-100"
                    >
                      Rembourser
                    </button>
                  ) : (
                    <span className="text-xs text-gray-300">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DrawerTable({ drawers, loading }: { drawers: CashDrawer[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="space-y-3 p-4">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonBlock key={i} className="h-12 w-full" />)}
      </div>
    );
  }
  if (drawers.length === 0) {
    return <p className="text-gray-400 text-center py-12">Aucune session de caisse</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="py-3 px-4 font-semibold text-gray-600">Ouverture</th>
            <th className="py-3 px-4 font-semibold text-gray-600">Clôture</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Fond ouvert.</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Attendu</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Comptage réel</th>
            <th className="py-3 px-4 font-semibold text-gray-600 text-right">Écart</th>
            <th className="py-3 px-4 font-semibold text-gray-600">Statut</th>
          </tr>
        </thead>
        <tbody>
          {drawers.map((d) => (
            <tr key={d.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
              <td className="py-3 px-4 text-gray-600">{d.opened_at ? formatDate(d.opened_at) : '-'}</td>
              <td className="py-3 px-4 text-gray-600">{d.closed_at ? formatDate(d.closed_at) : '-'}</td>
              <td className="py-3 px-4 text-right">{formatCurrency(d.opening_amount)}</td>
              <td className="py-3 px-4 text-right">{d.expected_amount != null ? formatCurrency(d.expected_amount) : '-'}</td>
              <td className="py-3 px-4 text-right">{d.closing_amount != null ? formatCurrency(d.closing_amount) : '-'}</td>
              <td className="py-3 px-4 text-right">
                {d.difference != null ? (
                  <span className={`font-bold ${d.difference === 0 ? 'text-green-600' : d.difference > 0 ? 'text-blue-600' : 'text-red-600'}`}>
                    {d.difference >= 0 ? '+' : ''}{formatCurrency(d.difference)}
                  </span>
                ) : '-'}
              </td>
              <td className="py-3 px-4">
                {d.is_open ? (
                  <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">Ouverte</span>
                ) : (
                  <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Clôturée</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState<AdminTab>('all');
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [cbTransactions, setCbTransactions] = useState<Transaction[]>([]);
  const [cashTransactions, setCashTransactions] = useState<Transaction[]>([]);
  const [drawers, setDrawers] = useState<CashDrawer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [refundTxId, setRefundTxId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const loadTransactions = useCallback(async (method?: string): Promise<Transaction[]> => {
    const url = method ? `/api/pos/transactions?limit=200&method=${method}` : '/api/pos/transactions?limit=200';
    const res = await api.get(url);
    if (!res.ok) throw new Error('Erreur chargement transactions');
    return res.json();
  }, []);

  const loadDrawers = useCallback(async (): Promise<CashDrawer[]> => {
    const res = await api.get('/api/admin/cash-drawers?limit=50');
    if (!res.ok) throw new Error('Erreur chargement caisses');
    return res.json();
  }, []);

  useEffect(() => {
    setError('');
    setLoading(true);
    const load = async () => {
      try {
        if (tab === 'all') {
          setTransactions(await loadTransactions());
        } else if (tab === 'cb') {
          setCbTransactions(await loadTransactions('card'));
        } else if (tab === 'cash') {
          setCashTransactions(await loadTransactions('cash'));
        } else if (tab === 'drawers') {
          setDrawers(await loadDrawers());
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erreur inconnue');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [tab, loadTransactions, loadDrawers, reloadKey]);

  const tabs: { key: AdminTab; label: string; icon: string }[] = [
    { key: 'all', label: 'Toutes les transactions', icon: '📋' },
    { key: 'cb', label: 'CB / SumUp', icon: '💳' },
    { key: 'cash', label: 'Espèces', icon: '💶' },
    { key: 'drawers', label: 'Sessions caisse', icon: '🗄️' },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">Administration</h1>
          <p className="text-gray-500 mt-1">Backlog des transactions et suivi de caisse</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg min-h-[44px] whitespace-nowrap transition-colors text-sm font-medium ${
                tab === t.key
                  ? 'bg-teal text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        {tab === 'all' && (
          <Card title={`Backlog — ${transactions.length} transaction(s)`}>
            <TransactionTable transactions={transactions} loading={loading} onRefund={setRefundTxId} />
          </Card>
        )}

        {tab === 'cb' && (
          <Card title={`Paiements CB / SumUp — ${cbTransactions.length} transaction(s)`}>
            <div className="mb-4 px-4">
              <p className="text-sm text-gray-500">
                Transactions réglées par carte bancaire (SumUp terminal ou simulation).
              </p>
            </div>
            <TransactionTable transactions={cbTransactions} loading={loading} onRefund={setRefundTxId} />
          </Card>
        )}

        {tab === 'cash' && (
          <Card title={`Transactions en espèces — ${cashTransactions.length} transaction(s)`}>
            <div className="mb-4 px-4">
              <p className="text-sm text-gray-500">
                Transactions réglées en espèces. Le total doit correspondre au fond de caisse en fin de journée.
              </p>
              {cashTransactions.length > 0 && (
                <div className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
                  <span className="text-sm font-semibold text-green-800">
                    Total espèces:{' '}
                    {formatCurrency(cashTransactions.reduce((s, tx) => s + tx.total_ttc, 0))}
                  </span>
                </div>
              )}
            </div>
            <TransactionTable transactions={cashTransactions} loading={loading} onRefund={setRefundTxId} />
          </Card>
        )}

        {tab === 'drawers' && (
          <Card title="Sessions tiroir-caisse">
            <div className="mb-4 px-4">
              <p className="text-sm text-gray-500">
                Historique des ouvertures et clôtures de caisse. Un écart positif = excédent, négatif = déficit.
              </p>
            </div>
            <DrawerTable drawers={drawers} loading={loading} />
          </Card>
        )}
      </main>

      <RefundModal
        open={refundTxId !== null}
        transactionId={refundTxId}
        onClose={() => setRefundTxId(null)}
        onCompleted={() => setReloadKey(k => k + 1)}
      />
    </div>
  );
}
