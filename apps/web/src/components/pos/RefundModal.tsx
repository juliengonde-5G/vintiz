'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';
import { isIOS } from '@/lib/platform';

interface TransactionItem {
  id: string;
  name: string;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  line_total: number;
}

interface TransactionDetail {
  id: string;
  transaction_number: number;
  type: string;
  total_ttc: number;
  client: { id: string; first_name: string; last_name: string } | null;
  items: TransactionItem[];
}

interface RefundModalProps {
  open: boolean;
  transactionId: string | null;
  onClose: () => void;
  onCompleted?: () => void;
}

type RefundMethod = 'cash' | 'card' | 'cheque' | 'avoir';

const METHODS: { value: RefundMethod; label: string; needsClient: boolean }[] = [
  { value: 'cash', label: 'Espèces', needsClient: false },
  { value: 'card', label: 'Carte', needsClient: false },
  { value: 'cheque', label: 'Chèque', needsClient: false },
  { value: 'avoir', label: 'Avoir (store credit)', needsClient: true },
];


export default function RefundModal({
  open, transactionId, onClose, onCompleted,
}: RefundModalProps) {
  const [tx, setTx] = useState<TransactionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [method, setMethod] = useState<RefundMethod>('cash');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [refundTxId, setRefundTxId] = useState<string | null>(null);
  const [printing, setPrinting] = useState(false);

  const reset = useCallback(() => {
    setTx(null);
    setQuantities({});
    setRefundTxId(null);
    setPrinting(false);
    setMethod('cash');
    setReason('');
    setError('');
    setDone(false);
  }, []);

  useEffect(() => {
    if (!open || !transactionId) { reset(); return; }
    setLoading(true);
    setError('');
    api.get(`/api/pos/transactions/${transactionId}`)
      .then(async (res) => {
        if (!res.ok) {
          setError('Transaction introuvable');
          return;
        }
        const data: TransactionDetail = await res.json();
        setTx(data);
        // Preselect: 0 for everyone (manager picks)
        setQuantities(Object.fromEntries(data.items.map(i => [i.id, 0])));
      })
      .catch(() => setError('Erreur de chargement'))
      .finally(() => setLoading(false));
  }, [open, transactionId, reset]);

  const refundTotal = tx?.items.reduce((sum, it) => {
    const qty = quantities[it.id] || 0;
    if (qty <= 0) return sum;
    const unitAfterDiscount = it.unit_price * (1 - it.discount_percent / 100);
    return sum + unitAfterDiscount * qty;
  }, 0) || 0;

  const hasSelection = Object.values(quantities).some(q => q > 0);
  const methodMeta = METHODS.find(m => m.value === method);
  const needsClientButMissing = methodMeta?.needsClient && !tx?.client;

  const submit = async () => {
    if (!tx) return;
    setSubmitting(true);
    setError('');
    try {
      const items = tx.items
        .filter(it => (quantities[it.id] || 0) > 0)
        .map(it => ({ transaction_item_id: it.id, quantity: quantities[it.id] }));
      const res = await api.post(`/api/pos/transactions/${tx.id}/refund`, {
        items,
        refund_method: method,
        reason: reason || null,
      });
      if (res.ok) {
        const body = await res.json().catch(() => null);
        setRefundTxId(body?.id || null);
        setDone(true);
        onCompleted?.();
      } else {
        const err = await res.json().catch(() => null);
        setError(err?.detail || 'Erreur lors du remboursement');
      }
    } catch {
      setError('Erreur réseau');
    }
    setSubmitting(false);
  };

  /**
   * Direct ESC/POS path — MUNBYN 047P-WiFi on port 9100. The only path
   * that works on Android (Lenovo Idea Tab Pro Gen 2) since Chrome's
   * window.print() falls back to "Print to PDF" without a system driver
   * for raw thermal printers.
   */
  const printRefundEscpos = useCallback(async () => {
    if (!refundTxId) return;
    setPrinting(true);
    try {
      const res = await api.post(`/api/pos/transactions/${refundTxId}/print`, {});
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        setError(err?.detail || 'Imprimante ESC/POS indisponible — vérifie l\'IP MUNBYN dans Réglages › Matériel');
      }
    } catch {
      setError('Erreur de connexion à l\'imprimante');
    }
    setPrinting(false);
  }, [refundTxId]);

  const printRefundReceipt = useCallback(async () => {
    if (!refundTxId) return;
    setPrinting(true);
    try {
      const res = await api.get(`/api/pos/transactions/${refundTxId}/receipt`);
      if (!res.ok) {
        setError('Impossible de générer le ticket de retour');
        setPrinting(false);
        return;
      }
      const data = await res.json();
      const text: string = data.receipt_text || data.text || '';
      const w = window.open('', '_blank', 'width=400,height=700');
      if (!w) {
        const browser = isIOS() ? 'Safari' : 'Chrome';
        alert(
          `Impossible d'ouvrir la fenêtre d'impression. Autorisez les pop-ups pour ce site dans les réglages ${browser}.`,
        );
        setPrinting(false);
        return;
      }
      const safe = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const logoUrl = `${window.location.origin}/receipt-logo.png`;
      w.document.write(`<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Ticket retour Vintiz</title>
<style>
  @page { size: 80mm auto; margin: 0; }
  body { margin: 0; padding: 4mm 3mm; }
  .logo { display: block; margin: 0 auto 3mm; width: 28mm; height: auto;
          filter: grayscale(1) contrast(10) brightness(0.9);
          -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  pre { font-family: 'Courier New', Consolas, monospace; font-size: 12px;
        line-height: 1.35; white-space: pre-wrap; word-break: break-word; margin: 0; }
  @media print { body { padding: 0 2mm; } }
</style></head>
<body>
<img class="logo" src="${logoUrl}" alt="Vintiz" onerror="this.style.display='none'">
<pre>${safe}</pre>
<script>
  (function() {
    var img = document.querySelector('.logo');
    var go = function() { window.focus(); window.print(); };
    if (!img || img.complete) { go(); }
    else { img.addEventListener('load', go); img.addEventListener('error', go); }
  })();
</script>
</body></html>`);
      w.document.close();
    } catch {
      setError('Erreur impression');
    }
    setPrinting(false);
  }, [refundTxId]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={tx ? `Remboursement #${tx.transaction_number}` : 'Remboursement'}
      actions={
        done ? (
          <>
            <Button variant="secondary" onClick={onClose}>
              Fermer sans ticket
            </Button>
            <Button
              onClick={printRefundEscpos}
              disabled={printing || !refundTxId}
            >
              {printing ? 'Impression…' : 'Imprimer (MUNBYN)'}
            </Button>
            {/* AirPrint fallback — uniquement iOS Safari (sur Android Chrome
                window.print() ne pilote pas la MUNBYN, donc inutile). */}
            {typeof window !== 'undefined' && isIOS() && (
              <Button
                variant="outline"
                onClick={printRefundReceipt}
                disabled={printing || !refundTxId}
              >
                Imprimer (AirPrint)
              </Button>
            )}
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose} disabled={submitting}>
              Annuler
            </Button>
            <Button
              onClick={submit}
              disabled={
                submitting || !hasSelection || refundTotal <= 0 || !!needsClientButMissing
              }
            >
              {submitting
                ? 'Traitement…'
                : `Rembourser ${formatCurrency(refundTotal)}`}
            </Button>
          </>
        )
      }
    >
      {loading && <div className="text-center text-gray-400 py-6">Chargement…</div>}
      {error && (
        <div className="mb-3 p-2 bg-red-50 text-red-700 rounded text-sm">{error}</div>
      )}

      {done && (
        <div className="p-3 bg-green-50 text-green-700 rounded text-sm">
          Remboursement enregistré. Le ticket de retour est généré et la chaîne
          NF525 mise à jour.
        </div>
      )}

      {tx && !done && (
        <div className="space-y-4">
          <div>
            <p className="text-sm text-gray-500">
              Total initial : <strong>{formatCurrency(tx.total_ttc)}</strong>
              {tx.client && (
                <> &mdash; Client : <strong>{tx.client.first_name} {tx.client.last_name}</strong></>
              )}
            </p>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-black mb-2">Articles à rembourser</h3>
            <div className="space-y-2">
              {tx.items.map(it => {
                const qty = quantities[it.id] || 0;
                return (
                  <div key={it.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{it.name}</p>
                      <p className="text-xs text-gray-500">
                        {formatCurrency(it.unit_price)}
                        {it.discount_percent > 0 && ` (-${it.discount_percent}%)`}
                        {' × '}{it.quantity}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setQuantities({ ...quantities, [it.id]: Math.max(0, qty - 1) })}
                        className="w-8 h-8 rounded border border-gray-200 hover:bg-gray-100"
                      >−</button>
                      <span className="w-8 text-center font-medium">{qty}</span>
                      <button
                        type="button"
                        onClick={() => setQuantities({ ...quantities, [it.id]: Math.min(it.quantity, qty + 1) })}
                        className="w-8 h-8 rounded border border-gray-200 hover:bg-gray-100"
                        disabled={qty >= it.quantity}
                      >+</button>
                      <span className="text-xs text-gray-400 w-10">/ {it.quantity}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-black mb-2">Méthode de remboursement</h3>
            <div className="grid grid-cols-2 gap-2">
              {METHODS.map(m => (
                <label
                  key={m.value}
                  className={`p-2 border rounded-lg cursor-pointer text-sm ${
                    method === m.value
                      ? 'border-vz-teal bg-vz-teal-soft/40'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="refund-method"
                    value={m.value}
                    checked={method === m.value}
                    onChange={() => setMethod(m.value)}
                    className="mr-2"
                  />
                  {m.label}
                </label>
              ))}
            </div>
            {needsClientButMissing && (
              <p className="text-xs text-red-600 mt-1">
                L&apos;avoir nécessite un client associé à la vente d&apos;origine.
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-semibold text-black mb-1">
              Motif (optionnel)
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="ex. Mauvaise taille, défaut visible…"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-vz-teal"
            />
          </div>
        </div>
      )}
    </Modal>
  );
}
