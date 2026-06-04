'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface ExportLine {
  line_number: number;
  account_number: string;
  account_label: string;
  debit: number;
  credit: number;
  label: string;
  piece_reference: string | null;
  piece_date: string | null;
}

interface ExportDetail {
  id: string;
  export_date: string;
  status: string;
  net_ttc: number;
  total_sales_ht: number;
  total_tva: number;
  total_sales_ttc: number;
  total_refunds_ttc: number;
  transaction_count: number;
  refund_count: number;
  cash_total: number;
  card_total: number;
  cheque_total: number;
  cheque_cdc_total: number;
  avoir_total: number;
  transfer_total: number;
  cash_expected: number | null;
  cash_counted: number | null;
  cash_discrepancy: number | null;
  discrepancy_alert_sent: boolean;
  pennylane_ledger_event_id: string | null;
  pennylane_exported_at: string | null;
  pennylane_error: string | null;
  pennylane_attempts: number;
  fec_filename: string | null;
  email_sent_at: string | null;
  email_sent_to: string | null;
  locked_at: string | null;
  lines: ExportLine[];
}

const STATUS_COLOR: Record<string, string> = {
  exported: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  manual: 'bg-blue-100 text-blue-800',
  pending: 'bg-yellow-100 text-yellow-800',
};

function fmt2(v: number) { return v.toFixed(2); }
function fmtDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function ExportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [exp, setExp] = useState<ExportDetail | null>(null);
  const [retrying, setRetrying] = useState(false);

  const load = () => {
    api.get(`/api/accounting/exports/${id}`).then(r => r.json()).then(setExp);
  };

  useEffect(() => { load(); }, [id]);

  const retry = async () => {
    setRetrying(true);
    try {
      await api.post(`/api/accounting/exports/${id}/retry`, {}).then(r => r.json());
      load();
    } finally {
      setRetrying(false);
    }
  };

  const [regenerating, setRegenerating] = useState(false);
  const [regenError, setRegenError] = useState<string | null>(null);

  // Régénère le FEC à partir des transactions liées (Tx.accounting_export_id).
  // À utiliser quand le FEC actuel a été produit avec une version buguée du
  // moteur (ex. bons cadeaux non comptabilisés → débit < crédit). La chaîne
  // fiscale NF525 n'est PAS touchée — seules les lignes d'écriture et le
  // fichier FEC sont recalculés.
  const regenerate = async () => {
    if (!exp) return;
    const ok = window.confirm(
      'Régénérer le FEC ?\n\n' +
      'Recalcule la ventilation comptable et le fichier FEC à partir des ' +
      'transactions liées. La chaîne fiscale (hash NF525) n\'est pas modifiée. ' +
      'À utiliser pour corriger un FEC déséquilibré produit par une version ' +
      'antérieure du moteur.'
    );
    if (!ok) return;
    setRegenerating(true);
    setRegenError(null);
    try {
      const res = await api.post(`/api/accounting/exports/${id}/regenerate`, {});
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setRegenError(body.detail || `Régénération impossible (HTTP ${res.status})`);
        return;
      }
      await load();
    } catch {
      setRegenError('Erreur réseau pendant la régénération.');
    } finally {
      setRegenerating(false);
    }
  };

  // Détecte un FEC déséquilibré pour mettre en avant le bouton « Régénérer ».
  const balance = useMemo(() => {
    if (!exp) return { debit: 0, credit: 0, diff: 0, balanced: true };
    const debit = (exp.lines || []).reduce((s, l) => s + (l.debit || 0), 0);
    const credit = (exp.lines || []).reduce((s, l) => s + (l.credit || 0), 0);
    return {
      debit: Math.round(debit * 100) / 100,
      credit: Math.round(credit * 100) / 100,
      diff: Math.round((debit - credit) * 100) / 100,
      balanced: Math.abs(debit - credit) < 0.01,
    };
  }, [exp]);

  const downloadFec = async () => {
    if (!exp?.fec_filename) return;
    // Voir page liste : download authentifié via blob (token + base API),
    // sinon window.open tape le front et renvoie une page 404.
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
      link.download = exp.fec_filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(objectUrl);
    } catch {
      alert('Erreur réseau pendant le téléchargement du FEC');
    }
  };

  if (!exp) {
    return (
      <div className="min-h-screen bg-vz-bg">
        <Sidebar />
        <main className="md:ml-64 flex items-center justify-center min-h-screen">
          <p className="text-vz-ink-mute">Chargement…</p>
        </main>
      </div>
    );
  }

  const discColor = exp.cash_discrepancy !== null && Math.abs(exp.cash_discrepancy) > 5 ? 'text-red-600' : 'text-green-600';
  const totalDebit = exp.lines.reduce((s, l) => s + l.debit, 0);
  const totalCredit = exp.lines.reduce((s, l) => s + l.credit, 0);
  const balanced = Math.abs(totalDebit - totalCredit) < 0.005;

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center gap-4">
            <button onClick={() => router.back()} className="text-vz-ink-mute hover:text-vz-ink text-sm">← Retour</button>
            <div className="flex-1">
              <h1 className="text-2xl font-display font-semibold text-vz-ink">
                Clôture du {new Date(exp.export_date).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}
              </h1>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLOR[exp.status] || STATUS_COLOR.pending}`}>
              {exp.status}
            </span>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'CA net TTC', value: `${fmt2(exp.net_ttc)} €`, color: 'text-vz-teal' },
              { label: 'Ventes brutes', value: `${fmt2(exp.total_sales_ttc)} €`, color: '' },
              { label: 'Remboursements', value: `−${fmt2(exp.total_refunds_ttc)} €`, color: 'text-red-500' },
              { label: 'Transactions', value: `${exp.transaction_count} v.`, color: '' },
            ].map(k => (
              <Card key={k.label}>
                <p className="text-xs text-vz-ink-mute">{k.label}</p>
                <p className={`text-xl font-semibold mt-1 ${k.color || 'text-vz-ink'}`}>{k.value}</p>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Répartition encaissements */}
            <Card>
              <h2 className="font-semibold text-vz-ink mb-3">Encaissements par méthode</h2>
              <table className="w-full text-sm">
                <tbody>
                  {[
                    ['Espèces', exp.cash_total],
                    ['CB SumUp', exp.card_total],
                    ['Chèques', exp.cheque_total],
                    ['Club des Commerçants', exp.cheque_cdc_total],
                    ['Avoirs', exp.avoir_total],
                    ['Virements', exp.transfer_total],
                  ].filter(([, v]) => (v as number) !== 0).map(([label, value]) => (
                    <tr key={label as string} className="border-b border-vz-line last:border-0">
                      <td className="py-2 text-vz-ink-soft">{label as string}</td>
                      <td className="py-2 text-right font-mono text-vz-ink">{fmt2(value as number)} €</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            {/* Contrôle de caisse */}
            <Card>
              <h2 className="font-semibold text-vz-ink mb-3">Contrôle de caisse</h2>
              {exp.cash_expected !== null ? (
                <table className="w-full text-sm">
                  <tbody>
                    <tr className="border-b border-vz-line">
                      <td className="py-2 text-vz-ink-soft">Attendu</td>
                      <td className="py-2 text-right font-mono">{fmt2(exp.cash_expected)} €</td>
                    </tr>
                    <tr className="border-b border-vz-line">
                      <td className="py-2 text-vz-ink-soft">Compté</td>
                      <td className="py-2 text-right font-mono">{exp.cash_counted !== null ? `${fmt2(exp.cash_counted)} €` : '—'}</td>
                    </tr>
                    <tr>
                      <td className="py-2 font-medium text-vz-ink">Écart</td>
                      <td className={`py-2 text-right font-mono font-bold ${discColor}`}>
                        {exp.cash_discrepancy !== null ? `${exp.cash_discrepancy >= 0 ? '+' : ''}${fmt2(exp.cash_discrepancy)} €` : '—'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              ) : (
                <p className="text-vz-ink-mute text-sm">Données de caisse non disponibles.</p>
              )}
            </Card>
          </div>

          {/* Statut Pennylane */}
          <Card>
            <h2 className="font-semibold text-vz-ink mb-3">Export Pennylane</h2>
            <div className="space-y-2 text-sm">
              {exp.pennylane_exported_at && (
                <p className="text-green-700">✓ Exporté le {fmtDate(exp.pennylane_exported_at)} — ID : <code className="font-mono text-xs bg-green-50 px-1">{exp.pennylane_ledger_event_id}</code></p>
              )}
              {exp.pennylane_error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                  <p className="text-red-800 font-medium">Erreur ({exp.pennylane_attempts} tentative{exp.pennylane_attempts > 1 ? 's' : ''})</p>
                  <p className="text-red-600 text-xs mt-1 font-mono">{exp.pennylane_error}</p>
                </div>
              )}
              {exp.fec_filename && (
                <div className="flex items-center gap-3">
                  <span className="text-vz-ink-soft">FEC : {exp.fec_filename}</span>
                  <button onClick={downloadFec} className="text-vz-teal text-xs hover:underline">Télécharger</button>
                </div>
              )}
              {exp.email_sent_at && (
                <p className="text-vz-ink-soft">Email envoyé à {exp.email_sent_to} le {fmtDate(exp.email_sent_at)}</p>
              )}
            </div>
            {/* Détection FEC déséquilibré : un FEC dont la somme débit ≠
                crédit est ILLÉGAL (NF525 + DGFiP). On surface clairement et
                on propose la régénération depuis les transactions liées. */}
            {!balance.balanced && (
              <div className="mt-4 p-3 rounded-lg bg-red-50 border-2 border-red-300 text-red-900 text-sm">
                <p className="font-semibold">
                  ⚠ FEC déséquilibré : débit {balance.debit.toFixed(2)} € ≠ crédit {balance.credit.toFixed(2)} €
                  &nbsp;(écart {balance.diff > 0 ? '+' : ''}{balance.diff.toFixed(2)} €)
                </p>
                <p className="text-xs mt-1 text-red-700">
                  Causé par une version buguée du moteur (ex. bons cadeaux
                  non comptabilisés). Régénérer recalcule la ventilation à
                  partir des transactions liées sans toucher à la chaîne fiscale.
                </p>
              </div>
            )}
            <div className="mt-4 pt-4 border-t border-vz-line flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={balance.balanced ? 'outline' : 'primary'}
                onClick={regenerate}
                disabled={regenerating}
              >
                {regenerating ? 'Régénération…' : 'Régénérer le FEC'}
              </Button>
              {exp.status === 'failed' && (
                <Button size="sm" onClick={retry} disabled={retrying}>
                  {retrying ? 'Retry en cours…' : 'Re-exporter vers Pennylane'}
                </Button>
              )}
            </div>
            {regenError && (
              <p className="mt-2 text-xs text-red-600 font-mono">{regenError}</p>
            )}
          </Card>

          {/* Lignes d'écriture */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-vz-ink">Écriture comptable</h2>
              <span className={`text-xs px-2 py-1 rounded ${balanced ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                {balanced ? '✓ Équilibrée' : '✗ Déséquilibrée'}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vz-line bg-vz-bg-alt">
                    <th className="text-left px-3 py-2 text-vz-ink-soft font-medium">N°</th>
                    <th className="text-left px-3 py-2 text-vz-ink-soft font-medium">Compte</th>
                    <th className="text-left px-3 py-2 text-vz-ink-soft font-medium">Libellé</th>
                    <th className="text-right px-3 py-2 text-vz-ink-soft font-medium">Débit</th>
                    <th className="text-right px-3 py-2 text-vz-ink-soft font-medium">Crédit</th>
                    <th className="text-left px-3 py-2 text-vz-ink-soft font-medium">Pièce</th>
                  </tr>
                </thead>
                <tbody>
                  {exp.lines.map(ln => (
                    <tr key={ln.line_number} className="border-b border-vz-line hover:bg-vz-bg-alt/50">
                      <td className="px-3 py-2 text-vz-ink-mute font-mono text-xs">{ln.line_number}</td>
                      <td className="px-3 py-2 font-mono text-vz-ink text-xs">{ln.account_number}</td>
                      <td className="px-3 py-2 text-vz-ink">{ln.account_label}</td>
                      <td className="px-3 py-2 text-right font-mono text-green-700">{ln.debit > 0 ? `${fmt2(ln.debit)} €` : ''}</td>
                      <td className="px-3 py-2 text-right font-mono text-blue-700">{ln.credit > 0 ? `${fmt2(ln.credit)} €` : ''}</td>
                      <td className="px-3 py-2 text-xs text-vz-ink-mute font-mono">{ln.piece_reference || '—'}</td>
                    </tr>
                  ))}
                  <tr className="bg-vz-bg-alt font-semibold">
                    <td colSpan={3} className="px-3 py-2 text-right text-vz-ink-soft text-xs">TOTAUX</td>
                    <td className="px-3 py-2 text-right font-mono text-green-700">{fmt2(totalDebit)} €</td>
                    <td className="px-3 py-2 text-right font-mono text-blue-700">{fmt2(totalCredit)} €</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
