'use client';

import React, { useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface JournalLine {
  export_id: string;
  export_date: string;
  line_number: number;
  account_number: string;
  account_label: string;
  debit: number;
  credit: number;
  label: string;
  piece_reference: string | null;
}

function fmt2(v: number) { return v.toFixed(2); }
function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const today = new Date().toISOString().slice(0, 10);
const monthStart = today.slice(0, 8) + '01';

export default function JournalPage() {
  const [lines, setLines] = useState<JournalLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState(monthStart);
  const [dateTo, setDateTo] = useState(today);

  const load = () => {
    setLoading(true);
    api.get(`/api/accounting/journal?from=${dateFrom}&to=${dateTo}&limit=500`)
      .then(r => r.json())
      .then(setLines)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const totalDebit = lines.reduce((s, l) => s + l.debit, 0);
  const totalCredit = lines.reduce((s, l) => s + l.credit, 0);
  const balanced = Math.abs(totalDebit - totalCredit) < 0.01;

  return (
    <div className="flex h-screen bg-vz-bg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-display font-semibold text-vz-ink">Journal comptable</h1>
              <p className="text-vz-ink-soft mt-1">Toutes les lignes d'écriture sur la période sélectionnée.</p>
            </div>
            <div className="flex items-center gap-2">
              <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="text-sm" />
              <span className="text-vz-ink-mute">→</span>
              <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="text-sm" />
              <Button size="sm" onClick={load}>Filtrer</Button>
            </div>
          </div>

          {!loading && lines.length > 0 && (
            <div className="grid grid-cols-3 gap-4 mb-6">
              <Card>
                <p className="text-xs text-vz-ink-mute">Total Débit</p>
                <p className="text-xl font-semibold text-green-700 mt-1 font-mono">{fmt2(totalDebit)} €</p>
              </Card>
              <Card>
                <p className="text-xs text-vz-ink-mute">Total Crédit</p>
                <p className="text-xl font-semibold text-blue-700 mt-1 font-mono">{fmt2(totalCredit)} €</p>
              </Card>
              <Card>
                <p className="text-xs text-vz-ink-mute">Équilibre</p>
                <p className={`text-xl font-semibold mt-1 ${balanced ? 'text-green-700' : 'text-red-600'}`}>
                  {balanced ? '✓ Équilibré' : `Δ ${fmt2(Math.abs(totalDebit - totalCredit))} €`}
                </p>
              </Card>
            </div>
          )}

          {loading ? (
            <p className="text-vz-ink-mute text-center py-12">Chargement…</p>
          ) : lines.length === 0 ? (
            <Card>
              <p className="text-center text-vz-ink-mute py-8">Aucune écriture pour la période sélectionnée.</p>
            </Card>
          ) : (
            <div className="bg-white rounded-xl border border-vz-line overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vz-line bg-vz-bg-alt">
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Date</th>
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Compte</th>
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Libellé</th>
                    <th className="text-right px-3 py-3 text-vz-ink-soft font-medium">Débit</th>
                    <th className="text-right px-3 py-3 text-vz-ink-soft font-medium">Crédit</th>
                    <th className="text-left px-3 py-3 text-vz-ink-soft font-medium">Pièce</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((ln, i) => (
                    <tr key={i} className="border-b border-vz-line hover:bg-vz-bg-alt/50">
                      <td className="px-3 py-2 text-vz-ink-mute text-xs">{fmtDate(ln.export_date)}</td>
                      <td className="px-3 py-2 font-mono text-vz-ink text-xs">{ln.account_number}</td>
                      <td className="px-3 py-2 text-vz-ink">{ln.account_label}</td>
                      <td className="px-3 py-2 text-right font-mono text-green-700">{ln.debit > 0 ? `${fmt2(ln.debit)} €` : ''}</td>
                      <td className="px-3 py-2 text-right font-mono text-blue-700">{ln.credit > 0 ? `${fmt2(ln.credit)} €` : ''}</td>
                      <td className="px-3 py-2 text-xs text-vz-ink-mute font-mono">{ln.piece_reference || '—'}</td>
                    </tr>
                  ))}
                  <tr className="bg-vz-bg-alt font-semibold border-t-2 border-vz-line">
                    <td colSpan={3} className="px-3 py-2 text-right text-vz-ink-soft text-xs">TOTAUX ({lines.length} lignes)</td>
                    <td className="px-3 py-2 text-right font-mono text-green-700">{fmt2(totalDebit)} €</td>
                    <td className="px-3 py-2 text-right font-mono text-blue-700">{fmt2(totalCredit)} €</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
