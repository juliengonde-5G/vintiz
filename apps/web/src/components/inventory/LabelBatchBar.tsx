'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface PrinterStatus {
  online: boolean;
  ip: string;
  port: number;
  latency_ms: number | null;
  enabled: boolean;
  detail: string | null;
  model: string;
}

interface LabelBatchBarProps {
  selectedIds: string[];
  onCleared: () => void;
  onToast: (message: string, kind?: 'success' | 'error') => void;
}

const POLL_INTERVAL_MS = 30_000;

/**
 * Sticky bar shown at the bottom of the inventory page whenever ≥1
 * product is checked. Displays the selection count, a printer
 * online/offline pill (auto-refreshed every 30 s) and a primary
 * action to send the whole batch to the Zebra.
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
        if (res.ok) {
          setStatus(await res.json());
        }
      } catch {
        if (!cancelled) setStatus((prev) => prev ?? { online: false, ip: '', port: 0, latency_ms: null, enabled: false, detail: 'Réseau', model: 'Zebra ZD421d' });
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (selectedIds.length === 0) return null;

  const printable = status?.online && status?.enabled;

  const handleA4Sheet = () => {
    // Mode dégradé : ouvre une planche A4 imprimable dans un nouvel
    // onglet. window.print() se déclenche tout seul côté serveur.
    const qs = new URLSearchParams({ ids: selectedIds.join(',') });
    window.open(`/api/labels/sheet?${qs.toString()}`, '_blank', 'noopener');
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
        const printed = (body.printed as number) ?? 0;
        const failed = (body.failed as number) ?? 0;
        if (failed === 0) {
          onToast(`${printed} étiquette${printed > 1 ? 's' : ''} envoyée${printed > 1 ? 's' : ''} à l'imprimante`, 'success');
          onCleared();
        } else {
          onToast(`${printed} OK, ${failed} échec${failed > 1 ? 's' : ''} — vérifiez la console`, 'error');
        }
      } else {
        onToast((body.detail as string) || 'Échec de l\'envoi à l\'imprimante', 'error');
      }
    } catch {
      onToast('Erreur réseau — imprimante injoignable', 'error');
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
          disabled={sending || !printable}
          onClick={handleBatch}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            sending || !printable
              ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
              : 'bg-vz-teal text-white hover:bg-vz-teal-deep'
          }`}
          title={!printable ? 'Imprimante hors ligne ou désactivée' : undefined}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 6 2 18 2 18 9" />
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
            <rect x="6" y="14" width="12" height="8" />
          </svg>
          {sending ? 'Envoi…' : `Imprimer Zebra (${selectedIds.length})`}
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
  const ok = status.online && status.enabled;
  const dotClass = ok ? 'bg-green-500' : 'bg-red-500';
  const labelText = ok
    ? `${status.model} • ${status.ip}${status.latency_ms != null ? ` (${status.latency_ms} ms)` : ''}`
    : status.enabled
      ? `Imprimante hors ligne (${status.ip || 'IP ?'})`
      : 'Imprimante désactivée';
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-vz-ink-soft" title={status.detail ?? undefined}>
      <span className={`w-2 h-2 rounded-full ${dotClass}`} />
      {labelText}
    </span>
  );
}
