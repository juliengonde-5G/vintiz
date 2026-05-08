'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';

type ReceiptKind = 'ticket' | 'invoice';

interface Template {
  id: string;
  name: string;
  kind: ReceiptKind;
  title: string;
  footer: string;
  conditions_retour: string | null;
  show_tva_breakdown: boolean;
  show_loyalty_footer: boolean;
  is_default: boolean;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface Draft {
  id: string | null;
  name: string;
  kind: ReceiptKind;
  title: string;
  footer: string;
  conditions_retour: string;
  show_tva_breakdown: boolean;
  show_loyalty_footer: boolean;
  is_active: boolean;
}

const EMPTY_DRAFT: Draft = {
  id: null,
  name: '',
  kind: 'ticket',
  title: 'VINTIZ',
  footer: 'Merci de votre visite',
  conditions_retour: '',
  show_tva_breakdown: false,
  show_loyalty_footer: true,
  is_active: true,
};

/**
 * Receipt / invoice templates manager — surfaced in /settings &gt;
 * Communication. Lets the manager personalise the printed ticket
 * (logo title, footer text, return conditions) without touching the
 * code. NF525 note: editing a template does NOT alter historical
 * receipts because the transaction snapshots ``template_id`` at sign
 * time.
 */
export default function ReceiptTemplatesPanel() {
  const [rows, setRows] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/receipt-templates');
      if (res.ok) {
        const data = await res.json();
        setRows(data.templates || []);
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
  const startEdit = (t: Template): void =>
    setEditing({
      id: t.id,
      name: t.name,
      kind: t.kind,
      title: t.title,
      footer: t.footer,
      conditions_retour: t.conditions_retour ?? '',
      show_tva_breakdown: t.show_tva_breakdown,
      show_loyalty_footer: t.show_loyalty_footer,
      is_active: t.is_active,
    });

  const save = async (): Promise<void> => {
    if (!editing) return;
    setBusy(true);
    const body = {
      name: editing.name,
      kind: editing.kind,
      title: editing.title,
      footer: editing.footer,
      conditions_retour: editing.conditions_retour || null,
      show_tva_breakdown: editing.show_tva_breakdown,
      show_loyalty_footer: editing.show_loyalty_footer,
      is_active: editing.is_active,
    };
    try {
      const res = editing.id
        ? await api.put(`/api/admin/receipt-templates/${editing.id}`, body)
        : await api.post('/api/admin/receipt-templates', body);
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
    setBusy(false);
  };

  const setDefault = async (t: Template): Promise<void> => {
    setBusy(true);
    try {
      const res = await api.post(
        `/api/admin/receipt-templates/${t.id}/set-default`,
        {},
      );
      if (res.ok) await load();
      else alert('Erreur : impossible de définir par défaut.');
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(false);
  };

  const deactivate = async (t: Template): Promise<void> => {
    if (
      !window.confirm(
        `Désactiver le template "${t.name}" ?\nIl ne sera plus proposé au POS.`,
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await api.delete(`/api/admin/receipt-templates/${t.id}`);
      if (res.ok || res.status === 204) await load();
      else {
        const detail = await res.json().catch(() => ({}));
        alert(`Erreur : ${detail.detail || res.statusText}`);
      }
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(false);
  };

  const tickets = rows.filter((r) => r.kind === 'ticket');
  const invoices = rows.filter((r) => r.kind === 'invoice');

  return (
    <Card>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-vz-ink">
            Templates de tickets et factures
          </h2>
          <p className="text-sm text-vz-ink-mute">
            Personnalise titre, footer et conditions de retour. Le template
            par défaut s'applique automatiquement aux nouvelles ventes du
            kind correspondant.
          </p>
        </div>
        <Button onClick={startCreate}>Nouveau template</Button>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-vz-ink-mute">
          Chargement…
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Section
            title="Tickets B2C"
            templates={tickets}
            onEdit={startEdit}
            onSetDefault={setDefault}
            onDeactivate={deactivate}
          />
          <Section
            title="Factures B2B"
            templates={invoices}
            onEdit={startEdit}
            onSetDefault={setDefault}
            onDeactivate={deactivate}
          />
        </div>
      )}

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing?.id ? 'Modifier le template' : 'Nouveau template'}
        actions={
          <>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Annuler
            </Button>
            <Button onClick={() => void save()} disabled={busy}>
              {busy ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </>
        }
      >
        {editing && (
          <div className="space-y-3">
            <Field
              label="Nom (interne)"
              value={editing.name}
              onChange={(s) => setEditing({ ...editing, name: s })}
            />
            <Field
              label="Titre imprimé"
              value={editing.title}
              onChange={(s) => setEditing({ ...editing, title: s })}
            />
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-vz-ink-soft">
                Type
              </span>
              <select
                value={editing.kind}
                onChange={(e) =>
                  setEditing({ ...editing, kind: e.target.value as ReceiptKind })
                }
                className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm"
              >
                <option value="ticket">Ticket B2C</option>
                <option value="invoice">Facture B2B</option>
              </select>
            </label>
            <Field
              label="Footer (multi-lignes)"
              value={editing.footer}
              onChange={(s) => setEditing({ ...editing, footer: s })}
              multiline
            />
            <Field
              label="Conditions de retour (optionnel)"
              value={editing.conditions_retour}
              onChange={(s) =>
                setEditing({ ...editing, conditions_retour: s })
              }
              multiline
            />
            <Toggle
              label="Détail TVA imprimé"
              hint="Recommandé pour les factures B2B"
              value={editing.show_tva_breakdown}
              onChange={(v) =>
                setEditing({ ...editing, show_tva_breakdown: v })
              }
            />
            <Toggle
              label="Bloc fidélité imprimé"
              hint="Affiche solde + points gagnés sur le ticket"
              value={editing.show_loyalty_footer}
              onChange={(v) =>
                setEditing({ ...editing, show_loyalty_footer: v })
              }
            />
            <Toggle
              label="Actif"
              hint="Les inactifs ne sont pas proposés au POS"
              value={editing.is_active}
              onChange={(v) => setEditing({ ...editing, is_active: v })}
            />
          </div>
        )}
      </Modal>
    </Card>
  );
}

function Section({
  title,
  templates,
  onEdit,
  onSetDefault,
  onDeactivate,
}: {
  title: string;
  templates: Template[];
  onEdit: (t: Template) => void;
  onSetDefault: (t: Template) => void;
  onDeactivate: (t: Template) => void;
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-vz-ink-mute">
        {title}
      </h3>
      {templates.length === 0 ? (
        <p className="rounded-lg bg-vz-bg-alt px-3 py-4 text-sm text-vz-ink-mute">
          Aucun template — clique « Nouveau template ».
        </p>
      ) : (
        <ul className="space-y-2">
          {templates.map((t) => (
            <li
              key={t.id}
              className="rounded-xl border border-vz-line bg-vz-surface p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-vz-ink">
                      {t.name}
                    </span>
                    {t.is_default && (
                      <span className="rounded-full bg-vz-teal-soft px-2 py-0.5 text-xs font-medium text-vz-teal-deep">
                        Par défaut
                      </span>
                    )}
                    {!t.is_active && (
                      <span className="rounded-full bg-vz-bg-alt px-2 py-0.5 text-xs text-vz-ink-mute">
                        Inactif
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-vz-ink-mute">
                    Titre : {t.title}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <button
                    type="button"
                    onClick={() => onEdit(t)}
                    className="text-xs text-vz-teal underline"
                  >
                    Modifier
                  </button>
                  {!t.is_default && t.is_active && (
                    <button
                      type="button"
                      onClick={() => onSetDefault(t)}
                      className="text-xs text-vz-teal underline"
                    >
                      Définir par défaut
                    </button>
                  )}
                  {t.is_active && !t.is_default && (
                    <button
                      type="button"
                      onClick={() => onDeactivate(t)}
                      className="text-xs text-vz-accent underline"
                    >
                      Désactiver
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}

function Field({ label, value, onChange, multiline }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-vz-ink-soft">
        {label}
      </span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm focus:border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
        />
      )}
    </label>
  );
}

function Toggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-vz-line bg-vz-surface px-3 py-2 hover:bg-vz-bg-alt">
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-vz-teal"
      />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-vz-ink">{label}</div>
        {hint && <div className="text-xs text-vz-ink-mute">{hint}</div>}
      </div>
    </label>
  );
}
