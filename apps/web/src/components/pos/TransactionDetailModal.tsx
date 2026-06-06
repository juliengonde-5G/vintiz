'use client';

import React, { useCallback, useEffect, useState } from 'react';

import LinkClientControl from '@/components/pos/LinkClientControl';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

interface TxItem {
  id: string;
  product_id: string | null;
  name: string;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  line_total: number;
}

interface TxPayment {
  id: string;
  method: string;
  amount: number;
}

interface TxClient {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
}

interface TxDetail {
  id: string;
  transaction_number: number;
  type: string;
  total_ttc: number;
  total_ht: number;
  tax_amount: number;
  created_at: string | null;
  client: TxClient | null;
  items: TxItem[];
  payments: TxPayment[];
}

const METHOD_LABELS: Record<string, string> = {
  cash: 'Espèces',
  card: 'CB',
  cheque: 'Chèque',
  cheque_cdc: 'Chèque CDC',
  transfer: 'Virement',
  avoir: 'Avoir',
  voucher: 'Bon cadeau',
};

function fmtDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

function clientName(c: { first_name: string | null; last_name: string | null }): string {
  return [c.first_name, c.last_name].filter(Boolean).join(' ') || 'Cliente';
}

/**
 * Détail complet d'une transaction (articles, paiements, totaux) + rattachement
 * d'une cliente a posteriori. Réutilisé par la fiche client (vue achat) et la
 * page admin Transactions & Caisse.
 */
export default function TransactionDetailModal({
  transactionId,
  onClose,
  onChanged,
  allowLink = true,
}: {
  transactionId: string | null;
  onClose: () => void;
  onChanged?: () => void;
  allowLink?: boolean;
}) {
  const [tx, setTx] = useState<TxDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!transactionId) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/pos/transactions/${transactionId}`);
      if (!res.ok) throw new Error('Transaction introuvable');
      setTx(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [transactionId]);

  useEffect(() => {
    if (transactionId) load();
    else setTx(null);
  }, [transactionId, load]);

  if (!transactionId) return null;

  return (
    <Modal open onClose={onClose} title={tx ? `Achat #${tx.transaction_number}` : 'Achat'}>
      {loading && <p className="text-sm text-gray-500">Chargement…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {tx && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="text-gray-600">{fmtDate(tx.created_at)}</span>
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                tx.type === 'refund' ? 'bg-orange-100 text-orange-700' : 'bg-vz-teal-soft text-vz-teal'
              }`}
            >
              {tx.type === 'refund' ? 'Retour' : 'Vente'}
            </span>
          </div>

          {/* Cliente */}
          <div className="rounded-lg border border-vz-line p-3 space-y-2">
            <p className="text-xs uppercase tracking-wider text-gray-400">Cliente</p>
            {tx.client ? (
              <p className="text-sm font-medium text-black">
                {clientName(tx.client)}
                {tx.client.email && (
                  <span className="ml-2 text-xs text-gray-500">{tx.client.email}</span>
                )}
              </p>
            ) : (
              <p className="text-sm text-gray-500">Aucune cliente rattachée</p>
            )}
            {allowLink && (
              <LinkClientControl
                transactionId={tx.id}
                hasClient={!!tx.client}
                onChanged={(detail) => {
                  setTx(detail as TxDetail);
                  onChanged?.();
                }}
              />
            )}
          </div>

          {/* Articles */}
          <div>
            <p className="text-xs uppercase tracking-wider text-gray-400 mb-1">
              Articles ({tx.items.length})
            </p>
            <div className="overflow-x-auto rounded-lg border border-vz-line">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500">
                  <tr>
                    <th className="text-left p-2">Article</th>
                    <th className="text-right p-2">Qté</th>
                    <th className="text-right p-2">PU</th>
                    <th className="text-right p-2">Remise</th>
                    <th className="text-right p-2">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {tx.items.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-3 text-center text-gray-400">
                        Aucun article
                      </td>
                    </tr>
                  ) : (
                    tx.items.map((it) => (
                      <tr key={it.id} className="border-t border-gray-100">
                        <td className="p-2">{it.name}</td>
                        <td className="p-2 text-right">{it.quantity}</td>
                        <td className="p-2 text-right">{formatCurrency(it.unit_price)}</td>
                        <td className="p-2 text-right text-gray-500">
                          {it.discount_percent ? `-${it.discount_percent}%` : '—'}
                        </td>
                        <td className="p-2 text-right font-medium">{formatCurrency(it.line_total)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Paiements + totaux */}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="text-sm">
              <p className="text-xs uppercase tracking-wider text-gray-400 mb-1">Paiements</p>
              <div className="flex flex-wrap gap-1.5">
                {tx.payments.map((p) => (
                  <span
                    key={p.id}
                    className="inline-block px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-700"
                  >
                    {METHOD_LABELS[p.method] || p.method} · {formatCurrency(p.amount)}
                  </span>
                ))}
              </div>
            </div>
            <div className="text-right text-sm">
              <p className="text-gray-500">
                HT {formatCurrency(tx.total_ht)} · TVA {formatCurrency(tx.tax_amount)}
              </p>
              <p className="text-lg font-bold text-vz-teal">{formatCurrency(tx.total_ttc)}</p>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
