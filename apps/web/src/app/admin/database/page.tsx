'use client';

/**
 * Gestionnaire de base de données (admin, manager only).
 *
 * - État de la base : moteur, taille, volumes par table, dernière sauvegarde.
 * - Sauvegardes : liste (auto/manuelle), téléchargement, suppression, et
 *   déclenchement manuel d'une sauvegarde complète.
 * - Réglages : rétention, email d'alerte, activation du cron nocturne (03:00).
 * - Exports : CSV par table.
 *
 * La sauvegarde nocturne tourne côté serveur à 3h ; en cas d'échec un mail est
 * envoyé au destinataire d'alerte. Chaque sauvegarde est une ligne ci-dessous.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface BackupManifest {
  format?: string;
  database?: { bytes?: number };
  photos?: { included?: boolean };
  config?: { files?: string[] };
}

interface BackupRow {
  id: string;
  filename: string;
  size_bytes: number | null;
  status: 'pending' | 'success' | 'failed' | string;
  trigger: 'auto' | 'manual' | string;
  db_engine: string | null;
  kind?: 'full' | 'db' | string;
  manifest?: BackupManifest | null;
  error: string | null;
  created_at: string | null;
  duration_ms: number | null;
  downloadable: boolean;
}

interface DbState {
  engine: string;
  size_bytes: number | null;
  table_counts: Record<string, number>;
  backup_count: number;
  last_backup: BackupRow | null;
  last_success_at: string | null;
  backup_dir: string;
  exportable_tables: string[];
}

interface BackupConfig {
  retention_days: number;
  alert_email: string | null;
  enabled: boolean;
  include_files: boolean;
}

function humanSize(bytes: number | null): string {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} o`;
  const units = ['Ko', 'Mo', 'Go', 'To'];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}

function fmtDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
    + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function coverageLabel(b: BackupRow): string {
  if (b.kind !== 'full') return 'Base seule';
  const parts = ['Base'];
  const cfg = b.manifest?.config?.files?.length ?? 0;
  if (cfg > 0) parts.push('config');
  return parts.join(' + ');
}

const STATUS_BADGE: Record<string, string> = {
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
};

const TABLE_LABELS: Record<string, string> = {
  products: 'Produits',
  categories: 'Catégories',
  clients: 'Clients',
  loyalty_accounts: 'Cartes fidélité',
  transactions: 'Transactions',
  users: 'Utilisateurs',
  newsletter_subscribers: 'Newsletter',
};

export default function DatabaseManagerPage() {
  const [state, setState] = useState<DbState | null>(null);
  const [backups, setBackups] = useState<BackupRow[]>([]);
  const [config, setConfig] = useState<BackupConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [savingCfg, setSavingCfg] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind: 'success' | 'error' } | null>(null);

  const notify = useCallback((msg: string, kind: 'success' | 'error' = 'success') => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [sRes, bRes, cRes] = await Promise.all([
        api.get('/api/admin/database/state'),
        api.get('/api/admin/database/backups'),
        api.get('/api/admin/database/config'),
      ]);
      if (sRes.ok) setState(await sRes.json());
      if (bRes.ok) setBackups((await bRes.json()).backups || []);
      if (cRes.ok) setConfig(await cRes.json());
    } catch {
      notify('Erreur de chargement', 'error');
    }
    setLoading(false);
  }, [notify]);

  useEffect(() => { refresh(); }, [refresh]);

  const downloadBlob = async (url: string, fallbackName: string) => {
    try {
      const res = await api.get(url);
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        notify(e.detail || 'Téléchargement impossible', 'error');
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = fallbackName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
    } catch {
      notify('Erreur réseau au téléchargement', 'error');
    }
  };

  const runBackup = async () => {
    setRunning(true);
    try {
      const res = await api.post('/api/admin/database/backups/run', {});
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        notify('Sauvegarde créée');
      } else {
        notify(data.detail || 'Échec de la sauvegarde', 'error');
      }
    } catch {
      notify('Erreur réseau', 'error');
    }
    setRunning(false);
    refresh();
  };

  const deleteBackup = async (id: string) => {
    if (!confirm('Supprimer définitivement cette sauvegarde ?')) return;
    try {
      const res = await api.delete(`/api/admin/database/backups/${id}`);
      if (res.ok) { notify('Sauvegarde supprimée'); refresh(); }
      else notify('Suppression impossible', 'error');
    } catch { notify('Erreur réseau', 'error'); }
  };

  const saveConfig = async () => {
    if (!config) return;
    setSavingCfg(true);
    try {
      const res = await api.put('/api/admin/database/config', {
        retention_days: Number(config.retention_days),
        alert_email: config.alert_email || null,
        enabled: config.enabled,
        include_files: config.include_files,
      });
      if (res.ok) { setConfig(await res.json()); notify('Réglages enregistrés'); }
      else notify('Échec de l\'enregistrement', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSavingCfg(false);
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-10 md:p-8">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold text-black">Base de données</h1>
              <p className="text-sm text-gray-500">État, sauvegardes et exports</p>
            </div>
            <Button onClick={runBackup} disabled={running}>
              {running ? 'Sauvegarde en cours…' : '⬇ Lancer une sauvegarde'}
            </Button>
          </div>

          {toast && (
            <div role="status" className={`px-4 py-3 rounded-xl text-sm font-medium ${toast.kind === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
              {toast.msg}
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-16">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-vz-teal" />
            </div>
          ) : (
            <>
              {/* État de la base */}
              {state && (
                <Card title="État de la base">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                    <div><p className="text-xs text-gray-500">Moteur</p><p className="text-sm font-medium text-black uppercase">{state.engine}</p></div>
                    <div><p className="text-xs text-gray-500">Taille</p><p className="text-sm font-medium text-black">{humanSize(state.size_bytes)}</p></div>
                    <div><p className="text-xs text-gray-500">Sauvegardes</p><p className="text-sm font-medium text-black">{state.backup_count}</p></div>
                    <div><p className="text-xs text-gray-500">Dernière réussie</p><p className="text-sm font-medium text-black">{fmtDate(state.last_success_at)}</p></div>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {Object.entries(state.table_counts).map(([k, v]) => (
                      <div key={k} className="bg-gray-50 rounded-lg p-2.5">
                        <p className="text-xs text-gray-500">{TABLE_LABELS[k] || k}</p>
                        <p className="text-lg font-bold text-vz-teal">{v < 0 ? '—' : v}</p>
                      </div>
                    ))}
                  </div>
                  <p className="text-[11px] text-gray-400 mt-3 font-mono break-all">Dossier&nbsp;: {state.backup_dir}</p>
                </Card>
              )}

              {/* Réglages */}
              {config && (
                <Card title="Réglages de sauvegarde">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Rétention (jours)</label>
                      <Input type="number" min="1" value={String(config.retention_days)}
                        onChange={(e) => setConfig({ ...config, retention_days: parseInt(e.target.value || '1', 10) })} />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-black mb-1.5">Email d&apos;alerte (échec)</label>
                      <Input type="email" placeholder="ops@vintiz.fr" value={config.alert_email || ''}
                        onChange={(e) => setConfig({ ...config, alert_email: e.target.value })} />
                    </div>
                  </div>
                  <label className="flex items-center gap-2 mt-4 cursor-pointer">
                    <input type="checkbox" checked={config.enabled}
                      onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                      className="w-4 h-4 accent-vz-teal" />
                    <span className="text-sm text-gray-700">Sauvegarde automatique chaque nuit à 3&nbsp;h</span>
                  </label>
                  <label className="flex items-start gap-2 mt-3 cursor-pointer">
                    <input type="checkbox" checked={config.include_files}
                      onChange={(e) => setConfig({ ...config, include_files: e.target.checked })}
                      className="w-4 h-4 mt-0.5 accent-vz-teal" />
                    <span className="text-sm text-gray-700">
                      Sauvegarde <strong>complète</strong> (base + configuration)
                      <span className="block text-xs text-gray-500">
                        Inclut, en plus de la base : la configuration boutique &amp; matériel
                        (.tar.gz). Les photos ne sont pas archivées — seuls leurs liens sont
                        conservés (dans la base). Décocher pour ne garder que la base (.sql.gz).
                      </span>
                    </span>
                  </label>
                  <div className="mt-4">
                    <Button onClick={saveConfig} disabled={savingCfg}>
                      {savingCfg ? 'Enregistrement…' : 'Enregistrer les réglages'}
                    </Button>
                  </div>
                </Card>
              )}

              {/* Exports CSV */}
              {state && state.exportable_tables.length > 0 && (
                <Card title="Exports CSV">
                  <p className="text-sm text-gray-500 mb-3">Générer un export d&apos;une table au format CSV.</p>
                  <div className="flex flex-wrap gap-2">
                    {state.exportable_tables.map((t) => (
                      <Button key={t} variant="outline"
                        onClick={() => downloadBlob(`/api/admin/database/export?table=${t}`, `vintiz_${t}.csv`)}>
                        ⬇ {TABLE_LABELS[t] || t}
                      </Button>
                    ))}
                  </div>
                </Card>
              )}

              {/* Liste des sauvegardes */}
              <Card title="Sauvegardes">
                {backups.length === 0 ? (
                  <p className="text-sm text-gray-400 py-4 text-center">Aucune sauvegarde enregistrée.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                          <th className="py-2 pr-3">Date</th>
                          <th className="py-2 pr-3">Type</th>
                          <th className="py-2 pr-3">Contenu</th>
                          <th className="py-2 pr-3">Statut</th>
                          <th className="py-2 pr-3">Taille</th>
                          <th className="py-2 pr-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backups.map((b) => (
                          <tr key={b.id} className="border-b border-gray-50">
                            <td className="py-2 pr-3 text-gray-700">{fmtDate(b.created_at)}</td>
                            <td className="py-2 pr-3 text-gray-600">{b.trigger === 'auto' ? 'Auto (nuit)' : 'Manuelle'}</td>
                            <td className="py-2 pr-3">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${b.kind === 'full' ? 'bg-vz-teal-soft text-vz-teal-deep' : 'bg-gray-100 text-gray-600'}`}>
                                {coverageLabel(b)}
                              </span>
                            </td>
                            <td className="py-2 pr-3">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[b.status] || 'bg-gray-100 text-gray-600'}`}>
                                {b.status === 'success' ? 'Réussie' : b.status === 'failed' ? 'Échec' : b.status}
                              </span>
                              {b.status === 'failed' && b.error && (
                                <span className="block text-[11px] text-red-500 mt-0.5 max-w-xs truncate" title={b.error}>{b.error}</span>
                              )}
                            </td>
                            <td className="py-2 pr-3 text-gray-600">{humanSize(b.size_bytes)}</td>
                            <td className="py-2 pr-3">
                              <div className="flex justify-end gap-2">
                                {b.downloadable && (
                                  <button onClick={() => downloadBlob(`/api/admin/database/backups/${b.id}/download`, b.filename)}
                                    className="text-vz-teal hover:underline text-sm">Télécharger</button>
                                )}
                                <button onClick={() => deleteBackup(b.id)}
                                  className="text-red-500 hover:underline text-sm">Supprimer</button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
