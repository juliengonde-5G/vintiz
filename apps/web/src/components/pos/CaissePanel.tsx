'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

interface ZReportRow {
  id: string;
  report_number: number;
  total_sales: number;
  total_refunds: number;
  total_net: number;
  transaction_count: number;
  is_locked: boolean;
  is_regularization?: boolean;
  regularization_reason?: string | null;
  emailed_at: string | null;
  created_at: string | null;
}

interface DrawerRow {
  id: string;
  opened_at: string;
  closed_at: string | null;
  opening_amount: number;
  closing_amount: number | null;
  expected_amount: number | null;
  difference: number | null;
  is_open: boolean;
}

interface RegPreview {
  period_from: string;
  period_to: string;
  orphan_count: number;
  sale_count: number;
  covered_count: number;
  has_overlap: boolean;
  open_drawers_count: number;
  can_regularize: boolean;
  total_sales: number;
  total_refunds: number;
  total_net: number;
  by_method: Record<string, number>;
  transaction_numbers: number[];
}

type CaisseTab = 'z' | 'sessions' | 'regularisation';

function fmtDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

export default function CaissePanel() {
  const [tab, setTab] = useState<CaisseTab>('z');
  const [zrows, setZrows] = useState<ZReportRow[]>([]);
  const [drawers, setDrawers] = useState<DrawerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState('');
  const [busy, setBusy] = useState(false);
  const [emailing, setEmailing] = useState<ZReportRow | null>(null);
  const [emailTarget, setEmailTarget] = useState('');

  const loadZ = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/pos/z-reports?limit=60');
      const data = await res.json();
      setZrows(Array.isArray(data) ? data : data.reports || []);
    } catch {
      /* noop */
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDrawers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/admin/cash-drawers?limit=50');
      setDrawers(res.ok ? await res.json() : []);
    } catch {
      /* noop */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'z') loadZ();
    else if (tab === 'sessions') loadDrawers();
  }, [tab, loadZ, loadDrawers]);

  const downloadPdf = async (z: ZReportRow) => {
    const res = await api.get(`/api/pos/z-reports/${z.id}/pdf`);
    if (!res.ok) {
      alert('Impossible de télécharger le rapport Z.');
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Z-${String(z.report_number).padStart(4, '0')}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const lockReport = async (z: ZReportRow) => {
    if (
      !window.confirm(
        `Verrouiller intangiblement le rapport Z #${z.report_number} ?\n\n` +
          `Irréversible (NF525 article 88 CGI).`,
      )
    )
      return;
    setBusy(true);
    try {
      const res = await api.post(`/api/pos/z-reports/${z.id}/lock`, {});
      if (res.ok) {
        await loadZ();
        setFlash(`Z #${z.report_number} verrouillé.`);
      } else alert('Verrouillage refusé.');
    } finally {
      setBusy(false);
    }
  };

  const sendEmail = async () => {
    if (!emailing) return;
    setBusy(true);
    try {
      const res = await api.post(`/api/pos/z-reports/${emailing.id}/email`, {
        to: emailTarget.trim() || null,
      });
      if (res.ok) {
        const data = await res.json();
        setFlash(`Z #${emailing.report_number} envoyé à ${data.emailed_to}.`);
        setEmailing(null);
        setEmailTarget('');
        await loadZ();
      } else {
        const d = await res.json().catch(() => ({}));
        alert(`Erreur : ${d.detail || res.statusText}`);
      }
    } finally {
      setBusy(false);
    }
  };

  const tabs: { key: CaisseTab; label: string }[] = [
    { key: 'z', label: 'Rapports Z' },
    { key: 'sessions', label: 'Sessions tiroir' },
    { key: 'regularisation', label: 'Régularisation' },
  ];

  return (
    <div className="space-y-4">
      {flash && (
        <div className="rounded-lg bg-vz-teal-soft px-4 py-3 text-sm text-vz-teal-deep">
          {flash}
          <button onClick={() => setFlash('')} className="ml-2 font-bold">
            &times;
          </button>
        </div>
      )}

      <div className="inline-flex rounded-xl border border-vz-line bg-vz-surface p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.key ? 'bg-vz-teal text-white' : 'text-vz-ink-soft hover:bg-vz-bg-alt'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'z' && (
        <Card>
          {loading ? (
            <p className="py-12 text-center text-vz-ink-mute">Chargement…</p>
          ) : zrows.length === 0 ? (
            <p className="py-12 text-center text-vz-ink-mute">Aucun rapport Z.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-vz-line text-xs uppercase tracking-wide text-vz-ink-mute">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">N°</th>
                    <th className="px-3 py-2 text-right">Ventes</th>
                    <th className="px-3 py-2 text-right">Net</th>
                    <th className="px-3 py-2 text-right">Tx</th>
                    <th className="px-3 py-2">Statut</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {zrows.map((z) => (
                    <tr key={z.id} className="border-b border-vz-line last:border-b-0">
                      <td className="px-3 py-3 font-mono text-xs text-vz-ink-soft">
                        {fmtDate(z.created_at)}
                      </td>
                      <td className="px-3 py-3 font-mono">
                        Z-{String(z.report_number).padStart(4, '0')}
                        {z.is_regularization && (
                          <span
                            title={z.regularization_reason || 'Régularisation a posteriori'}
                            className="ml-2 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700"
                          >
                            Régul.
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums">
                        {formatCurrency(z.total_sales)}
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
                            🔒 Verrouillé
                          </span>
                        ) : (
                          <span className="inline-block rounded-full bg-vz-accent-soft px-2 py-0.5 text-xs font-medium text-vz-ink">
                            Brouillon
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
                              className="text-xs text-vz-accent underline disabled:opacity-50"
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
      )}

      {tab === 'sessions' && (
        <Card>
          {loading ? (
            <p className="py-12 text-center text-vz-ink-mute">Chargement…</p>
          ) : drawers.length === 0 ? (
            <p className="py-12 text-center text-vz-ink-mute">Aucune session de caisse.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-vz-line text-xs uppercase tracking-wide text-vz-ink-mute">
                  <tr>
                    <th className="px-3 py-2">Ouverture</th>
                    <th className="px-3 py-2">Clôture</th>
                    <th className="px-3 py-2 text-right">Fond</th>
                    <th className="px-3 py-2 text-right">Attendu</th>
                    <th className="px-3 py-2 text-right">Compté</th>
                    <th className="px-3 py-2 text-right">Écart</th>
                    <th className="px-3 py-2">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {drawers.map((d) => (
                    <tr key={d.id} className="border-b border-vz-line last:border-b-0">
                      <td className="px-3 py-3 text-vz-ink-soft">{fmtDate(d.opened_at)}</td>
                      <td className="px-3 py-3 text-vz-ink-soft">{fmtDate(d.closed_at)}</td>
                      <td className="px-3 py-3 text-right">{formatCurrency(d.opening_amount)}</td>
                      <td className="px-3 py-3 text-right">
                        {d.expected_amount != null ? formatCurrency(d.expected_amount) : '—'}
                      </td>
                      <td className="px-3 py-3 text-right">
                        {d.closing_amount != null ? formatCurrency(d.closing_amount) : '—'}
                      </td>
                      <td className="px-3 py-3 text-right">
                        {d.difference != null ? (
                          <span
                            className={`font-semibold ${
                              d.difference === 0
                                ? 'text-green-600'
                                : d.difference > 0
                                  ? 'text-blue-600'
                                  : 'text-red-600'
                            }`}
                          >
                            {d.difference >= 0 ? '+' : ''}
                            {formatCurrency(d.difference)}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-3 py-3">
                        {d.is_open ? (
                          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                            Ouverte
                          </span>
                        ) : (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                            Clôturée
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
      )}

      {tab === 'regularisation' && (
        <RegularizationPanel
          onDone={(msg) => {
            setFlash(msg);
            setTab('z');
            void loadZ();
          }}
        />
      )}

      <Modal
        open={emailing !== null}
        onClose={() => setEmailing(null)}
        title={emailing ? `Envoyer Z-${String(emailing.report_number).padStart(4, '0')}` : ''}
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
        <div className="space-y-3">
          <p className="text-sm text-vz-ink-soft">
            Le PDF sera attaché. Laisse vide pour l&apos;adresse par défaut (/settings &gt;
            Communication).
          </p>
          <input
            type="email"
            value={emailTarget}
            onChange={(e) => setEmailTarget(e.target.value)}
            placeholder="comptable@example.fr"
            className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm"
          />
        </div>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Régularisation a posteriori — aperçu + établissement d'un Z pour un jour
// d'ouverture de caisse oublié.
// ---------------------------------------------------------------------------

function RegularizationPanel({ onDone }: { onDone: (msg: string) => void }) {
  const [day, setDay] = useState('');
  const [preview, setPreview] = useState<RegPreview | null>(null);
  const [reason, setReason] = useState('');
  const [closeOpen, setCloseOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const runPreview = async () => {
    if (!day) return;
    setLoading(true);
    setError('');
    setPreview(null);
    try {
      const res = await api.get(`/api/pos/z-reports/regularization/preview?date=${day}`);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Erreur aperçu');
      }
      setPreview(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur aperçu');
    } finally {
      setLoading(false);
    }
  };

  const create = async () => {
    if (!day || !reason.trim()) return;
    setCreating(true);
    setError('');
    try {
      const res = await api.post('/api/pos/z-reports/regularization', {
        date: day,
        reason: reason.trim(),
        close_open_drawers: closeOpen,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Échec de la régularisation');
      }
      const data = await res.json();
      const closedN = Array.isArray(data.closed_z_reports) ? data.closed_z_reports.length : 0;
      const parts: string[] = [];
      if (closedN > 0) parts.push(`${closedN} caisse(s) ouverte(s) clôturée(s)`);
      if (data.regularization) {
        parts.push(
          `Z de régularisation #${data.regularization.z_report_number} ` +
            `(${formatCurrency(data.regularization.total_net)} net) pour le ${day}`,
        );
      } else if (closedN > 0) {
        parts.push('journée déjà couverte par la clôture — aucune régularisation nécessaire');
      }
      onDone(parts.join(' · ') || 'Opération effectuée.');
      setDay('');
      setReason('');
      setCloseOpen(false);
      setPreview(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Échec de la régularisation');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Card>
      <div className="space-y-4">
        <div>
          <h3 className="font-semibold text-vz-ink">Clôture de régularisation a posteriori</h3>
          <p className="mt-1 text-sm text-vz-ink-mute">
            Pour une journée dont l&apos;ouverture de caisse a été oubliée. Le Z est créé à sa
            date réelle, numéroté à la suite et chaîné sur le dernier Z (chaîne NF525 intacte,
            jamais antidatée). Fiscal seul : pas de recomptage des espèces.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
              Journée à régulariser
            </span>
            <input
              type="date"
              value={day}
              onChange={(e) => {
                setDay(e.target.value);
                setPreview(null);
              }}
              className="rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm"
            />
          </label>
          <Button onClick={() => void runPreview()} disabled={!day || loading}>
            {loading ? 'Analyse…' : 'Aperçu'}
          </Button>
        </div>

        {error && (
          <p className="rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">{error}</p>
        )}

        {preview && (
          <div className="rounded-lg border border-vz-line p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Ventes orphelines" value={String(preview.sale_count)} />
              <Stat label="CA net" value={formatCurrency(preview.total_net)} accent />
              <Stat label="Ventes TTC" value={formatCurrency(preview.total_sales)} />
              <Stat label="Remboursements" value={formatCurrency(preview.total_refunds)} />
            </div>

            {Object.keys(preview.by_method).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(preview.by_method).map(([m, amt]) => (
                  <span
                    key={m}
                    className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700"
                  >
                    {m} · {formatCurrency(amt)}
                  </span>
                ))}
              </div>
            )}

            {preview.has_overlap && !closeOpen && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                ⚠ {preview.covered_count} transaction(s) de cette journée sont déjà couvertes par
                une session de caisse{preview.open_drawers_count > 0 ? ' (restée ouverte)' : ''}.
                Impossible de régulariser sans double-comptage.
              </p>
            )}

            {preview.open_drawers_count > 0 && (
              <label className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <input
                  type="checkbox"
                  checked={closeOpen}
                  onChange={(e) => setCloseOpen(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  Clôturer d&apos;abord {preview.open_drawers_count} caisse(s) restée(s) ouverte(s)
                  (génère leur rapport Z) — débloque l&apos;ouverture du jour. Si la clôture couvre
                  déjà cette journée, aucune régularisation séparée ne sera créée.
                </span>
              </label>
            )}

            {preview.orphan_count === 0 && !preview.has_overlap && preview.open_drawers_count === 0 && (
              <p className="text-sm text-vz-ink-mute">
                Aucune transaction orpheline ce jour-là — rien à régulariser.
              </p>
            )}

            {(preview.can_regularize || (closeOpen && preview.open_drawers_count > 0)) && (
              <div className="space-y-2 border-t border-vz-line pt-3">
                <label className="block text-sm">
                  <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
                    Motif (obligatoire)
                  </span>
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Ex. ouverture de caisse oubliée le 05/06"
                    className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm"
                  />
                </label>
                <Button onClick={() => void create()} disabled={!reason.trim() || creating}>
                  {creating
                    ? 'Traitement…'
                    : closeOpen && preview.open_drawers_count > 0
                      ? 'Clôturer la caisse + régulariser'
                      : 'Établir la régularisation'}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg bg-vz-bg-alt p-3">
      <p className="text-xs text-vz-ink-mute">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold ${accent ? 'text-vz-teal' : 'text-vz-ink'}`}>
        {value}
      </p>
    </div>
  );
}
