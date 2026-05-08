'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';

type TerminalStatus = 'active' | 'inactive' | 'unknown';

interface Terminal {
  id: string;
  label: string;
  reader_id: string;
  status: TerminalStatus;
  last_heartbeat_at: string | null;
  last_heartbeat_status: string | null;
  location: string | null;
  is_default: boolean;
  notes: string | null;
}

interface Draft {
  id: string | null;
  label: string;
  reader_id: string;
  location: string;
  is_default: boolean;
  notes: string;
}

const EMPTY_DRAFT: Draft = {
  id: null,
  label: '',
  reader_id: '',
  location: '',
  is_default: false,
  notes: '',
};

function formatDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
    }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  );
}

function statusTone(t: Terminal): 'ok' | 'warn' | 'alert' {
  if (t.status === 'active' && t.last_heartbeat_status === 'ok') return 'ok';
  if (t.status === 'inactive' || t.last_heartbeat_status === 'not_found')
    return 'alert';
  return 'warn';
}

function freshnessLabel(s: string | null): string {
  if (!s) return 'jamais testé';
  const ageMin = Math.round((Date.now() - new Date(s).getTime()) / 60000);
  if (ageMin < 1) return 'à l’instant';
  if (ageMin < 60) return `il y a ${ageMin} min`;
  const h = Math.floor(ageMin / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.floor(h / 24);
  return `il y a ${d} j`;
}

/**
 * SumUp multi-terminal manager — surfaced in /settings &gt; Paiement.
 *
 * Vintiz now drives several SumUp Solo readers (caisse Lenovo + portable
 * Galaxy Tab). Each row exposes a heartbeat colour code so the manager
 * can spot a TPE that lost Wi-Fi before the cashier tries to use it.
 *
 * "Tester" hits ``POST /admin/sumup-terminals/{id}/ping`` which calls
 * the live SumUp Readers API in production (and reports "simulated" in
 * sandbox).
 */
export default function SumUpTerminalsPanel() {
  const [rows, setRows] = useState<Terminal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/sumup-terminals');
      if (res.ok) {
        const data = await res.json();
        setRows(data.terminals || []);
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

  const startCreate = (): void => setEditing({ ...EMPTY_DRAFT });
  const startEdit = (t: Terminal): void =>
    setEditing({
      id: t.id,
      label: t.label,
      reader_id: t.reader_id,
      location: t.location ?? '',
      is_default: t.is_default,
      notes: t.notes ?? '',
    });

  const save = async (): Promise<void> => {
    if (!editing) return;
    setBusy('save');
    const body = {
      label: editing.label,
      reader_id: editing.reader_id.trim(),
      location: editing.location || null,
      is_default: editing.is_default,
      notes: editing.notes || null,
    };
    try {
      const res = editing.id
        ? await api.put(`/api/admin/sumup-terminals/${editing.id}`, body)
        : await api.post('/api/admin/sumup-terminals', body);
      if (res.ok) {
        setEditing(null);
        await load();
      } else {
        const detail = await res.json().catch(() => ({}));
        alert(`Erreur : ${detail.detail || res.statusText}`);
      }
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(null);
  };

  const remove = async (t: Terminal): Promise<void> => {
    if (!window.confirm(`Supprimer le terminal "${t.label}" ?`)) return;
    setBusy(t.id);
    try {
      const res = await api.delete(`/api/admin/sumup-terminals/${t.id}`);
      if (res.ok || res.status === 204) await load();
      else alert('Erreur : suppression refusée.');
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(null);
  };

  const ping = async (t: Terminal): Promise<void> => {
    setBusy(t.id);
    setFlash(null);
    try {
      const res = await api.post(`/api/admin/sumup-terminals/${t.id}/ping`, {});
      if (res.ok) {
        const data = await res.json();
        const probe = data.probe || {};
        if (probe.mode === 'simulated') {
          setFlash(`${t.label} : SumUp en sandbox — heartbeat simulé.`);
        } else if (probe.ok) {
          setFlash(`${t.label} : connecté ✓`);
        } else {
          setFlash(`${t.label} : ${probe.error || 'injoignable'}`);
        }
        await load();
      } else {
        alert('Erreur : ping échoué.');
      }
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(null);
  };

  return (
    <Card>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-vz-ink">
            Terminaux SumUp
          </h2>
          <p className="text-sm text-vz-ink-mute">
            Multi-terminaux : déclare chaque TPE Solo enregistré sur le
            compte SumUp. Le terminal par défaut est celui qui sonne quand
            le POS pousse un paiement CB.
          </p>
        </div>
        <Button onClick={startCreate}>Ajouter un terminal</Button>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
          {error}
        </p>
      )}
      {flash && (
        <p className="mb-3 rounded-lg bg-vz-teal-soft px-4 py-3 text-sm text-vz-teal-deep">
          {flash}
        </p>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-vz-ink-mute">
          Chargement…
        </p>
      ) : rows.length === 0 ? (
        <p className="rounded-lg bg-vz-bg-alt px-3 py-4 text-sm text-vz-ink-mute">
          Aucun terminal déclaré. Le POS continuera d'utiliser
          ``SUMUP_READER_ID`` (env var) tant que la table reste vide.
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((t) => {
            const tone = statusTone(t);
            const dot =
              tone === 'ok'
                ? 'bg-vz-teal'
                : tone === 'warn'
                  ? 'bg-vz-gold'
                  : 'bg-vz-accent';
            return (
              <li
                key={t.id}
                className="rounded-xl border border-vz-line bg-vz-surface p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span
                        className={`inline-block h-2.5 w-2.5 rounded-full ${dot}`}
                        aria-hidden="true"
                      />
                      <span className="truncate text-sm font-semibold text-vz-ink">
                        {t.label}
                      </span>
                      {t.is_default && (
                        <span className="rounded-full bg-vz-teal-soft px-2 py-0.5 text-xs font-medium text-vz-teal-deep">
                          Par défaut
                        </span>
                      )}
                    </div>
                    <div className="font-mono text-xs text-vz-ink-mute">
                      {t.reader_id}
                    </div>
                    <div className="text-xs text-vz-ink-mute">
                      {t.location ? `📍 ${t.location} · ` : ''}
                      Heartbeat : {t.last_heartbeat_status || '—'} (
                      {freshnessLabel(t.last_heartbeat_at)})
                    </div>
                    {t.notes && (
                      <div className="mt-1 text-xs italic text-vz-ink-soft">
                        {t.notes}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <button
                      type="button"
                      disabled={busy === t.id}
                      onClick={() => void ping(t)}
                      className="text-xs text-vz-teal underline disabled:opacity-50"
                    >
                      Tester la connexion
                    </button>
                    <button
                      type="button"
                      onClick={() => startEdit(t)}
                      className="text-xs text-vz-teal underline"
                    >
                      Modifier
                    </button>
                    <button
                      type="button"
                      disabled={busy === t.id}
                      onClick={() => void remove(t)}
                      className="text-xs text-vz-accent underline disabled:opacity-50"
                    >
                      Supprimer
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-3 text-xs text-vz-ink-mute">
        Comment trouver le <code>reader_id</code> ?{' '}
        <a
          href="https://developer.sumup.com/api/readers/get-list"
          target="_blank"
          rel="noopener"
          className="text-vz-teal underline"
        >
          Documentation SumUp
        </a>{' '}
        — récupère la liste depuis l'API Readers ou via l'app SumUp Pro.
      </p>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.id ? 'Modifier le terminal' : 'Nouveau terminal SumUp'}
        actions={
          <>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Annuler
            </Button>
            <Button
              onClick={() => void save()}
              disabled={busy === 'save' || !editing?.label || !editing?.reader_id}
            >
              {busy === 'save' ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </>
        }
      >
        {editing && (
          <div className="space-y-3">
            <Field
              label="Libellé"
              value={editing.label}
              onChange={(s) => setEditing({ ...editing, label: s })}
              placeholder="Caisse Lenovo dock"
            />
            <Field
              label="reader_id"
              value={editing.reader_id}
              onChange={(s) => setEditing({ ...editing, reader_id: s })}
              placeholder="reader_xxxxxxxxxxxxxxxx"
              mono
            />
            <Field
              label="Emplacement"
              value={editing.location}
              onChange={(s) => setEditing({ ...editing, location: s })}
              placeholder="Comptoir caisse / TPE mobile"
            />
            <Field
              label="Notes"
              value={editing.notes}
              onChange={(s) => setEditing({ ...editing, notes: s })}
              multiline
              placeholder="N° de série, date d'enrôlement…"
            />
            <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-vz-line bg-vz-surface px-3 py-2 hover:bg-vz-bg-alt">
              <input
                type="checkbox"
                checked={editing.is_default}
                onChange={(e) =>
                  setEditing({ ...editing, is_default: e.target.checked })
                }
                className="h-4 w-4 accent-vz-teal"
              />
              <div>
                <div className="text-sm font-medium text-vz-ink">
                  Terminal par défaut
                </div>
                <div className="text-xs text-vz-ink-mute">
                  Cocher démote l'ancien défaut. Le POS pousse les
                  paiements CB sur ce terminal.
                </div>
              </div>
            </label>
          </div>
        )}
      </Modal>
    </Card>
  );
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
  mono?: boolean;
}

function Field({ label, value, onChange, placeholder, multiline, mono }: FieldProps) {
  const baseClass =
    'w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal' +
    (mono ? ' font-mono' : '');
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-vz-ink-soft">
        {label}
      </span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={2}
          className={baseClass}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={baseClass}
        />
      )}
    </label>
  );
}
