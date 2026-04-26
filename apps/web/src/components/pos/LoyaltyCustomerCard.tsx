'use client';

import React from 'react';

export type CustomerBrief = {
  id: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  loyalty_points: number;
  tier: string;
  avoir_credit: number;
  last_visit?: string | null;
  days_since_last_visit?: number | null;
  lifetime_value: number;
  favorite_categories: { name: string; count: number; share: number }[];
  favorite_brands: string[];
  favorite_colors: string[];
  size_profile: { haut?: string; bas?: string };
  last_purchases: { date?: string; name: string; price: number }[];
  personal_shopper_picks_today: { id: string; name: string; thumb?: string | null; score?: number | null }[];
  active_reservation?: any | null;
  anniversary_coupon?: { code: string; discount_value: number; valid_until?: string | null } | null;
  rfm_segment?: string | null;
};

type Props = {
  brief: CustomerBrief;
  onTapPick?: (productId: string) => void;
  onClose?: () => void;
};

const tierColor = (tier: string): string => {
  const t = (tier || '').toLowerCase();
  if (t === 'gold' || t === 'or') return 'bg-yellow-50 text-yellow-700 border-yellow-200';
  if (t === 'silver' || t === 'argent') return 'bg-gray-50 text-gray-700 border-gray-200';
  return 'bg-orange-50 text-orange-700 border-orange-200';
};

const formatVisit = (days?: number | null) => {
  if (days === null || days === undefined) return 'Première visite';
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return 'Hier';
  if (days < 7) return `Il y a ${days} j`;
  if (days < 30) return `Il y a ${Math.floor(days / 7)} sem.`;
  if (days < 365) return `Il y a ${Math.floor(days / 30)} mois`;
  return `Il y a ${Math.floor(days / 365)} an(s)`;
};

export default function LoyaltyCustomerCard({ brief, onTapPick, onClose }: Props) {
  const sizeStr = [
    brief.size_profile.haut && `Taille ${brief.size_profile.haut}`,
    brief.size_profile.bas && `T.${brief.size_profile.bas}`,
  ].filter(Boolean).join(' · ');

  return (
    <div className="bg-gradient-warm rounded-xl border border-pink/30 p-3 mb-3 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xl shrink-0">🌟</span>
          <div className="min-w-0">
            <div className="font-medium text-black truncate">
              {brief.first_name} {brief.last_name}
            </div>
            <div className={`inline-block text-[11px] px-2 py-0.5 rounded-full border ${tierColor(brief.tier)}`}>
              {brief.tier} · {brief.loyalty_points} pts
              {brief.avoir_credit > 0 && ` · avoir ${brief.avoir_credit.toFixed(2)}€`}
            </div>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-black min-h-0 min-w-0 h-6 w-6"
            aria-label="Fermer la carte"
          >
            ×
          </button>
        )}
      </div>

      {/* Key meta */}
      <div className="text-xs text-gray-600 mb-2 flex flex-wrap gap-x-3 gap-y-0.5">
        <span>🕒 {formatVisit(brief.days_since_last_visit)}</span>
        <span>💰 CA total {brief.lifetime_value.toFixed(0)} €</span>
        {brief.rfm_segment && <span className="text-teal">· {brief.rfm_segment}</span>}
      </div>

      {/* Profile chips */}
      <div className="text-xs text-black space-y-0.5 mb-3">
        {brief.favorite_categories.length > 0 && (
          <div>
            <span className="text-gray-500">Achète souvent :</span>{' '}
            {brief.favorite_categories.map((c, i) => (
              <span key={c.name}>
                <strong>{c.name}</strong> ({Math.round(c.share * 100)}%)
                {i < brief.favorite_categories.length - 1 && ' · '}
              </span>
            ))}
          </div>
        )}
        {brief.favorite_brands.length > 0 && (
          <div>
            <span className="text-gray-500">Marques :</span> {brief.favorite_brands.join(', ')}
          </div>
        )}
        <div className="flex flex-wrap gap-x-3">
          {brief.favorite_colors.length > 0 && (
            <span>
              <span className="text-gray-500">Couleurs :</span> {brief.favorite_colors.join(', ')}
            </span>
          )}
          {sizeStr && (
            <span>
              <span className="text-gray-500">Taille :</span> {sizeStr}
            </span>
          )}
        </div>
      </div>

      {/* Anniversary coupon */}
      {brief.anniversary_coupon && (
        <div className="text-xs bg-pink/30 rounded-lg p-2 mb-2">
          🎁 Coupon {brief.anniversary_coupon.code} · -{brief.anniversary_coupon.discount_value}€
          {brief.anniversary_coupon.valid_until && (
            <> · jusqu'au {brief.anniversary_coupon.valid_until.slice(0, 10)}</>
          )}
        </div>
      )}

      {/* Active reservation warning */}
      {brief.active_reservation && (
        <div className="text-xs bg-amber-50 text-amber-700 rounded-lg p-2 mb-2">
          ⚠ Réservation 48h active · {brief.active_reservation.expires_at?.slice(0, 16)}
        </div>
      )}

      {/* Personal Shopper picks */}
      {brief.personal_shopper_picks_today.length > 0 && (
        <div>
          <div className="text-xs font-medium text-black mb-1.5">
            💡 Suggestions du jour pour {brief.first_name}
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            {brief.personal_shopper_picks_today.slice(0, 3).map((pick) => (
              <button
                key={pick.id}
                onClick={() => onTapPick?.(pick.id)}
                disabled={!onTapPick}
                className="bg-white rounded-lg overflow-hidden border border-gray-200 text-left min-h-0 min-w-0 p-0 hover:border-teal hover:shadow-sm transition-all"
              >
                <div className="aspect-square bg-gray-100 overflow-hidden">
                  {pick.thumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={pick.thumb} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-2xl text-gray-300">👗</div>
                  )}
                </div>
                <div className="p-1.5">
                  <div className="text-[10px] text-black truncate">{pick.name}</div>
                  {typeof pick.score === 'number' && (
                    <div className="text-[10px] text-teal">{pick.score.toFixed(0)}/100</div>
                  )}
                </div>
              </button>
            ))}
          </div>
          <p className="text-[10px] text-gray-400 mt-1">Tap pour ajouter au panier</p>
        </div>
      )}
    </div>
  );
}
