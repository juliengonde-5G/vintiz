'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
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
  accent_color: string;
  header_note: string | null;
  payment_terms: string | null;
  legal_mentions: string | null;
  email_subject: string | null;
  email_body: string | null;
  show_payment_block: boolean;
  show_legal_mentions: boolean;
  is_default: boolean;
  is_active: boolean;
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
  accent_color: string;
  header_note: string;
  payment_terms: string;
  legal_mentions: string;
  email_subject: string;
  email_body: string;
  show_payment_block: boolean;
  show_legal_mentions: boolean;
  is_active: boolean;
}

const EMPTY_DRAFT: Draft = {
  id: null,
  name: '',
  kind: 'invoice',
  title: 'FACTURE',
  footer: 'Merci de votre confiance.',
  conditions_retour: '',
  show_tva_breakdown: true,
  show_loyalty_footer: false,
  accent_color: '#0B7A6A',
  header_note: '',
  payment_terms: 'Paiement à réception.',
  legal_mentions:
    'En cas de retard de paiement, une pénalité égale à 3 fois le taux d’intérêt légal sera exigible (art. L.441-10 C. com.), ainsi qu’une indemnité forfaitaire de 40 € pour frais de recouvrement.',
  email_subject: 'Votre facture {invoice_number} — {shop_name}',
  email_body:
    'Bonjour,\n\nVeuillez trouver ci-joint votre facture {invoice_number} d’un montant de {total_ttc}.\n\nCordialement,\n{shop_name}',
  show_payment_block: true,
  show_legal_mentions: true,
  is_active: true,
};

function toDraft(t: Template): Draft {
  return {
    id: t.id,
    name: t.name,
    kind: t.kind,
    title: t.title,
    footer: t.footer,
    conditions_retour: t.conditions_retour ?? '',
    show_tva_breakdown: t.show_tva_breakdown,
    show_loyalty_footer: t.show_loyalty_footer,
    accent_color: t.accent_color || '#0B7A6A',
    header_note: t.header_note ?? '',
    payment_terms: t.payment_terms ?? '',
    legal_mentions: t.legal_mentions ?? '',
    email_subject: t.email_subject ?? '',
    email_body: t.email_body ?? '',
    show_payment_block: t.show_payment_block,
    show_legal_mentions: t.show_legal_mentions,
    is_active: t.is_active,
  };
}

function draftToBody(d: Draft) {
  return {
    name: d.name,
    kind: d.kind,
    title: d.title,
    footer: d.footer,
    conditions_retour: d.conditions_retour || null,
    show_tva_breakdown: d.show_tva_breakdown,
    show_loyalty_footer: d.show_loyalty_footer,
    accent_color: d.accent_color,
    header_note: d.header_note || null,
    payment_terms: d.payment_terms || null,
    legal_mentions: d.legal_mentions || null,
    email_subject: d.email_subject || null,
    email_body: d.email_body || null,
    show_payment_block: d.show_payment_block,
    show_legal_mentions: d.show_legal_mentions,
    is_active: d.is_active,
  };
}

/**
 * Tickets & Factures studio — Settings page.
 *
 * Configure the printed ticket and the B2B invoice PDF (zones, fields, legal
 * mentions, accent colour) with a live preview, plus the configurable invoice
 * email (subject + body, PDF attached on send). NF525: editing a template does
 * NOT alter historical documents (the sale snapshots ``template_id``).
 */
export default function ReceiptInvoiceStudio() {
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

  const save = async (): Promise<void> => {
    if (!editing) return;
    if (!editing.name.trim()) {
      alert('Donnez un nom au template.');
      return;
    }
    setBusy(true);
    try {
      const body = draftToBody(editing);
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
      const res = await api.post(`/api/admin/receipt-templates/${t.id}/set-default`, {});
      if (res.ok) await load();
      else alert('Erreur : impossible de définir par défaut.');
    } catch {
      alert('Erreur réseau.');
    }
    setBusy(false);
  };

  const deactivate = async (t: Template): Promise<void> => {
    if (!window.confirm(`Désactiver le template "${t.name}" ?`)) return;
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

  if (editing) {
    return (
      <StudioEditor
        draft={editing}
        busy={busy}
        onChange={setEditing}
        onCancel={() => setEditing(null)}
        onSave={save}
      />
    );
  }

  const tickets = rows.filter((r) => r.kind === 'ticket');
  const invoices = rows.filter((r) => r.kind === 'invoice');

  return (
    <Card>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-vz-ink">
            Tickets & Factures
          </h2>
          <p className="text-sm text-vz-ink-mute">
            Mise en forme du ticket de caisse imprimé et de la facture PDF
            (zones, champs, mentions légales, couleur), avec aperçu en direct.
            Le mail d&apos;envoi de facture est paramétrable.
          </p>
        </div>
        <Button onClick={() => setEditing({ ...EMPTY_DRAFT })}>Nouveau template</Button>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-vz-ink-mute">Chargement…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Section
            title="Tickets de caisse (B2C)"
            templates={tickets}
            onEdit={(t) => setEditing(toDraft(t))}
            onSetDefault={setDefault}
            onDeactivate={deactivate}
          />
          <Section
            title="Factures (B2B)"
            templates={invoices}
            onEdit={(t) => setEditing(toDraft(t))}
            onSetDefault={setDefault}
            onDeactivate={deactivate}
          />
        </div>
      )}
    </Card>
  );
}

function StudioEditor({
  draft,
  busy,
  onChange,
  onCancel,
  onSave,
}: {
  draft: Draft;
  busy: boolean;
  onChange: (d: Draft) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  const set = (patch: Partial<Draft>): void => onChange({ ...draft, ...patch });
  const isInvoice = draft.kind === 'invoice';

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold text-vz-ink">
          {draft.id ? 'Modifier le template' : 'Nouveau template'}
        </h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>
            Annuler
          </Button>
          <Button onClick={onSave} disabled={busy}>
            {busy ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ---- Form ---- */}
        <div className="space-y-5">
          <FieldGroup title="Type & identification">
            <Field label="Nom (interne)" value={draft.name} onChange={(s) => set({ name: s })} />
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-vz-ink-soft">Type</span>
              <select
                value={draft.kind}
                onChange={(e) => set({ kind: e.target.value as ReceiptKind })}
                className="w-full rounded-lg border border-vz-line bg-vz-surface px-3 py-2 text-sm"
              >
                <option value="ticket">Ticket de caisse (B2C)</option>
                <option value="invoice">Facture (B2B, PDF)</option>
              </select>
            </label>
          </FieldGroup>

          <FieldGroup title="Contenu">
            <Field label="Titre imprimé" value={draft.title} onChange={(s) => set({ title: s })} />
            {isInvoice && (
              <Field
                label="Note d'introduction (au-dessus des articles)"
                value={draft.header_note}
                onChange={(s) => set({ header_note: s })}
                multiline
              />
            )}
            <Field label="Footer" value={draft.footer} onChange={(s) => set({ footer: s })} multiline />
            <Field
              label="Conditions de retour"
              value={draft.conditions_retour}
              onChange={(s) => set({ conditions_retour: s })}
              multiline
            />
          </FieldGroup>

          <FieldGroup title="Présentation & zones">
            {isInvoice && (
              <label className="flex items-center gap-3">
                <input
                  type="color"
                  value={draft.accent_color}
                  onChange={(e) => set({ accent_color: e.target.value })}
                  className="h-9 w-12 rounded border border-vz-line"
                />
                <span className="text-sm text-vz-ink-soft">Couleur d&apos;accent</span>
              </label>
            )}
            <Toggle
              label="Détail TVA"
              hint="Affiche la ventilation par taux"
              value={draft.show_tva_breakdown}
              onChange={(v) => set({ show_tva_breakdown: v })}
            />
            {!isInvoice && (
              <Toggle
                label="Bloc fidélité"
                hint="Solde + points gagnés sur le ticket"
                value={draft.show_loyalty_footer}
                onChange={(v) => set({ show_loyalty_footer: v })}
              />
            )}
            {isInvoice && (
              <>
                <Toggle
                  label="Bloc règlement (IBAN, termes)"
                  value={draft.show_payment_block}
                  onChange={(v) => set({ show_payment_block: v })}
                />
                <Toggle
                  label="Mentions légales"
                  value={draft.show_legal_mentions}
                  onChange={(v) => set({ show_legal_mentions: v })}
                />
              </>
            )}
            <Toggle
              label="Actif"
              hint="Les inactifs ne sont pas proposés au POS"
              value={draft.is_active}
              onChange={(v) => set({ is_active: v })}
            />
          </FieldGroup>

          {isInvoice && (
            <FieldGroup title="Mentions légales & paiement">
              <Field
                label="Conditions de paiement"
                value={draft.payment_terms}
                onChange={(s) => set({ payment_terms: s })}
                multiline
              />
              <Field
                label="Mentions légales (pénalités, escompte, médiation…)"
                value={draft.legal_mentions}
                onChange={(s) => set({ legal_mentions: s })}
                multiline
              />
              <p className="text-xs text-vz-ink-mute">
                Les coordonnées vendeur (SIRET, RCS, TVA intracom., IBAN…) se
                règlent dans l&apos;onglet « Boutique ».
              </p>
            </FieldGroup>
          )}

          {isInvoice && (
            <FieldGroup title="Email d'envoi de la facture">
              <Field
                label="Objet"
                value={draft.email_subject}
                onChange={(s) => set({ email_subject: s })}
              />
              <Field
                label="Corps du message"
                value={draft.email_body}
                onChange={(s) => set({ email_body: s })}
                multiline
              />
              <p className="text-xs text-vz-ink-mute">
                Variables : <code>{'{invoice_number}'}</code>{' '}
                <code>{'{company}'}</code> <code>{'{total_ttc}'}</code>{' '}
                <code>{'{date}'}</code> <code>{'{shop_name}'}</code>. Le PDF est
                joint automatiquement.
              </p>
            </FieldGroup>
          )}
        </div>

        {/* ---- Live preview ---- */}
        <div className="lg:sticky lg:top-4 lg:self-start">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-vz-ink-mute">
            Aperçu en direct
          </p>
          {isInvoice ? <InvoicePreview draft={draft} /> : <TicketPreview draft={draft} />}
        </div>
      </div>
    </Card>
  );
}

function InvoicePreview({ draft }: { draft: Draft }) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const lastUrl = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(async () => {
      setLoading(true);
      setFailed(false);
      try {
        const res = await api.post(
          '/api/admin/receipt-templates/preview-invoice.pdf',
          draftToBody(draft),
        );
        if (!res.ok) throw new Error('preview failed');
        const blob = await res.blob();
        if (cancelled) return;
        const next = URL.createObjectURL(blob);
        if (lastUrl.current) URL.revokeObjectURL(lastUrl.current);
        lastUrl.current = next;
        setUrl(next);
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(draftToBody(draft))]);

  useEffect(() => () => {
    if (lastUrl.current) URL.revokeObjectURL(lastUrl.current);
  }, []);

  return (
    <div className="rounded-xl border border-vz-line bg-vz-bg-alt/40 p-2">
      {failed ? (
        <p className="p-6 text-center text-sm text-vz-accent">
          Aperçu indisponible.
        </p>
      ) : url ? (
        <iframe
          title="Aperçu facture"
          src={url}
          className="h-[640px] w-full rounded-lg bg-white"
        />
      ) : (
        <p className="p-6 text-center text-sm text-vz-ink-mute">
          {loading ? 'Génération de l’aperçu…' : 'Aperçu en cours…'}
        </p>
      )}
      {loading && url && (
        <p className="pt-1 text-center text-[11px] text-vz-ink-mute">
          Mise à jour…
        </p>
      )}
    </div>
  );
}

function TicketPreview({ draft }: { draft: Draft }) {
  const sep = '------------------------------------------';
  const lines: string[] = [];
  lines.push(center(draft.title || 'VINTIZ', 42));
  lines.push(center('6 rue Saint-Jacques, 27200 Vernon', 42));
  lines.push(sep);
  if (draft.header_note) lines.push(draft.header_note);
  lines.push('Ticket #1042            ' + new Date().toLocaleDateString('fr-FR'));
  lines.push(sep);
  lines.push('Robe Sézane            1 x  49.00      49.00');
  lines.push('Sac boutique Vintiz    1 x   0.25       0.25');
  lines.push(sep);
  if (draft.show_tva_breakdown) {
    lines.push(rightCol('Total HT', '41.04'));
    lines.push(rightCol('TVA 20%', '8.21'));
  }
  lines.push(rightCol('TOTAL TTC', '49.25'));
  lines.push(rightCol('CB', '49.25'));
  lines.push(sep);
  if (draft.show_loyalty_footer) {
    lines.push('Fidélité : +49 pts — solde 312 pts');
    lines.push(sep);
  }
  if (draft.footer) lines.push(...draft.footer.split('\n'));
  if (draft.conditions_retour) {
    lines.push('');
    lines.push(...draft.conditions_retour.split('\n'));
  }

  return (
    <div className="rounded-xl border border-vz-line bg-white p-4">
      <pre className="mx-auto max-w-[24rem] whitespace-pre-wrap break-words font-mono text-[11px] leading-snug text-vz-ink">
        {lines.join('\n')}
      </pre>
    </div>
  );
}

function center(s: string, width: number): string {
  if (s.length >= width) return s;
  const pad = Math.floor((width - s.length) / 2);
  return ' '.repeat(pad) + s;
}

function rightCol(label: string, value: string): string {
  const width = 42;
  const left = label;
  const right = value;
  const space = Math.max(1, width - left.length - right.length);
  return left + ' '.repeat(space) + right;
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
            <li key={t.id} className="rounded-xl border border-vz-line bg-vz-surface p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {t.kind === 'invoice' && (
                      <span
                        className="inline-block h-3 w-3 flex-shrink-0 rounded-full border border-vz-line"
                        style={{ backgroundColor: t.accent_color || '#0B7A6A' }}
                      />
                    )}
                    <span className="truncate text-sm font-semibold text-vz-ink">{t.name}</span>
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
                  <div className="text-xs text-vz-ink-mute">Titre : {t.title}</div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <button type="button" onClick={() => onEdit(t)} className="text-xs text-vz-teal underline">
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

function FieldGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-vz-line bg-vz-bg-alt/30 p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-vz-ink-mute">
        {title}
      </h4>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-vz-ink-soft">{label}</span>
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
