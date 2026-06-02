'use client';

import React from 'react';

export type CustomerBrief = {
  id: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  loyalty_points: number;
  loyalty_active: boolean;
  membership_number: string | null;
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
  anniversary_coupon?: { code: string; discount_value: number; valid_until?: string | null } | null;
  rfm_segment?: string | null;
};

type Props = {
  brief: CustomerBrief;
  // ``onTapPick`` was used by the legacy 3-thumbnail grid that this card
  // showed when a member was identified. The grid was moved to the
  // ClientCompanion's « ✨ Pépites du jour » button so the card stays
  // compact at the top of the ticket. Prop kept (optional, ignored) so
  // existing callers don't break — safe to drop in a future cleanup.
  onTapPick?: (productId: string) => void;
  onClose?: () => void;
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

export default function LoyaltyCustomerCard({ brief, onClose }: Props) {
  const sizeStr = [
    brief.size_profile.haut && `T.${brief.size_profile.haut}`,
    brief.size_profile.bas && `T.${brief.size_profile.bas}`,
  ].filter(Boolean).join(' · ');

  // Compact card : à l'identification cliente, on voulait alléger ce
  // bandeau (l'utilisateur disait « trop gros »). On ne montre plus la
  // grille Personal Shopper ici — elle est désormais exposée via le
  // bouton « ✨ Pépites du jour » du ClientCompanion juste en dessous,
  // qui charge à la demande et garde l'affectation principale du POS
  // (panier + recherche) intacte.
  return (
    <div className="bg-vz-bg rounded-lg border border-vz-line/60 px-2.5 py-1.5 mb-1.5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-base shrink-0" aria-hidden>🌟</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0">
              <span className="text-xs font-semibold text-black truncate">
                {brief.first_name} {brief.last_name}
              </span>
              <span className="text-[10px] text-vz-teal-deep font-medium">
                {brief.membership_number ?? 'Non membre'} · {brief.loyalty_points} pts
              </span>
              {brief.avoir_credit > 0 && (
                <span className="text-[10px] text-vz-accent font-medium">
                  avoir {brief.avoir_credit.toFixed(2)}€
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-x-2 gap-y-0 text-[10px] text-gray-500 leading-tight">
              <span>🕒 {formatVisit(brief.days_since_last_visit)}</span>
              <span>· CA {brief.lifetime_value.toFixed(0)} €</span>
              {brief.rfm_segment && <span className="text-vz-teal">· {brief.rfm_segment}</span>}
              {brief.favorite_categories[0] && (
                <span>· {brief.favorite_categories[0].name} ({Math.round(brief.favorite_categories[0].share * 100)}%)</span>
              )}
              {sizeStr && <span>· {sizeStr}</span>}
            </div>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-300 hover:text-black h-5 w-5 leading-none text-sm shrink-0"
            aria-label="Fermer la carte"
          >
            ×
          </button>
        )}
      </div>

      {brief.anniversary_coupon && (
        <div className="mt-1 text-[10px] text-vz-accent leading-snug">
          🎁 {brief.anniversary_coupon.code} · -{brief.anniversary_coupon.discount_value}€
          {brief.anniversary_coupon.valid_until && (
            <> · jusqu'au {brief.anniversary_coupon.valid_until.slice(0, 10)}</>
          )}
        </div>
      )}
    </div>
  );
}
