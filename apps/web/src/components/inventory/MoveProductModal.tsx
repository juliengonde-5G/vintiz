'use client';

/**
 * Modal de mouvement de stock depuis la fiche produit.
 *
 * Trois actions (déclenchées par les 3 boutons de la fiche) :
 *
 *  - ``place``  : Mettre en rayon — pioche la zone suggérée par l'IA
 *                 (``GET /products/:id/suggest-zone``), opérateur confirme
 *                 ou change. Exécute ``to_status=displayed`` + ``to_zone_id``.
 *  - ``move``   : Déplacer (changer de zone) — sélecteur de zone seul,
 *                 statut inchangé. Mêmes endpoints que l'aménagement hebdo.
 *  - ``reserve``: Mettre en réserve — pas de zone à choisir ; envoie
 *                 ``to_status=stock``. Le backend efface ``zone_id`` au
 *                 transit vers la réserve.
 *
 * Tous les chemins passent par ``POST /inventory/movements/execute`` (même
 * pipeline que la page Mouvements de stock) — historisation cohérente.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

export type MoveAction = 'place' | 'move' | 'reserve';

interface Suggestion {
  primary_zone_id: string | null;
  primary_zone_name: string | null;
  alternative_zone_id: string | null;
  alternative_zone_name: string | null;
  rationale: string | null;
}

interface MoveProductModalProps {
  open: boolean;
  action: MoveAction;
  productId: string;
  productBarcode: string;
  productName: string;
  currentZoneId: string | null;
  onClose: () => void;
  /** Re-fetch product + score + history après mouvement. */
  onApplied: () => void;
}

const TITLES: Record<MoveAction, string> = {
  place: 'Mettre en rayon',
  move: 'Déplacer dans une autre zone',
  reserve: 'Renvoyer en réserve',
};

const CTA: Record<MoveAction, string> = {
  place: 'Placer en rayon',
  move: 'Déplacer',
  reserve: 'Mettre en réserve',
};

export default function MoveProductModal({
  open,
  action,
  productId,
  productBarcode,
  productName,
  currentZoneId,
  onClose,
  onApplied,
}: MoveProductModalProps) {
  const needsZone = action !== 'reserve';

  const [zones, setZones] = useState<{ id: string; name: string }[]>([]);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [loadingSuggestion, setLoadingSuggestion] = useState(false);
  const [chosenZoneId, setChosenZoneId] = useState<string>('');
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState('');

  // Charge zones + suggestion à chaque ouverture (le placement IA peut
  // évoluer si on rouvre après une vente).
  useEffect(() => {
    if (!open || !needsZone) {
      setSuggestion(null);
      setChosenZoneId('');
      setError('');
      return;
    }
    setError('');
    let active = true;
    (async () => {
      try {
        const zRes = await api.get('/api/admin/zones');
        if (active && zRes.ok) {
          const data = await zRes.json();
          const list = Array.isArray(data) ? data : data.zones || [];
          setZones(list.map((z: { id: string; name: string }) => ({ id: z.id, name: z.name })));
        }
      } catch { /* zones best-effort */ }
      if (action === 'place') {
        setLoadingSuggestion(true);
        try {
          const sRes = await api.get(`/api/inventory/products/${productId}/suggest-zone`);
          if (active && sRes.ok) {
            const sug = (await sRes.json()) as Suggestion;
            setSuggestion(sug);
            setChosenZoneId(sug.primary_zone_id || '');
          }
        } catch { /* silent */ }
        if (active) setLoadingSuggestion(false);
      } else if (action === 'move') {
        // Préselection : zone actuelle (l'opérateur n'a qu'à choisir la cible).
        setChosenZoneId('');
      }
    })();
    return () => {
      active = false;
    };
  }, [open, action, productId, needsZone]);

  const handleSubmit = useCallback(async () => {
    if (needsZone && !chosenZoneId) {
      setError('Choisissez une zone d’implantation.');
      return;
    }
    setExecuting(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        barcode: productBarcode,
        reason:
          action === 'place'
            ? 'Mise en rayon (fiche produit)'
            : action === 'move'
              ? 'Changement de zone (fiche produit)'
              : 'Retour en réserve (fiche produit)',
      };
      if (action === 'place') {
        body.to_status = 'displayed';
        body.to_zone_id = chosenZoneId;
      } else if (action === 'move') {
        body.to_zone_id = chosenZoneId;
      } else {
        body.to_status = 'stock';
      }
      const res = await api.post('/api/inventory/movements/execute', body);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError((data && data.detail) || 'Mouvement refusé.');
        return;
      }
      onApplied();
      onClose();
    } catch {
      setError('Erreur réseau pendant le mouvement.');
    } finally {
      setExecuting(false);
    }
  }, [action, chosenZoneId, needsZone, onApplied, onClose, productBarcode]);

  if (!open) return null;

  return (
    <Modal open={open} onClose={onClose} title={TITLES[action]}>
      <div className="space-y-4">
        <p className="text-sm text-vz-ink-soft">
          <strong>{productName}</strong>
          <span className="block text-xs text-gray-400 font-mono mt-0.5">{productBarcode}</span>
        </p>

        {action === 'reserve' && (
          <p className="text-sm text-gray-600">
            La pièce sera retirée du rayon et placée en réserve. La zone
            actuelle sera libérée.
          </p>
        )}

        {needsZone && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Zone d&apos;implantation
              {action === 'place' && loadingSuggestion && (
                <span className="text-gray-400 font-normal"> (suggestion IA…)</span>
              )}
            </label>
            <select
              value={chosenZoneId}
              onChange={(e) => setChosenZoneId(e.target.value)}
              className="w-full min-h-[48px] px-3 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
            >
              <option value="">— Choisir une zone —</option>
              {zones
                .filter((z) => action !== 'move' || z.id !== currentZoneId)
                .map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.name}
                  </option>
                ))}
            </select>
            {action === 'place' && suggestion?.primary_zone_name && (
              <p className="mt-1.5 text-xs text-vz-teal-deep">
                💡 Suggéré : <strong>{suggestion.primary_zone_name}</strong>
                {suggestion.rationale ? ` — ${suggestion.rationale}` : ''}
              </p>
            )}
            {action === 'place' &&
              suggestion?.alternative_zone_id &&
              suggestion.alternative_zone_id !== chosenZoneId && (
                <button
                  type="button"
                  onClick={() =>
                    setChosenZoneId(suggestion.alternative_zone_id || '')
                  }
                  className="mt-1 text-xs text-gray-500 underline"
                >
                  Alternative : {suggestion.alternative_zone_name}
                </button>
              )}
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
        )}

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={executing}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={executing}>
            {executing ? 'Mouvement…' : CTA[action]}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
