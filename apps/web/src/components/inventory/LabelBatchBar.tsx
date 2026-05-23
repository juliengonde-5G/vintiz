'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface PrinterStatus {
  enabled: boolean;
  agent_configured: boolean;
  online: boolean;
  last_seen: string | null;
  pending: number;
  printing: number;
  errors: number;
  model: string;
  cups_printer_name?: string;
}

interface LabelBatchBarProps {
  selectedIds: string[];
  onCleared: () => void;
  onToast: (message: string, kind?: 'success' | 'error') => void;
}

const POLL_INTERVAL_MS = 30_000;

/**
 * Sticky bar shown at the bottom of the inventory page whenever ≥1 product is
 * checked. Shows the selection count, the Raspberry Pi agent status pill
 * (online + queue depth, auto-refreshed every 30 s) and a primary action that
 * queues the whole batch for the in-store Pi to print.
 */
export default function LabelBatchBar({ selectedIds, onCleared, onToast }: LabelBatchBarProps) {
  const [status, setStatus] = useState<PrinterStatus | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await api.get('/api/labels/printer/status');
        if (cancelled) return;
        if (res.ok) setStatus(await res.json());
      } catch {
        if (!cancelled) {
          setStatus((prev) => prev ?? {
            enabled: false, agent_configured: false, online: false, last_seen: null,
            pending: 0, printing: 0, errors: 0, model: 'Raspberry Pi · CUPS',
          });
        }
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (selectedIds.length === 0) return null;

  // Queuing is allowed as soon as the label printer is enabled — the Pi prints
  // asynchronously, so we don't gate on it being online right now.
  const queueable = Boolean(status?.enabled);

  const handleA4Sheet = async () => {
    // Mode dégradé : récupère la planche A4 via fetch (avec le JWT manager
    // dans l'Authorization header) puis ouvre le HTML dans un nouvel onglet
    // via une blob URL. window.open(url) direct ne joint pas le header d'auth.
    try {
      const qs = new URLSearchParams({ ids: selectedIds.join(',') });
      const res = await api.get(`/api/labels/sheet?${qs.toString()}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({} as Record<string, unknown>));
        onToast((body.detail as string) || 'Impossible de générer la planche A4', 'error');
        return;
      }
      const html = await res.text();
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      onToast('Erreur réseau — planche A4', 'error');
    }
  };

  const handleBatch = async () => {
    setSending(true);
    try {
      const res = await api.post('/api/labels/print/batch', {
        product_ids: selectedIds,
        copies: 1,
      });
      const body = await res.json().catch(() => ({} as Record<string, unknown>));
      if (res.ok) {
        const queued = (body.queued as number) ?? 0;
        const failed = (body.failed as number) ?? 0;
        if (failed === 0) {
          onToast(`${queued} étiquette${queued > 1 ? 's' : ''} en file d'impression`, 'success');
          onCleared();
        } else {
          onToast(`${queued} en file, ${failed} échec${failed > 1 ? 's' : ''}`, 'error');
        }
      } else {
        onToast((body.detail as string) || "Échec de la mise en file", 'error');
      }
    } catch {
      onToast('Erreur réseau — serveur injoignable', 'error');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 md:left-[calc(50%+8rem)] w-[calc(100vw-2rem)] max-w-2xl">
      <div className="bg-white border border-vz-line rounded-2xl shadow-lg px-4 py-3 flex items-center gap-3 flex-wrap">
        <span className="text-sm font-medium text-vz-ink">
          {selectedIds.length} produit{selectedIds.length > 1 ? 's' : ''} sélectionné{selectedIds.length > 1 ? 's' : ''}
        </span>
        <button
          onClick={onCleared}
          className="text-xs text-vz-ink-mute hover:text-vz-ink underline underline-offset-2"
        >
          Tout désélectionner
        </button>

        <div className="flex-1" />

        <PrinterPill status={status} />

        <button
          type="button"
          onClick={handleA4Sheet}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium border border-vz-line text-vz-ink-soft hover:bg-vz-bg-alt transition-colors"
          title="Mode dégradé : planche A4 sur imprimante classique"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="4" y="3" width="16" height="18" rx="2" />
            <line x1="8" y1="8" x2="16" y2="8" />
            <line x1="8" y1="12" x2="16" y2="12" />
            <line x1="8" y1="16" x2="12" y2="16" />
          </svg>
          Planche A4
        </button>

        <button
          type="button"
          disabled={sending || !queueable}
          onClick={handleBatch}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            sending || !queueable
              ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
              : 'bg-vz-teal text-white hover:bg-vz-teal-deep'
          }`}
          title={!queueable ? 'Imprimante étiquettes désactivée dans les paramètres' : undefined}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 6 2 18 2 18 9" />
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
            <rect x="6" y="14" width="12" height="8" />
          </svg>
          {sending ? 'Envoi…' : `Imprimer (${selectedIds.length})`}
        </button>
      </div>
    </div>
  );
}

function PrinterPill({ status }: { status: PrinterStatus | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-vz-ink-mute">
        <span className="w-2 h-2 rounded-full bg-gray-300 animate-pulse" />
        Vérification…
      </span>
    );
  }
  const dotClass = !status.enabled
    ? 'bg-gray-400'
    : status.online
      ? 'bg-green-500'
      : 'bg-amber-500';

  let labelText: string;
  if (!status.enabled) {
    labelText = 'Imprimante désactivée';
  } else if (!status.agent_configured) {
    labelText = 'Agent Pi non configuré';
  } else {
    const queue = status.pending + status.printing;
    const queueText = queue > 0 ? ` • ${queue} en file` : '';
    labelText = status.online
      ? `Raspberry Pi en ligne${queueText}`
      : `Agent Pi hors ligne${queueText}`;
  }
  const title = status.last_seen ? `Dernier contact : ${new Date(status.last_seen).toLocaleString('fr-FR')}` : undefined;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-vz-ink-soft" title={title}>
      <span className={`w-2 h-2 rounded-full ${dotClass}`} />
      {labelText}
    </span>
  );
}
