'use client';

import React, { useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface ReconciliationLine {
  vintiz_payment_id: string;
  vintiz_transaction_number: number;
  vintiz_amount: number;
  sumup_transaction_id: string | null;
  sumup_transaction_code: string | null;
  sumup_amount: number | null;
  status: 'matched' | 'vintiz_only' | 'sumup_only' | 'amount_mismatch';
  delta: number;
}

interface ReconciliationReport {
  reconciliation_date: string;
  total_vintiz_card: number;
  total_sumup: number;
  delta: number;
  matched_count: number;
  unmatched_vintiz: number;
  unmatched_sumup: number;
  lines: ReconciliationLine[];
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  matched: { label: '✓ Rapproché', color: 'bg-green-100 text-green-800' },
  vintiz_only: { label: 'Vintiz seulement', color: 'bg-yellow-100 text-yellow-800' },
  sumup_only: { label: 'SumUp seulement', color: 'bg-orange-100 text-orange-800' },
  amount_mismatch: { label: 'Écart montant', color: 'bg-red-100 text-red-800' },
};

function fmt2(v: number) { return v.toFixed(2); }

export default function ReconciliationPage() {
  const [targetDate, setTargetDate] = useState(new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    setLoading(true);
    setError('');
    setReport(null);
    try {
      const data: ReconciliationReport = await api.get(`/api/accounting/reconciliation/${targetDate}`).then(r => r.json());
      setReport(data);
    } catch (e: any) {
      setError(e?.message || 'Erreur lors de la réconciliation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="max-w-5xl mx-auto space-y-6">
          <div>
            <h1 className="text-2xl font-display font-semibold text-vz-ink">Réconciliation SumUp</h1>
            <p className="text-vz-ink-soft mt-1">Comparaison des paiements CB Vintiz vs les transactions SumUp.</p>
          </div>

          <Card>
            <div className="flex items-center gap-4">
              <label className="text-sm text-vz-ink-soft">Date à réconcilier</label>
              <Input
                type="date"
                value={targetDate}
                onChange={e => setTargetDate(e.target.value)}
                className="text-sm w-44"
              />
              <Button onClick={run} disabled={loading}>
                {loading ? 'Analyse en cours…' : 'Lancer la réconciliation'}
              </Button>
            </div>
            <p className="text-xs text-vz-ink-mute mt-3">
              Requiert une clé API SumUp configurée. Les transactions SumUp SUCCESSFUL de la journée sont comparées aux paiements CB Vintiz.
            </p>
          </Card>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3 text-sm">{error}</div>
          )}

          {report && (
            <>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: 'Total CB Vintiz', value: `${fmt2(report.total_vintiz_card)} €`, color: '' },
                  { label: 'Total SumUp', value: `${fmt2(report.total_sumup)} €`, color: '' },
                  {
                    label: 'Écart',
                    value: `${report.delta >= 0 ? '+' : ''}${fmt2(report.delta)} €`,
                    color: Math.abs(report.delta) < 0.01 ? 'text-green-700' : 'text-red-600',
                  },
                  {
                    label: 'Rapprochés',
                    value: `${report.matched_count} / ${report.lines.filter(l => l.status !== 'sumup_only').length}`,
                    color: '',
                  },
                ].map(k => (
                  <Card key={k.label}>
                    <p className="text-xs text-vz-ink-mute">{k.label}</p>
                    <p className={`text-xl font-semibold mt-1 font-mono ${k.color || 'text-vz-ink'}`}>{k.value}</p>
                  </Card>
                ))}
              </div>

              {(report.unmatched_vintiz > 0 || report.unmatched_sumup > 0) && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-800">
                  ⚠️ {report.unmatched_vintiz} paiement(s) Vintiz sans contrepartie SumUp — {report.unmatched_sumup} transaction(s) SumUp sans contrepartie Vintiz.
                </div>
              )}

              <div className="bg-white rounded-xl border border-vz-line overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-vz-line bg-vz-bg-alt">
                      <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Ticket Vintiz</th>
                      <th className="text-right px-3 py-3 text-vz-ink-soft font-medium">Montant Vintiz</th>
                      <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Code SumUp</th>
                      <th className="text-right px-3 py-3 text-vz-ink-soft font-medium">Montant SumUp</th>
                      <th className="text-right px-3 py-3 text-vz-ink-soft font-medium">Δ</th>
                      <th className="text-center px-3 py-3 text-vz-ink-soft font-medium">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.lines.map((ln, i) => {
                      const st = STATUS_CONFIG[ln.status];
                      return (
                        <tr key={i} className="border-b border-vz-line hover:bg-vz-bg-alt/50">
                          <td className="px-3 py-2 font-mono text-xs text-vz-ink">
                            {ln.vintiz_transaction_number > 0 ? `#${ln.vintiz_transaction_number}` : '—'}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-vz-ink">
                            {ln.vintiz_amount > 0 ? `${fmt2(ln.vintiz_amount)} €` : '—'}
                          </td>
                          <td className="px-3 py-2 font-mono text-xs text-vz-ink-mute">
                            {ln.sumup_transaction_code || '—'}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-vz-ink">
                            {ln.sumup_amount !== null ? `${fmt2(ln.sumup_amount)} €` : '—'}
                          </td>
                          <td className={`px-3 py-2 text-right font-mono text-xs ${Math.abs(ln.delta) > 0.01 ? 'text-red-600 font-bold' : 'text-vz-ink-mute'}`}>
                            {Math.abs(ln.delta) > 0.005 ? `${ln.delta >= 0 ? '+' : ''}${fmt2(ln.delta)} €` : '—'}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${st.color}`}>
                              {st.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
