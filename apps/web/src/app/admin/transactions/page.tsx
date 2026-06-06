'use client';

import React, { Suspense, useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Modal from '@/components/ui/Modal';
import CaissePanel from '@/components/pos/CaissePanel';
import LinkClientControl from '@/components/pos/LinkClientControl';
import RefundModal from '@/components/pos/RefundModal';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';
import { printTransactionTicket } from '@/lib/print-ticket';

interface CardPayment {
  amount: number;
  sumup_transaction_id: string | null;
  sumup_transaction_code: string | null;
  sumup_auth_code: string | null;
  sumup_card_brand: string | null;
  sumup_card_last4: string | null;
  sumup_environment: string | null;
}

interface AdminTransaction {
  id: string;
  transaction_number: number;
  type: 'sale' | 'refund' | 'void';
  is_invoice: boolean;
  invoice_number: number | null;
  total_ttc: number;
  total_ht: number;
  total_tva: number;
  methods: string[];
  card_payments: CardPayment[];
  cashier_id: string | null;
  client_id: string | null;
  client_company_name: string | null;
  created_at: string | null;
}

interface FailedCbAttempt {
  id: string;
  amount: number;
  status: 'pending' | 'succeeded' | 'failed' | 'cancelled';
  transaction_id: string | null;
  sumup_checkout_id: string | null;
  sumup_transaction_id: string | null;
  sumup_card_brand: string | null;
  sumup_card_last4: string | null;
  error_detail: string | null;
  cancelled_reason: string | null;
  created_at: string | null;
}

interface Filters {
  from: string;
  to: string;
  method: string;
  type: string;
  is_invoice: 'all' | 'invoice' | 'ticket';
  min_amount: string;
  max_amount: string;
}

const DEFAULT_FILTERS: Filters = {
  from: '',
  to: '',
  method: '',
  type: '',
  is_invoice: 'all',
  min_amount: '',
  max_amount: '',
};

const METHOD_LABEL: Record<string, string> = {
  cash: 'Espèces',
  card: 'CB',
  cheque: 'Chèque',
  cheque_cdc: 'Chèque CDC',
  avoir: 'Avoir',
  transfer: 'Virement',
};

function formatDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

function MethodBadge({ method }: { method: string }) {
  const label = METHOD_LABEL[method] || method;
  const cls =
    method === 'cash'
      ? 'bg-vz-teal-soft text-vz-teal-deep'
      : method === 'card'
        ? 'bg-blue-100 text-blue-700'
        : method === 'cheque'
          ? 'bg-purple-100 text-purple-700'
          : method === 'avoir'
            ? 'bg-vz-accent-soft text-vz-ink'
            : 'bg-vz-bg-alt text-vz-ink-soft';
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {label}
    </span>
  );
}

export default function AdminTransactionsPage() {
  return (
    <Suspense fallback={null}>
      <AdminTransactionsInner />
    </Suspense>
  );
}

function AdminTransactionsInner() {
  const searchParams = useSearchParams();
  const initialView = (() => {
    const v = searchParams.get('view');
    return v === 'caisse' || v === 'failed_cb' ? v : 'transactions';
  })();
  const [view, setView] = useState<'transactions' | 'failed_cb' | 'caisse'>(initialView);
  const [rows, setRows] = useState<AdminTransaction[]>([]);
  const [attempts, setAttempts] = useState<FailedCbAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [detail, setDetail] = useState<AdminTransaction | null>(null);
  const [refundTxId, setRefundTxId] = useState<string | null>(null);
  const [reissueMsg, setReissueMsg] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (filters.from) params.set('from', filters.from);
      if (filters.to) params.set('to', filters.to);
      if (filters.method) params.set('method', filters.method);
      if (filters.type) params.set('type', filters.type);
      if (filters.is_invoice !== 'all') {
        params.set('is_invoice', filters.is_invoice === 'invoice' ? 'true' : 'false');
      }
      if (filters.min_amount) params.set('min_amount', filters.min_amount);
      if (filters.max_amount) params.set('max_amount', filters.max_amount);
      params.set('limit', '200');

      const res = await api.get(`/api/admin/transactions?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setRows(data.transactions || []);
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [filters]);

  // Export CSV — réutilise exactement les filtres de l'historique affiché.
  // Download authentifié via blob (token + base API), comme les autres
  // exports : un <a href> relatif raterait l'auth et la base.
  const [exporting, setExporting] = useState(false);
  const exportCsv = useCallback(async (detailed: boolean) => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (filters.from) params.set('from', filters.from);
      if (filters.to) params.set('to', filters.to);
      if (filters.method) params.set('method', filters.method);
      if (filters.type) params.set('type', filters.type);
      if (filters.is_invoice !== 'all') {
        params.set('is_invoice', filters.is_invoice === 'invoice' ? 'true' : 'false');
      }
      if (filters.min_amount) params.set('min_amount', filters.min_amount);
      if (filters.max_amount) params.set('max_amount', filters.max_amount);
      const path = detailed ? 'export-detailed.csv' : 'export.csv';
      const res = await api.get(`/api/admin/transactions/${path}?${params.toString()}`);
      if (!res.ok) {
        setError('Export CSV impossible.');
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = detailed ? 'vintiz_transactions_detail.csv' : 'vintiz_transactions.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch {
      setError('Erreur réseau pendant l\'export.');
    } finally {
      setExporting(false);
    }
  }, [filters]);

  // Failed CB attempts — the "CB échouées" view folds the former
  // /admin/payment-attempts debug surface into this page.
  const loadAttempts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      params.set('status', 'failed');
      params.set('method', 'card');
      if (filters.from) params.set('from', filters.from);
      if (filters.to) params.set('to', filters.to);
      params.set('limit', '200');
      const res = await api.get(`/api/admin/payment-attempts?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setAttempts(data.attempts || []);
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [filters]);

  useEffect(() => {
    if (view === 'transactions') load();
    else loadAttempts();
  }, [view, load, loadAttempts]);

  const topErrors = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of attempts) {
      const key = a.error_detail || a.cancelled_reason || '(sans détail)';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
  }, [attempts]);

  const totalSales = rows
    .filter((r) => r.type === 'sale')
    .reduce((sum, r) => sum + r.total_ttc, 0);
  const totalRefunds = rows
    .filter((r) => r.type === 'refund')
    .reduce((sum, r) => sum + r.total_ttc, 0);

  const sendInvoice = async (tx: AdminTransaction): Promise<void> => {
    const to = window.prompt(
      'Adresse email du destinataire (laisser vide pour utiliser le client lié) :',
      '',
    );
    if (to === null) return; // cancelled
    try {
      const res = await api.post(`/api/pos/transactions/${tx.id}/send-invoice`, {
        to: to.trim() || undefined,
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        alert(data.message || 'Facture envoyée.');
      } else {
        alert(`Erreur : ${data.detail || res.statusText}`);
      }
    } catch {
      alert('Erreur réseau.');
    }
  };

  const downloadInvoice = async (tx: AdminTransaction): Promise<void> => {
    try {
      const res = await api.get(`/api/pos/transactions/${tx.id}/invoice.pdf`);
      if (!res.ok) {
        alert('Erreur : impossible de télécharger la facture.');
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FACT-${new Date(tx.created_at || '').getFullYear()}-${String(
        tx.invoice_number || tx.transaction_number,
      ).padStart(6, '0')}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      alert('Erreur réseau.');
    }
  };

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 py-6 pt-16 md:pt-6 md:px-6 lg:p-8">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-semibold text-vz-ink">
              Transactions &amp; Caisse
            </h1>
            <p className="text-sm text-vz-ink-mute">
              {view === 'transactions'
                ? 'Toutes les ventes, refunds et factures — détail CB (TPE Solo) inclus.'
                : view === 'failed_cb'
                  ? 'Tentatives CB refusées par le TPE Solo — regroupées par cause.'
                  : 'Suivi de caisse : rapports Z, sessions tiroir et régularisation.'}
            </p>
          </div>
          {view === 'transactions' && (
            <div className="flex flex-col items-end gap-2">
              <div className="flex gap-3">
                <KpiTile label="Ventes" value={formatCurrency(totalSales)} tone="teal" />
                <KpiTile
                  label="Remboursements"
                  value={formatCurrency(totalRefunds)}
                  tone="accent"
                />
                <KpiTile label="Lignes" value={String(rows.length)} tone="neutral" />
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={exporting}
                  onClick={() => void exportCsv(false)}
                >
                  {exporting ? 'Export…' : 'Export CSV'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={exporting}
                  onClick={() => void exportCsv(true)}
                  title="Une ligne par article vendu"
                >
                  CSV détaillé
                </Button>
              </div>
            </div>
          )}
        </header>

        {/* View switch — folds the old « Tentatives CB » page into this one. */}
        <div className="mb-4 inline-flex rounded-xl border border-vz-line bg-vz-surface p-1">
          {([
            ['transactions', 'Transactions'],
            ['failed_cb', 'CB échouées'],
            ['caisse', 'Caisse'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setView(key)}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
                view === key
                  ? 'bg-vz-teal text-white'
                  : 'text-vz-ink-soft hover:bg-vz-bg-alt'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {view === 'transactions' && (
          <Card>
            <FiltersBar
              value={filters}
              onChange={setFilters}
              onReset={() => setFilters(DEFAULT_FILTERS)}
            />
          </Card>
        )}

        {view === 'failed_cb' && topErrors.length > 0 && (
          <Card>
            <h2 className="mb-3 font-display text-lg font-semibold text-vz-ink">
              Top causes d&apos;échec
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

        {view === 'caisse' && <CaissePanel />}

        {view !== 'caisse' && (
        <Card className="mt-4">
          {error && (
            <p className="rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
              {error}
            </p>
          )}
          {loading ? (
            <p className="py-12 text-center text-vz-ink-mute">Chargement…</p>
          ) : view === 'failed_cb' ? (
            attempts.length === 0 ? (
              <p className="py-12 text-center text-vz-ink-mute">
                Aucune tentative CB refusée.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-vz-line text-xs uppercase tracking-wide text-vz-ink-mute">
                    <tr>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2 text-right">Montant</th>
                      <th className="px-3 py-2">Carte</th>
                      <th className="px-3 py-2">Réf. SumUp</th>
                      <th className="px-3 py-2">Cause</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attempts.map((a) => (
                      <tr
                        key={a.id}
                        className="border-b border-vz-line last:border-b-0"
                      >
                        <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                          {formatDate(a.created_at)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono tabular-nums">
                          {formatCurrency(a.amount)}
                        </td>
                        <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                          {a.sumup_card_brand || a.sumup_card_last4
                            ? `${a.sumup_card_brand || 'CB'} ••${a.sumup_card_last4 || '????'}`
                            : '—'}
                        </td>
                        <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                          {a.sumup_transaction_id || a.sumup_checkout_id || '—'}
                        </td>
                        <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                          {a.error_detail || a.cancelled_reason || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : rows.length === 0 ? (
            <p className="py-12 text-center text-vz-ink-mute">
              Aucune transaction ne correspond aux filtres.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-vz-line text-xs uppercase tracking-wide text-vz-ink-mute">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Ticket</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2">Client</th>
                    <th className="px-3 py-2">Méthodes</th>
                    <th className="px-3 py-2">CB</th>
                    <th className="px-3 py-2 text-right">Total TTC</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((tx) => (
                    <tr
                      key={tx.id}
                      onClick={() => setDetail(tx)}
                      className="cursor-pointer border-b border-vz-line last:border-b-0 hover:bg-vz-bg-alt"
                    >
                      <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                        {formatDate(tx.created_at)}
                      </td>
                      <td className="px-3 py-3 font-mono">
                        {tx.is_invoice && tx.invoice_number !== null
                          ? `FACT-${String(tx.invoice_number).padStart(6, '0')}`
                          : `#${tx.transaction_number}`}
                      </td>
                      <td className="px-3 py-3">
                        <TypeBadge type={tx.type} isInvoice={tx.is_invoice} />
                      </td>
                      <td className="px-3 py-3 text-vz-ink-soft">
                        {tx.client_company_name || (tx.client_id ? 'Client' : '—')}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1">
                          {tx.methods.length === 0
                            ? '—'
                            : tx.methods.map((m, i) => (
                                <MethodBadge key={i} method={m} />
                              ))}
                        </div>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                        {tx.card_payments.length > 0
                          ? tx.card_payments
                              .map((c) =>
                                c.sumup_card_brand || c.sumup_card_last4
                                  ? `${c.sumup_card_brand || 'CB'} ••${c.sumup_card_last4 || '????'}`
                                  : '✓',
                              )
                              .join(', ')
                          : '—'}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {formatCurrency(tx.total_ttc)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        {tx.is_invoice && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              void downloadInvoice(tx);
                            }}
                            className="text-xs text-vz-teal underline hover:text-vz-teal-deep"
                          >
                            PDF facture
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        )}
      </main>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={
          detail
            ? detail.is_invoice && detail.invoice_number !== null
              ? `Facture FACT-${String(detail.invoice_number).padStart(6, '0')}`
              : `Ticket #${detail.transaction_number}`
            : ''
        }
      >
        {detail && (
          <div className="space-y-3">
            <DetailRow label="Date" value={formatDate(detail.created_at)} />
            <DetailRow
              label="Type"
              value={
                detail.is_invoice
                  ? 'Facture B2B'
                  : detail.type === 'refund'
                    ? 'Remboursement'
                    : 'Vente'
              }
            />
            {detail.client_company_name && (
              <DetailRow label="Société" value={detail.client_company_name} />
            )}
            <DetailRow
              label="Méthodes"
              value={detail.methods.map((m) => METHOD_LABEL[m] || m).join(', ')}
            />
            {detail.card_payments.length > 0 && (
              <div className="rounded-lg border border-vz-line bg-vz-bg-alt/60 p-3">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
                  Détail CB — TPE Solo
                </p>
                {detail.card_payments.map((c, i) => (
                  <div key={i} className="space-y-1 text-sm">
                    <DetailRow
                      label="Carte"
                      value={
                        c.sumup_card_brand || c.sumup_card_last4
                          ? `${c.sumup_card_brand || 'CB'} •••• ${c.sumup_card_last4 || '????'}`
                          : '—'
                      }
                    />
                    <DetailRow
                      label="Réf. transaction"
                      value={c.sumup_transaction_code || c.sumup_transaction_id || '—'}
                    />
                    {c.sumup_auth_code && (
                      <DetailRow label="Autorisation" value={c.sumup_auth_code} />
                    )}
                  </div>
                ))}
              </div>
            )}
            <DetailRow label="Total HT" value={formatCurrency(detail.total_ht)} />
            <DetailRow label="TVA" value={formatCurrency(detail.total_tva)} />
            <DetailRow
              label="Total TTC"
              value={formatCurrency(detail.total_ttc)}
              emphasis
            />
            <DetailRow
              label="Cliente"
              value={
                detail.client_company_name
                  ? detail.client_company_name
                  : detail.client_id
                    ? 'Rattachée'
                    : 'Aucune'
              }
            />
            <div className="border-t border-vz-line pt-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
                Rattachement cliente
              </p>
              <LinkClientControl
                transactionId={detail.id}
                hasClient={!!detail.client_id}
                onChanged={(d) => {
                  const nd = d as { client?: { id: string } | null };
                  setDetail({ ...detail, client_id: nd.client?.id ?? null });
                  void load();
                }}
              />
            </div>
            <div className="flex flex-wrap gap-2 border-t border-vz-line pt-3">
              {detail.type === 'sale' && (
                <Button variant="outline" onClick={() => setRefundTxId(detail.id)}>
                  Rembourser
                </Button>
              )}
              <Button
                variant="outline"
                onClick={async () => {
                  setReissueMsg('');
                  const r = await printTransactionTicket(detail.id, { kickDrawer: false });
                  setReissueMsg(r.message);
                }}
              >
                Réimprimer le ticket
              </Button>
              <Button
                variant="outline"
                onClick={async () => {
                  setReissueMsg('');
                  const res = await api.post(`/api/pos/transactions/${detail.id}/resend`, {
                    channel: 'email',
                  });
                  setReissueMsg(
                    res.ok ? 'Ticket renvoyé par email à la cliente.' : 'Renvoi email impossible.',
                  );
                }}
              >
                Renvoyer (email)
              </Button>
            </div>
            {reissueMsg && <p className="text-xs text-vz-ink-soft">{reissueMsg}</p>}
            {detail.is_invoice && (
              <div className="flex flex-wrap gap-2 pt-3">
                <Button onClick={() => void downloadInvoice(detail)}>
                  Télécharger facture PDF
                </Button>
                <Button variant="outline" onClick={() => void sendInvoice(detail)}>
                  Envoyer par email
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>

      <RefundModal
        open={refundTxId !== null}
        transactionId={refundTxId}
        onClose={() => setRefundTxId(null)}
        onCompleted={() => {
          setRefundTxId(null);
          setDetail(null);
          void load();
        }}
      />
    </div>
  );
}

function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'teal' | 'accent' | 'neutral';
}) {
  const cls =
    tone === 'teal'
      ? 'bg-vz-teal-soft text-vz-teal-deep'
      : tone === 'accent'
        ? 'bg-vz-accent-soft text-vz-ink'
        : 'bg-vz-bg-alt text-vz-ink-soft';
  return (
    <div className={`rounded-xl px-4 py-2 ${cls}`}>
      <div className="text-xs font-medium uppercase tracking-wide opacity-80">
        {label}
      </div>
      <div className="font-mono text-lg font-bold tabular-nums">{value}</div>
    </div>
  );
}

function TypeBadge({ type, isInvoice }: { type: string; isInvoice: boolean }) {
  const label = isInvoice ? 'Facture' : type === 'refund' ? 'Refund' : 'Vente';
  const cls = isInvoice
    ? 'bg-vz-gold/10 text-vz-gold'
    : type === 'refund'
      ? 'bg-vz-accent-soft text-vz-ink'
      : 'bg-vz-teal-soft text-vz-teal-deep';
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {label}
    </span>
  );
}

function DetailRow({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-vz-line py-2 last:border-b-0">
      <span className="text-sm font-medium text-vz-ink-mute">{label}</span>
      <span
        className={
          emphasis
            ? 'font-mono text-lg font-bold tabular-nums text-vz-ink'
            : 'font-mono text-sm tabular-nums text-vz-ink'
        }
      >
        {value}
      </span>
    </div>
  );
}

function FiltersBar({
  value,
  onChange,
  onReset,
}: {
  value: Filters;
  onChange: (f: Filters) => void;
  onReset: () => void;
}) {
  const set = (patch: Partial<Filters>): void => onChange({ ...value, ...patch });
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
      <FilterField label="Du">
        <input
          type="date"
          value={value.from}
          onChange={(e) => set({ from: e.target.value })}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        />
      </FilterField>
      <FilterField label="Au">
        <input
          type="date"
          value={value.to}
          onChange={(e) => set({ to: e.target.value })}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        />
      </FilterField>
      <FilterField label="Méthode">
        <select
          value={value.method}
          onChange={(e) => set({ method: e.target.value })}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        >
          <option value="">Toutes</option>
          <option value="cash">Espèces</option>
          <option value="card">CB</option>
          <option value="cheque">Chèque</option>
          <option value="avoir">Avoir</option>
        </select>
      </FilterField>
      <FilterField label="Type">
        <select
          value={value.type}
          onChange={(e) => set({ type: e.target.value })}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        >
          <option value="">Tous</option>
          <option value="sale">Vente</option>
          <option value="refund">Refund</option>
        </select>
      </FilterField>
      <FilterField label="Document">
        <select
          value={value.is_invoice}
          onChange={(e) =>
            set({ is_invoice: e.target.value as Filters['is_invoice'] })
          }
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        >
          <option value="all">Tous</option>
          <option value="ticket">Tickets</option>
          <option value="invoice">Factures</option>
        </select>
      </FilterField>
      <FilterField label="Min €">
        <input
          type="number"
          step="0.01"
          value={value.min_amount}
          onChange={(e) => set({ min_amount: e.target.value })}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        />
      </FilterField>
      <FilterField label="Max €">
        <input
          type="number"
          step="0.01"
          value={value.max_amount}
          onChange={(e) => set({ max_amount: e.target.value })}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-2 py-1.5 text-sm"
        />
      </FilterField>
      <div className="col-span-2 flex items-end justify-end md:col-span-4 lg:col-span-7">
        <button
          type="button"
          onClick={onReset}
          className="text-xs text-vz-ink-mute underline hover:text-vz-ink"
        >
          Réinitialiser
        </button>
      </div>
    </div>
  );
}

function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
        {label}
      </span>
      {children}
    </label>
  );
}
