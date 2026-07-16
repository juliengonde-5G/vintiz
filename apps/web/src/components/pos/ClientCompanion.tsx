'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { mediaUrl } from '@/lib/format';

interface Suggestion {
  product_id: string;
  name: string;
  price_cents: number;
  photo_url: string | null;
  reason: string;
  size: string | null;
  color: string | null;
  zone_name: string | null;
  score: number;
}

// Unified payload for the mini product sheet (modal overlay) — used by both
// the complementary suggestions and the « Pépites du jour ».
interface PeekItem {
  product_id: string;
  name: string;
  price_cents: number;
  photo_url: string | null;
  zone_name: string | null;
  size: string | null;
  color: string | null;
  canAdd: boolean;
}

interface Pick {
  id: string;
  product_id: string;
  name: string;
  size: string | null;
  color: string | null;
  brand: string | null;
  price_cents: number;
  score: number;
  photo_url: string | null;
  zone_name: string | null;
}

interface PicksResponse {
  gated: string | null;
  cta: string | null;
  picks: Pick[];
  message?: string;
}

interface CouponPreview {
  code: string;
  discount_type: string;
  discount_value: number;
  discount_cents: number;
  new_total_cents: number;
  source: string;
  valid_until: string | null;
}

interface Alert {
  type: string;
  level: 'info' | 'warning';
  message: string;
}

interface CompanionPayload {
  client: {
    id: string;
    first_name: string;
    last_name: string;
    rfm_segment: string | null;
    membership_number: string | null;
  };
  loyalty: {
    active: boolean;
    points_current: number;
    would_earn: number;
    can_redeem_max_cents: number;
  };
  suggestions: Suggestion[];
  coupons: CouponPreview[];
  alerts: Alert[];
}

interface Props {
  clientId: string | null;
  cartTotalCents: number;
  cartProductIds: string[];
  onAddSuggestion?: (productId: string) => void;
  onApplyCoupon?: (code: string) => void;
}

const formatEur = (cents: number): string =>
  (cents / 100).toFixed(2).replace('.', ',') + ' €';

export default function ClientCompanion({
  clientId,
  cartTotalCents,
  cartProductIds,
  onAddSuggestion,
  onApplyCoupon,
}: Props) {
  const [payload, setPayload] = useState<CompanionPayload | null>(null);
  const [loading, setLoading] = useState(false);
  // « Pépites du jour » — loaded on demand (independent of the cart).
  const [picks, setPicks] = useState<PicksResponse | null>(null);
  const [picksLoading, setPicksLoading] = useState(false);
  const [picksOpen, setPicksOpen] = useState(false);
  // Mini product sheet (modal overlay) — null when closed.
  const [peek, setPeek] = useState<PeekItem | null>(null);

  // Reset the picks panel + modal only when the client changes — NOT on cart edits.
  useEffect(() => {
    setPicks(null);
    setPicksOpen(false);
    setPeek(null);
  }, [clientId]);

  const loadPicks = async () => {
    if (!clientId) return;
    setPicksOpen(true);
    setPicksLoading(true);
    try {
      const res = await api.get(`/api/pos/clients/${clientId}/picks?top_n=5`);
      setPicks(res.ok ? await res.json() : null);
    } catch {
      setPicks(null);
    }
    setPicksLoading(false);
  };

  useEffect(() => {
    if (!clientId) {
      setPayload(null);
      return;
    }
    // Debounce: cart mutates on every click, but we don't need to refetch
    // every keystroke. 300 ms aligned with the search debounce.
    const handle = setTimeout(() => {
      void load();
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, cartTotalCents, cartProductIds.join(',')]);

  const load = async () => {
    if (!clientId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        cart_total_cents: String(cartTotalCents),
        items: cartProductIds.join(','),
      });
      const res = await api.get(
        `/api/pos/clients/${clientId}/companion?${params.toString()}`
      );
      if (res.ok) {
        setPayload(await res.json());
      } else {
        setPayload(null);
      }
    } catch {
      setPayload(null);
    }
    setLoading(false);
  };

  if (!clientId) return null;

  return (
    <aside className="bg-vz-bg rounded-xl border border-vz-accent-soft/30 p-3 mb-3 shadow-sm space-y-3">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-black flex items-center gap-2">
          <span aria-hidden>💡</span>
          Compagnon caisse
        </h3>
        {loading && <span className="text-xs text-gray-400">Maj…</span>}
      </header>

      {payload ? (
        <>
          <section className="bg-white rounded-lg p-3 text-xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Solde fidélité</span>
              <span className="font-semibold text-vz-teal">
                {payload.loyalty.points_current} pts
              </span>
            </div>
            {payload.loyalty.would_earn > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-gray-500">À gagner sur ce panier</span>
                <span className="font-medium text-black">
                  +{payload.loyalty.would_earn} pts
                </span>
              </div>
            )}
            {/* NB : le rachat direct de points a été retiré (modèle chèque
                cadeau). On n'affiche plus « Rachat max possible » — c'était un
                reliquat non actionnable qui laissait croire à une remise
                applicable. La remise fidélité se propose via les chèques cadeau
                (100 pts → 5 €) affectés au paiement (bandeau chèques cadeaux). */}
          </section>

          {payload.alerts.length > 0 && (
            <ul className="space-y-1.5">
              {payload.alerts.map((alert) => (
                <li
                  key={alert.type}
                  className={
                    'text-xs px-2 py-1.5 rounded-lg ' +
                    (alert.level === 'warning'
                      ? 'bg-orange-50 text-orange-800 border border-orange-200'
                      : 'bg-vz-teal/10 text-vz-teal border border-vz-teal/30')
                  }
                >
                  {alert.message}
                </li>
              ))}
            </ul>
          )}

          {payload.coupons.length > 0 && (
            <section>
              <p className="text-xs font-medium text-black mb-1">Coupons applicables</p>
              <ul className="space-y-1">
                {payload.coupons.map((coupon) => (
                  <li
                    key={coupon.code}
                    className="bg-white rounded-lg p-2 text-xs flex items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <p className="font-mono truncate">{coupon.code}</p>
                      <p className="text-gray-500 text-[10px]">
                        {coupon.source} · -{formatEur(coupon.discount_cents)}
                      </p>
                    </div>
                    {onApplyCoupon && (
                      <button
                        type="button"
                        onClick={() => onApplyCoupon(coupon.code)}
                        className="text-[10px] px-2 py-1 rounded bg-vz-teal text-white"
                      >
                        Appliquer
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {payload.suggestions.length > 0 && (
            <section>
              <p className="text-xs font-medium text-black mb-1">Suggestions complémentaires</p>
              <ul className="grid grid-cols-3 gap-1.5">
                {payload.suggestions.map((s) => (
                  <li key={s.product_id}>
                    <button
                      type="button"
                      onClick={() =>
                        setPeek({
                          product_id: s.product_id,
                          name: s.name,
                          price_cents: s.price_cents,
                          photo_url: s.photo_url,
                          zone_name: s.zone_name,
                          size: s.size,
                          color: s.color,
                          canAdd: Boolean(onAddSuggestion),
                        })
                      }
                      className="block w-full bg-white rounded-lg overflow-hidden border border-gray-200 text-left p-0 hover:border-vz-teal hover:shadow-sm transition-all"
                    >
                      <div className="aspect-square bg-gray-100">
                        <Thumb url={s.photo_url} />
                      </div>
                      <div className="p-1.5">
                        <p className="text-[10px] text-black truncate">{s.name}</p>
                        <p className="text-[10px] text-gray-500 truncate">
                          {[s.size, s.color].filter(Boolean).join(' · ') || '—'}
                        </p>
                        <p className="text-[10px] text-vz-teal font-semibold">
                          {formatEur(s.price_cents)}
                        </p>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-[10px] text-gray-400 mt-1">
                Touchez une pièce pour voir sa fiche
              </p>
            </section>
          )}

          {/* « Pépites du jour » — independent of the cart, guides the
              salesperson to the physical zone. No add action (V3, §6.5). */}
          <section>
            {!picksOpen ? (
              <button
                type="button"
                onClick={loadPicks}
                className="w-full text-xs font-medium px-3 py-2 rounded-lg bg-vz-teal text-white hover:bg-vz-teal-deep"
              >
                ✨ Pépites du jour pour {payload.client.first_name}
              </button>
            ) : (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-black">✨ Pépites du jour</p>
                  {picksLoading && <span className="text-[10px] text-gray-400">…</span>}
                </div>
                {picks?.gated ? (
                  <p className="text-[11px] bg-vz-accent-soft/40 text-vz-ink rounded-lg p-2">
                    {picks.cta || 'Réservé aux membres avec profilage activé.'}
                  </p>
                ) : picks && picks.picks.length > 0 ? (
                  <ul className="grid grid-cols-3 gap-1.5">
                    {picks.picks.map((p) => (
                      <li key={p.id}>
                        <button
                          type="button"
                          onClick={() =>
                            setPeek({
                              product_id: p.product_id,
                              name: p.name,
                              price_cents: p.price_cents,
                              photo_url: p.photo_url,
                              zone_name: p.zone_name,
                              size: p.size,
                              color: p.color,
                              canAdd: false,
                            })
                          }
                          className="block w-full bg-white rounded-lg overflow-hidden border border-gray-200 text-left p-0 hover:border-vz-teal hover:shadow-sm transition-all"
                        >
                          <div className="aspect-square bg-gray-100">
                            <Thumb url={p.photo_url} />
                          </div>
                          <div className="p-1.5">
                            <p className="text-[10px] text-black truncate">{p.name}</p>
                            <p className="text-[10px] text-vz-teal font-semibold">
                              {formatEur(p.price_cents)}
                            </p>
                            {p.zone_name && (
                              <p className="text-[9px] text-gray-500 truncate" title={p.zone_name}>
                                📍 {p.zone_name}
                              </p>
                            )}
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-gray-500">
                    {picksLoading
                      ? 'Chargement…'
                      : picks?.message || 'Rien à proposer aujourd\'hui.'}
                  </p>
                )}
                <p className="text-[10px] text-gray-400">
                  Pièces présentes en boutique, classées selon ses goûts.
                </p>
              </div>
            )}
          </section>
        </>
      ) : (
        <p className="text-xs text-gray-500">
          {loading ? 'Chargement…' : 'Pas de données.'}
        </p>
      )}

      {/* Mini fiche produit — modale en overlay (n'affecte pas la mise en
          page « tout sur une page » du POS). */}
      {peek && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setPeek(null)}
        >
          <div
            className="w-full max-w-xs bg-white rounded-2xl overflow-hidden shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="aspect-square bg-gray-100 relative">
              <Thumb url={peek.photo_url} big />
              <button
                type="button"
                onClick={() => setPeek(null)}
                aria-label="Fermer"
                className="absolute top-2 right-2 h-8 w-8 rounded-full bg-white/90 text-gray-700 text-xl leading-none shadow"
              >
                ×
              </button>
            </div>
            <div className="p-4 space-y-2">
              <h4 className="font-medium text-black leading-snug">{peek.name}</h4>
              {(peek.size || peek.color) && (
                <p className="text-xs text-gray-500">
                  {[peek.size, peek.color].filter(Boolean).join(' · ')}
                </p>
              )}
              <p className="text-sm text-gray-700 flex items-center gap-1.5">
                <span aria-hidden>📍</span>
                {peek.zone_name || 'Emplacement non défini'}
              </p>
              <p className="text-lg font-semibold text-vz-teal">
                {formatEur(peek.price_cents)}
              </p>
              {peek.canAdd && onAddSuggestion && (
                <button
                  type="button"
                  onClick={() => {
                    onAddSuggestion(peek.product_id);
                    setPeek(null);
                  }}
                  className="w-full py-2.5 bg-vz-teal text-white rounded-lg font-medium hover:bg-vz-teal-deep"
                >
                  Ajouter au panier
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

/**
 * Robust product thumbnail: renders the image, and falls back to the 👗 glyph
 * when the URL is missing OR fails to load (a storefront copy can 404 on the
 * POS). Prevents the broken-image icon on suggestion / pick cards.
 */
function Thumb({ url, big }: { url: string | null; big?: boolean }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) {
    return (
      <div
        className={
          'w-full h-full flex items-center justify-center text-gray-300 ' +
          (big ? 'text-5xl' : 'text-2xl')
        }
      >
        👗
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={mediaUrl(url)}
      alt=""
      className="w-full h-full object-cover"
      onError={() => setFailed(true)}
    />
  );
}
