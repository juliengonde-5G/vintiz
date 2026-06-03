'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface AccountingExport {
  id: string;
  export_date: string;
  status: 'pending' | 'exported' | 'failed' | 'manual';
  net_ttc: number;
  total_sales_ttc: number;
  total_refunds_ttc: number;
  transaction_count: number;
  refund_count: number;
  cash_discrepancy: number | null;
  pennylane_exported_at: string | null;
  pennylane_error: string | null;
  fec_filename: string | null;
  email_sent_at: string | null;
  locked_at: string | null;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  exported: { label: 'Pennylane ✓', color: 'bg-green-100 text-green-800' },
  failed: { label: 'Échec Pennylane', color: 'bg-red-100 text-red-800' },
  manual: { label: 'Fichier FEC', color: 'bg-blue-100 text-blue-800' },
  pending: { label: 'En attente', color: 'bg-yellow-100 text-yellow-800' },
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export default function ExportsPage() {
  const [exports, setExports] = useState<AccountingExport[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api.get('/api/accounting/exports?limit=60').then(r => r.json()).then((data: AccountingExport[]) => {
      setExports(data);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const retry = async (id: string) => {
    setRetrying(id);
    try {
      await api.post(`/api/accounting/exports/${id}/retry`, {}).then(r => r.json());
      load();
    } finally {
      setRetrying(null);
    }
  };

  const downloadFec = async (id: string, filename: string) => {
    // Le FEC est protégé (JWT manager) et l'API peut être sur une autre
    // origine (NEXT_PUBLIC_API_URL). Un <a href="/api/..."> ne porte ni le
    // token ni la base → en prod il tape le front Next.js et renvoie une
    // page 404 (le "FEC" téléchargé était en réalité du HTML). On passe par
    // api.get (token + base) puis blob, comme les autres exports.
    try {
      const res = await api.get(`/api/accounting/exports/${id}/fec`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        alert(body.detail || `Téléchargement FEC impossible (HTTP ${res.status})`);
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename || `FEC_${id}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(objectUrl);
    } catch {
      alert('Erreur réseau pendant le téléchargement du FEC');
    }
  };

  return (
    <div className="flex h-screen bg-vz-bg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-display font-semibold text-vz-ink">Exports comptables</h1>
              <p className="text-vz-ink-soft mt-1">Historique des clôtures quotidiennes et statuts Pennylane.</p>
            </div>
            <Button variant="secondary" size="sm" onClick={load}>Actualiser</Button>
          </div>

          {loading ? (
            <p className="text-vz-ink-mute text-center py-12">Chargement…</p>
          ) : exports.length === 0 ? (
            <Card>
              <p className="text-center text-vz-ink-mute py-8">Aucun export disponible. Les exports sont générés automatiquement à chaque clôture de caisse.</p>
            </Card>
          ) : (
            <div className="bg-white rounded-xl border border-vz-line overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vz-line bg-vz-bg-alt">
                    <th className="text-left px-4 py-3 text-vz-ink-soft font-medium">Date</th>
                    <th className="text-right px-4 py-3 text-vz-ink-soft font-medium">CA net TTC</th>
                    <th className="text-right px-4 py-3 text-vz-ink-soft font-medium">Transactions</th>
                    <th className="text-center px-4 py-3 text-vz-ink-soft font-medium">Écart caisse</th>
                    <th className="text-center px-4 py-3 text-vz-ink-soft font-medium">Statut</th>
                    <th className="text-center px-4 py-3 text-vz-ink-soft font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {exports.map(exp => {
                    const st = STATUS_LABELS[exp.status] || STATUS_LABELS.pending;
                    const discColor = exp.cash_discrepancy === null ? '' : Math.abs(exp.cash_discrepancy) > 5 ? 'text-red-600 font-semibold' : 'text-green-600';
                    return (
                      <tr key={exp.id} className="border-b border-vz-line hover:bg-vz-bg-alt/50 transition-colors">
                        <td className="px-4 py-3 font-medium text-vz-ink">
                          <Link href={`/accounting/exports/${exp.id}`} className="hover:text-vz-teal">
                            {formatDate(exp.export_date)}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold text-vz-teal">
                          {exp.net_ttc.toFixed(2)} €
                        </td>
                        <td className="px-4 py-3 text-right text-vz-ink-soft">
                          {exp.transaction_count} ventes
                          {exp.refund_count > 0 && <span className="text-red-500 ml-1">· {exp.refund_count} remb.</span>}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {exp.cash_discrepancy !== null ? (
                            <span className={`font-mono text-xs ${discColor}`}>
                              {exp.cash_discrepancy >= 0 ? '+' : ''}{exp.cash_discrepancy.toFixed(2)} €
                            </span>
                          ) : (
                            <span className="text-vz-ink-mute">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${st.color}`}>
                            {st.label}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-2">
                            {exp.fec_filename && (
                              <button
                                onClick={() => downloadFec(exp.id, exp.fec_filename!)}
                                className="text-xs text-vz-teal hover:underline"
                                title="Télécharger FEC"
                              >
                                FEC
                              </button>
                            )}
                            {exp.status === 'failed' && (
                              <button
                                onClick={() => retry(exp.id)}
                                disabled={retrying === exp.id}
                                className="text-xs text-red-600 hover:underline disabled:opacity-50"
                              >
                                {retrying === exp.id ? '…' : 'Retry'}
                              </button>
                            )}
                            <Link href={`/accounting/exports/${exp.id}`} className="text-xs text-vz-ink-mute hover:text-vz-ink">
                              Détail →
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
