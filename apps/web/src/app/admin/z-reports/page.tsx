'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

interface ZReportRow {
  id: string;
  report_number: number;
  cashier_id: string | null;
  total_sales: number;
  total_refunds: number;
  total_net: number;
  transaction_count: number;
  hash: string;
  previous_hash: string | null;
  is_locked: boolean;
  locked_at: string | null;
  emailed_at: string | null;
  emailed_to: string | null;
  created_at: string | null;
}

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

export default function AdminZReportsPage() {
  const [rows, setRows] = useState<ZReportRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [emailing, setEmailing] = useState<ZReportRow | null>(null);
  const [emailTarget, setEmailTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/pos/z-reports?limit=60');
      if (res.ok) {
        const data = await res.json();
        setRows(Array.isArray(data) ? data : data.reports || []);
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const downloadPdf = async (z: ZReportRow): Promise<void> => {
    try {
      const res = await api.get(`/api/pos/z-reports/${z.id}/pdf`);
      if (!res.ok) {
        alert('Erreur : impossible de télécharger le rapport Z.');
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Z-${String(z.report_number).padStart(4, '0')}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      alert('Erreur réseau.');
    }
  };

  const lockReport = async (z: ZReportRow): Promise<void> => {
    if (
      !window.confirm(
        `Verrouiller intangiblement le rapport Z #${z.report_number} ?\n\n` +
          `Cette action est irréversible (NF525 article 88 CGI). Le PDF est ` +
          `persisté tel quel et plus aucune modification n'est possible.`,
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await api.post(`/api/pos/z-reports/${z.id}/lock`, {});
      if (res.ok) {
        const data = await res.json();
        setFlash(
          data.already_locked
            ? `Z #${z.report_number} déjà verrouillé.`
            : `Z #${z.report_number} verrouillé. SHA-256 : ${data.pdf_sha256?.slice(0, 16)}…`,
        );
        await load();
      } else {
        alert('Erreur : verrouillage refusé.');
      }
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(false);
  };

  const sendEmail = async (): Promise<void> => {
    if (!emailing) return;
    setBusy(true);
    try {
      const res = await api.post(`/api/pos/z-reports/${emailing.id}/email`, {
        to: emailTarget.trim() || null,
      });
      if (res.ok) {
        const data = await res.json();
        setFlash(
          `Z #${emailing.report_number} envoyé à ${data.emailed_to} ` +
            `(${data.backend}/${data.status}).`,
        );
        setEmailing(null);
        setEmailTarget('');
        await load();
      } else {
        const detail = await res.json().catch(() => ({}));
        alert(`Erreur : ${detail.detail || res.statusText}`);
      }
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(false);
  };

  return (
    <div className="flex min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="flex-1 p-6 lg:p-8">
        <header className="mb-6">
          <h1 className="font-display text-3xl font-semibold text-vz-ink">
            Rapports Z
          </h1>
          <p className="text-sm text-vz-ink-mute">
            Clôtures journalières, conformes NF525 (article 88 CGI). Une
            fois verrouillé, le PDF est persisté byte-identique et
            l'empreinte SHA-256 figée.
          </p>
        </header>

        {flash && (
          <div className="mb-4 rounded-lg bg-vz-teal-soft px-4 py-3 text-sm text-vz-teal-deep">
            {flash}
          </div>
        )}

        <Card>
          {error && (
            <p className="rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
              {error}
            </p>
          )}
          {loading ? (
            <p className="py-12 text-center text-vz-ink-mute">Chargement…</p>
          ) : rows.length === 0 ? (
            <p className="py-12 text-center text-vz-ink-mute">
              Aucun rapport Z encore généré.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-vz-line text-xs uppercase tracking-wide text-vz-ink-mute">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">N°</th>
                    <th className="px-3 py-2 text-right">Ventes</th>
                    <th className="px-3 py-2 text-right">Remb.</th>
                    <th className="px-3 py-2 text-right">Net</th>
                    <th className="px-3 py-2 text-right">Tx</th>
                    <th className="px-3 py-2">Statut</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((z) => (
                    <tr
                      key={z.id}
                      className="border-b border-vz-line last:border-b-0"
                    >
                      <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                        {formatDate(z.created_at)}
                      </td>
                      <td className="px-3 py-3 font-mono">
                        Z-{String(z.report_number).padStart(4, '0')}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {formatCurrency(z.total_sales)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums text-vz-ink-soft">
                        {formatCurrency(z.total_refunds)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono font-semibold tabular-nums">
                        {formatCurrency(z.total_net)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {z.transaction_count}
                      </td>
                      <td className="px-3 py-3">
                        {z.is_locked ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-vz-teal-soft px-2 py-0.5 text-xs font-medium text-vz-teal-deep">
                            <span aria-hidden="true">🔒</span> Verrouillé
                          </span>
                        ) : (
                          <span className="inline-block rounded-full bg-vz-accent-soft px-2 py-0.5 text-xs font-medium text-vz-ink">
                            Brouillon
                          </span>
                        )}
                        {z.emailed_at && (
                          <span className="ml-2 text-xs text-vz-ink-mute">
                            Envoyé
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => void downloadPdf(z)}
                            className="text-xs text-vz-teal underline hover:text-vz-teal-deep"
                          >
                            PDF
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setEmailing(z);
                              setEmailTarget('');
                            }}
                            className="text-xs text-vz-teal underline hover:text-vz-teal-deep"
                          >
                            Email
                          </button>
                          {!z.is_locked && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void lockReport(z)}
                              className="text-xs text-vz-accent underline hover:text-vz-accent disabled:opacity-50"
                            >
                              Verrouiller
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>

      <Modal
        open={emailing !== null}
        onClose={() => setEmailing(null)}
        title={
          emailing
            ? `Envoyer Z-${String(emailing.report_number).padStart(4, '0')}`
            : ''
        }
        actions={
          <>
            <Button variant="outline" onClick={() => setEmailing(null)}>
              Annuler
            </Button>
            <Button onClick={() => void sendEmail()} disabled={busy}>
              {busy ? 'Envoi…' : 'Envoyer'}
            </Button>
          </>
        }
      >
        {emailing && (
          <div className="space-y-3">
            <p className="text-sm text-vz-ink-soft">
              Le PDF du rapport Z {emailing.is_locked ? '(verrouillé)' : '(en brouillon)'}{' '}
              sera attaché à l'email. Laisse vide pour utiliser l'adresse
              par défaut configurée dans /settings &gt; Communication.
            </p>
            <label className="block">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
                Destinataire
              </span>
              <input
                type="email"
                value={emailTarget}
                onChange={(e) => setEmailTarget(e.target.value)}
                placeholder="comptable@example.fr"
                className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
              />
            </label>
          </div>
        )}
      </Modal>
    </div>
  );
}
