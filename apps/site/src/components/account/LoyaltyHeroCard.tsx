"use client";

interface LoyaltyHeroProps {
  firstName: string;
  membershipNumber: string | null;
  points: number;
  nextTierLabel?: string;       // ex: "Prochain palier"
  pointsToNext?: number;         // ex: 260
  benefitText?: string;          // ex: "1 € = 1 pt · 100 pts = chèque cadeau de 5 €"
}

/**
 * Loyalty hero card — Sauge Néo direction. Big Fraunces 40px teal number for
 * the points balance, V###### in monospace, 4-px progress bar to the next
 * tier and a benefit one-liner below. Used by /account home and /account/fidelite.
 */
export default function LoyaltyHeroCard({
  firstName,
  membershipNumber,
  points,
  nextTierLabel = "Prochain palier",
  pointsToNext,
  benefitText = "1 € dépensé hors remise = 1 pt · 100 pts = chèque cadeau de 5 €",
}: LoyaltyHeroProps) {
  // Compute progress to the next 100-pts tier when caller doesn't supply one.
  const remainder = pointsToNext ?? Math.max(0, 100 - (points % 100));
  const progressPct = pointsToNext != null
    ? Math.min(100, Math.max(0, ((100 - pointsToNext) / 100) * 100))
    : (points % 100);

  return (
    <article className="bg-vz-surface rounded-vz-lg border border-vz-line p-6 md:p-8 shadow-vz-soft">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-teal">
            Carte fidélité Vintiz
          </p>
          <h2 className="font-display text-2xl md:text-3xl text-vz-ink mt-2">
            Bonjour {firstName} <span className="text-vz-accent">·</span>
          </h2>
        </div>
        {membershipNumber && (
          <span className="font-mono text-xs text-vz-ink-mute bg-vz-bg-alt rounded-full px-3 py-1">
            {membershipNumber}
          </span>
        )}
      </div>

      <div className="mt-6 flex items-baseline gap-3">
        <span className="font-display text-5xl md:text-6xl font-[450] text-vz-teal leading-none tracking-[-0.02em]">
          {points.toLocaleString("fr-FR")}
        </span>
        <span className="text-sm font-mono uppercase tracking-[0.18em] text-vz-ink-mute">
          pts
        </span>
      </div>

      <div className="mt-5">
        <div className="h-1 bg-vz-line rounded-full overflow-hidden">
          <div
            className="h-full bg-vz-teal rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-vz-ink-mute">
          {nextTierLabel} · <strong className="text-vz-ink-soft">{remainder}</strong> pts pour un chèque cadeau de 5 €
        </p>
      </div>

      <p className="mt-5 text-xs font-mono uppercase tracking-[0.18em] text-vz-ink-mute">
        {benefitText}
      </p>
    </article>
  );
}
