'use client';

import React, { useCallback, useEffect, useState } from 'react';

import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface Exchange {
  id: string;
  created_at: string | null;
  operation: string;
  method: string;
  url: string | null;
  http_status: number | null;
  ok: boolean;
  latency_ms: number | null;
  mode: string | null;
  checkout_id: string | null;
  reader_id: string | null;
  foreign_transaction_id: string | null;
  request_summary: string | null;
  response_summary: string | null;
  error: string | null;
  environment: string | null;
}

interface Summary {
  reader_pushes: number;
  link_checkouts: number;
  failures: number;
}

// Human labels for the logical operations recorded by the backend.
const OP_LABEL: Record<string, string> = {
  create_checkout: 'Création checkout',
  reader_push: 'Envoi au TPE',
  get_status: 'Statut checkout',
  reader_status: 'Statut TPE',
  cancel_peek: 'Annulation (vérif)',
  cancel_delete: 'Annulation',
  terminate: 'Arrêt TPE',
  refund: 'Remboursement',
  ping: 'Ping TPE',
  ping_status: 'Ping TPE (live)',
  sync: 'Sync terminaux',
  get_transaction: 'Lecture transaction',
  receipt: 'Reçu SumUp',
};

function formatDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return (
    d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) +
    ' ' +
    d.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  );
}

/**
 * Journal des échanges HTTP avec les serveurs SumUp — surfacé dans
 * /settings &gt; Système.
 *
 * Source de vérité côté serveur pour diagnostiquer « les transactions ne
 * passent plus vers le TPE » : chaque appel à api.sumup.com est tracé
 * (payload rédigé, aucun secret). Une ligne « Création checkout » en mode
 * **lien** = le paiement a été créé sans cibler de terminal → le Solo n'a
 * pas sonné. Le bandeau d'alerte le signale explicitement.
 */
export default function SumUpExchangeLogPanel() {
  const [rows, setRows] = useState<Exchange[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (onlyFailed) params.set('only_failed', 'true');
      params.set('limit', '150');
      const res = await api.get(`/api/admin/sumup-exchanges?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setRows(data.exchanges || []);
        setSummary(data.summary || null);
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement du journal.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [onlyFailed]);

  useEffect(() => {
    load();
  }, [load]);

  const clearLog = async (): Promise<void> => {
    if (!window.confirm('Vider le journal des échanges SumUp ?')) return;
    setBusy(true);
    try {
      const res = await api.delete('/api/admin/sumup-exchanges');
      if (res.ok) await load();
      else setError('Suppression refusée.');
    } catch {
      setError('Erreur réseau.');
    }
    setBusy(false);
  };

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold text-vz-ink">
            Journal des échanges SumUp
          </h2>
          <p className="max-w-2xl text-sm text-vz-ink-mute">
            Trace serveur de chaque appel à api.sumup.com (création de paiement,
            envoi au TPE, statut, annulation, remboursement, ping). Payloads
            rédigés — aucun secret ni numéro de carte n’est stocké. À utiliser
            pour comprendre pourquoi un paiement CB n’aboutit pas vers le
            terminal.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 text-sm text-vz-ink-soft">
            <input
              type="checkbox"
              checked={onlyFailed}
              onChange={(e) => setOnlyFailed(e.target.checked)}
              className="h-4 w-4 accent-vz-teal"
            />
            Échecs uniquement
          </label>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            Rafraîchir
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || rows.length === 0}
            onClick={() => void clearLog()}
          >
            Vider
          </Button>
        </div>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
          {error}
        </p>
      )}

      {summary && (summary.link_checkouts > 0) && (
        <div className="mb-3 rounded-lg border border-vz-accent bg-vz-accent-soft px-4 py-3 text-sm text-vz-ink">
          <strong>{summary.link_checkouts}</strong> paiement(s) créé(s) en mode{' '}
          <strong>lien</strong> sur la période affichée — le TPE Solo n’a pas
          sonné. Déclarez un terminal <strong>par défaut</strong> dans
          Paramètres › Caisse (ou renseignez <code>SUMUP_READER_ID</code>) pour
          que les paiements soient poussés sur le terminal.
        </div>
      )}

      {summary && (
        <div className="mb-4 flex flex-wrap gap-2">
          <SummaryChip label="Envois TPE" value={summary.reader_pushes} tone="ok" />
          <SummaryChip
            label="Créés en lien"
            value={summary.link_checkouts}
            tone={summary.link_checkouts > 0 ? 'alert' : 'neutral'}
          />
          <SummaryChip
            label="Échecs"
            value={summary.failures}
            tone={summary.failures > 0 ? 'alert' : 'neutral'}
          />
        </div>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-vz-ink-mute">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-lg bg-vz-bg-alt px-3 py-4 text-sm text-vz-ink-mute">
          Aucun échange enregistré. Le journal se remplit dès qu’un paiement CB
          est tenté à la caisse (ou qu’un TPE est testé).
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={r.id}
              className="rounded-xl border border-vz-line bg-vz-surface p-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <StatusDot ok={r.ok} />
                <span className="font-medium text-vz-ink">
                  {OP_LABEL[r.operation] || r.operation}
                </span>
                <span className="rounded bg-vz-bg-alt px-1.5 py-0.5 font-mono text-xs text-vz-ink-soft">
                  {r.method}
                </span>
                {r.mode && <ModeBadge mode={r.mode} />}
                <span
                  className={`font-mono text-xs ${
                    r.ok ? 'text-vz-teal-deep' : 'text-vz-accent'
                  }`}
                >
                  {r.error ? 'réseau KO' : r.http_status ?? '—'}
                </span>
                {r.latency_ms != null && (
                  <span className="font-mono text-xs text-vz-ink-mute">
                    {r.latency_ms} ms
                  </span>
                )}
                <span className="ml-auto font-mono text-xs text-vz-ink-mute">
                  {formatDate(r.created_at)}
                </span>
              </div>

              {(r.checkout_id || r.reader_id) && (
                <div className="mt-1 flex flex-wrap gap-x-4 font-mono text-[11px] text-vz-ink-mute">
                  {r.checkout_id && <span>checkout: {r.checkout_id}</span>}
                  {r.reader_id && <span>reader: {r.reader_id}</span>}
                </div>
              )}

              {r.error && (
                <p className="mt-1 break-words font-mono text-xs text-vz-accent">
                  {r.error}
                </p>
              )}
              {r.request_summary && (
                <p className="mt-1 break-words font-mono text-[11px] text-vz-ink-mute">
                  → {r.request_summary}
                </p>
              )}
              {r.response_summary && (
                <p className="mt-0.5 break-words font-mono text-[11px] text-vz-ink-soft">
                  ← {r.response_summary}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SummaryChip({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'ok' | 'alert' | 'neutral';
}) {
  const cls =
    tone === 'ok'
      ? 'bg-vz-teal-soft text-vz-teal-deep'
      : tone === 'alert'
        ? 'bg-vz-accent-soft text-vz-ink'
        : 'bg-vz-bg-alt text-vz-ink-soft';
  return (
    <span className={`rounded-lg px-3 py-1.5 text-xs font-medium ${cls}`}>
      {label} : <span className="font-mono font-bold">{value}</span>
    </span>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  const isReader = mode === 'reader';
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
        isReader
          ? 'bg-vz-teal-soft text-vz-teal-deep'
          : 'bg-vz-gold/15 text-vz-gold'
      }`}
      title={
        isReader
          ? 'Poussé vers le terminal Solo'
          : 'Mode lien — le terminal Solo ne sonne pas'
      }
    >
      {isReader ? 'TPE' : 'lien'}
    </span>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${
        ok ? 'bg-vz-teal' : 'bg-vz-accent'
      }`}
      aria-hidden="true"
    />
  );
}
