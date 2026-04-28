/**
 * Vintiz offer tile (charte v2).
 *
 * Renders a single coupon (anniversary, loyalty milestone, manual) in
 * the espace client offers list. Mirrors the visual layout of
 * `apps/site/src/app/account/offres/page.tsx`.
 */

interface OfferTileProps {
  code: string;
  /** "amount" → discount in €, "percent" → discount in %. */
  discountType: "amount" | "percent";
  discountValue: number;
  /** ISO timestamp (or null for evergreen). */
  validUntil: string | null;
  /** "anniversary" | "loyalty_milestone" | "manual" | "campaign" */
  source: string | null;
  expired?: boolean;
  notes?: string | null;
}

const SOURCE_LABELS: Record<string, string> = {
  loyalty_milestone: "Palier fidélité",
  anniversary: "Anniversaire",
  manual: "Cadeau boutique",
  campaign: "Opération en cours",
};

function formatDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export function OfferTile({
  code,
  discountType,
  discountValue,
  validUntil,
  source,
  expired,
  notes,
}: OfferTileProps) {
  const discount =
    discountType === "amount"
      ? `-${discountValue.toFixed(0)} €`
      : `-${discountValue.toFixed(0)} %`;

  return (
    <article
      className={
        "bg-white rounded-2xl shadow-sm p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 " +
        (expired ? "opacity-50" : "")
      }
    >
      <div>
        <p className="text-xs uppercase tracking-wider text-gray-500">
          {SOURCE_LABELS[source ?? ""] ?? "Coupon"}
        </p>
        <p className="text-2xl font-display font-semibold text-teal mt-1">{discount}</p>
        <p className="text-sm text-gray-600">
          Code <strong>{code}</strong> · valable jusqu&apos;au {formatDate(validUntil)}
        </p>
        {notes && <p className="text-xs text-gray-500 mt-1">{notes}</p>}
      </div>
      <span className="text-xs px-2 py-1 rounded-full bg-pink/30 text-black self-start">
        {expired ? "Expiré" : "À utiliser en boutique"}
      </span>
    </article>
  );
}
