import { legalMissingFields } from "@/data/legal-info";

/**
 * Bandeau « mentions provisoires » affiché en haut des pages légales tant que
 * des mentions obligatoires restent à compléter dans data/legal-info.ts.
 * Disparaît automatiquement une fois toutes les valeurs renseignées.
 */
export default function LegalDraftNotice() {
  const missing = legalMissingFields();
  if (missing.length === 0) return null;

  return (
    <div
      role="note"
      className="mb-8 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <p className="font-medium">Mentions légales provisoires</p>
      <p className="mt-1 leading-relaxed">
        Certaines informations obligatoires sont en cours de finalisation
        d&apos;immatriculation&nbsp;: {missing.join(", ")}. Elles seront publiées
        dès leur disponibilité.
      </p>
    </div>
  );
}
