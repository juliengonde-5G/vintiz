'use client';

import React, { useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface RepriceMove {
  recommended: boolean;
  current_zone_id: string | null;
  current_zone_name: string | null;
  suggested_zone_id: string | null;
  suggested_zone_name: string | null;
  alternative_zone_name: string | null;
  should_go_to_window: boolean;
  rationale: string;
}

interface RepriceReference {
  has_reference: boolean;
  below: boolean;
  floor: number | null;
  bucket: 'standard' | 'premium' | string;
  note: string | null;
}

interface RepriceResult {
  old_price: number;
  new_price: number;
  price_changed: boolean;
  score: { total_score: number; action: string; action_color: string };
  move: RepriceMove;
  reference?: RepriceReference | null;
}

interface RepriceModalProps {
  open: boolean;
  onClose: () => void;
  productId: string;
  currentPrice: number;
  /** Re-fetch product + score + history after a price change or a move. */
  onApplied: () => void;
  /** Open the (existing) label modal so the operator prints the new price tag. */
  onPrintLabel: () => void;
}

const scoreColor = (s: number) =>
  s >= 70 ? 'text-green-600' : s >= 40 ? 'text-yellow-600' : 'text-red-600';

const actionBg = (c: string) =>
  c === 'green'
    ? 'bg-green-50 text-green-700 border-green-200'
    : c === 'yellow'
      ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
      : c === 'orange'
        ? 'bg-orange-50 text-orange-700 border-orange-200'
        : 'bg-red-50 text-red-700 border-red-200';

const fmtPrice = (n: number) => `${n.toFixed(2).replace('.', ',')} €`;

export default function RepriceModal({
  open,
  onClose,
  productId,
  currentPrice,
  onApplied,
  onPrintLabel,
}: RepriceModalProps) {
  const [step, setStep] = useState<'input' | 'result'>('input');
  const [price, setPrice] = useState<number>(currentPrice);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<RepriceResult | null>(null);
  const [applyingMove, setApplyingMove] = useState(false);
  const [moveApplied, setMoveApplied] = useState(false);

  // Reset everything each time the modal is (re)opened.
  useEffect(() => {
    if (open) {
      setStep('input');
      setPrice(currentPrice);
      setSubmitting(false);
      setError('');
      setResult(null);
      setApplyingMove(false);
      setMoveApplied(false);
    }
  }, [open, currentPrice]);

  const bump = (delta: number) =>
    setPrice((p) => Math.max(0, Math.round((Number(p || 0) + delta) * 100) / 100));

  const handleValidate = async () => {
    if (price == null || Number.isNaN(price) || price < 0) {
      setError('Prix invalide');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const res = await api.post(
        `/api/inventory/products/${productId}/reprice`,
        { new_price: Number(price) },
      );
      if (res.ok) {
        const data: RepriceResult = await res.json();
        setResult(data);
        setStep('result');
        // The price (+ its history entry) is now persisted — refresh the page.
        onApplied();
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Échec de la mise à jour du prix');
      }
    } catch {
      setError('Erreur réseau');
    }
    setSubmitting(false);
  };

  const handleApplyMove = async () => {
    if (!result?.move?.suggested_zone_id) return;
    setApplyingMove(true);
    setError('');
    try {
      const res = await api.put(`/api/inventory/products/${productId}`, {
        zone_id: result.move.suggested_zone_id,
      });
      if (res.ok) {
        setMoveApplied(true);
        // The zone move is now logged in the movement history — refresh.
        onApplied();
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Échec du déplacement');
      }
    } catch {
      setError('Erreur réseau');
    }
    setApplyingMove(false);
  };

  const handlePrint = () => {
    onClose();
    onPrintLabel();
  };

  return (
    <Modal open={open} onClose={onClose} title="Modifier le prix">
      {step === 'input' ? (
        <div className="space-y-5">
          <div>
            <p className="text-xs text-gray-500 mb-1">Prix de vente actuel</p>
            <p className="text-lg font-bold text-gray-700">
              {fmtPrice(Number(currentPrice || 0))}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-black mb-1.5">
              Nouveau prix (€)
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => bump(-0.5)}
                className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0"
                aria-label="Diminuer le prix"
              >
                −
              </button>
              <Input
                type="number"
                step="0.50"
                min="0"
                value={String(price ?? 0)}
                onChange={(e) => setPrice(parseFloat(e.target.value))}
                className="text-center font-bold text-lg"
                autoFocus
              />
              <button
                type="button"
                onClick={() => bump(0.5)}
                className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0"
                aria-label="Augmenter le prix"
              >
                +
              </button>
            </div>
          </div>

          {error && (
            <div className="p-2 bg-red-50 text-red-700 rounded text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button onClick={handleValidate} disabled={submitting}>
              {submitting ? 'Calcul de la note…' : 'Valider'}
            </Button>
          </div>
        </div>
      ) : (
        result && (
          <div className="space-y-5">
            {/* New price */}
            <div className="flex items-baseline gap-2">
              <span className="text-sm text-gray-500">Prix</span>
              {result.price_changed ? (
                <>
                  <span className="text-red-500 line-through">
                    {fmtPrice(result.old_price)}
                  </span>
                  <span className="text-gray-400">→</span>
                  <span className="text-xl font-bold text-vz-teal">
                    {fmtPrice(result.new_price)}
                  </span>
                </>
              ) : (
                <span className="text-xl font-bold text-vz-teal">
                  {fmtPrice(result.new_price)}{' '}
                  <span className="text-sm font-normal text-gray-400">
                    (inchangé)
                  </span>
                </span>
              )}
            </div>

            {/* Refreshed note */}
            <div className="flex items-start gap-4 p-3 rounded-lg bg-gray-50">
              <div className="text-center">
                <div
                  className={`text-3xl font-bold ${scoreColor(result.score.total_score)}`}
                >
                  {Math.round(result.score.total_score)}
                </div>
                <div className="text-[10px] text-gray-500">/ 100</div>
              </div>
              <div className="flex-1">
                <p className="text-xs text-gray-500 mb-1">Note actualisée</p>
                <div
                  className={`inline-block px-2.5 py-1 rounded-lg border text-xs font-medium ${actionBg(result.score.action_color)}`}
                >
                  {result.score.action}
                </div>
              </div>
            </div>

            {/* Reference-grid notification (non-blocking) */}
            {result.reference?.below && result.reference.floor != null && (
              <div role="alert" className="p-3 rounded-lg border border-amber-300 bg-amber-50">
                <p className="text-sm font-medium text-amber-800">⚠️ Prix sous la grille de référence</p>
                <p className="text-xs text-amber-700 mt-1">
                  Plancher {result.reference.bucket === 'premium' ? 'premium' : 'standard'} :{' '}
                  <strong>{fmtPrice(result.reference.floor)}</strong>.
                </p>
                {result.reference.note && (
                  <p className="text-[11px] text-amber-600 mt-1">{result.reference.note}</p>
                )}
              </div>
            )}

            {/* Move proposal */}
            {result.move.recommended ? (
              <div className="p-3 rounded-lg border border-vz-teal/30 bg-vz-teal-soft/40">
                <p className="text-sm font-medium text-vz-teal-deep mb-1">
                  Déplacement suggéré
                  {result.move.should_go_to_window ? ' (vitrine)' : ''}
                </p>
                <p className="text-sm text-gray-700 flex flex-wrap items-center gap-1 mb-1">
                  <span className="font-medium">
                    {result.move.current_zone_name || 'Sans zone'}
                  </span>
                  <span className="text-gray-400">→</span>
                  <span className="font-bold text-vz-teal-deep">
                    {result.move.suggested_zone_name}
                  </span>
                </p>
                <p className="text-xs text-gray-500 mb-2">
                  {result.move.rationale}
                </p>
                {moveApplied ? (
                  <p className="text-sm font-medium text-green-700">
                    ✓ Produit déplacé en {result.move.suggested_zone_name}
                  </p>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={handleApplyMove}
                    disabled={applyingMove}
                  >
                    {applyingMove ? 'Déplacement…' : 'Appliquer le déplacement'}
                  </Button>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Aucun déplacement nécessaire — la zone actuelle convient à la
                nouvelle note.
              </p>
            )}

            {error && (
              <div className="p-2 bg-red-50 text-red-700 rounded text-sm">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 flex-wrap">
              <Button variant="outline" onClick={onClose}>
                Terminé
              </Button>
              <Button variant="primary" onClick={handlePrint}>
                🏷 Imprimer la nouvelle étiquette
              </Button>
            </div>
          </div>
        )
      )}
    </Modal>
  );
}
