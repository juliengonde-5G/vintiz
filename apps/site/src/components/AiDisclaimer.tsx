import Link from "next/link";

interface AiDisclaimerProps {
  /** Variante visuelle. `banner` = pleine largeur sticky, `inline` = encart simple. */
  variant?: "banner" | "inline";
  className?: string;
}

/**
 * Disclaimer permanent IA — conformité AI Act art. 50 (UE 2024/1689,
 * applicable au 02/08/2026 pour les systèmes à risque limité).
 *
 * À monter sur toute UI où un utilisateur interagit avec l'IA Personal
 * Shopper (Claude Haiku) — visible *avant* la première interaction, pas
 * en réponse à celle-ci.
 *
 * Les sorties IA générées par cette page doivent en plus porter
 * `data-ai-generated="true"` (cf. AiBadge / ProductGrid).
 */
export default function AiDisclaimer({
  variant = "banner",
  className = "",
}: AiDisclaimerProps) {
  if (variant === "inline") {
    return (
      <div
        role="note"
        aria-label="Information sur l'usage de l'intelligence artificielle"
        className={`rounded-xl bg-vz-teal-soft/40 border border-vz-teal/20 px-4 py-3 text-xs text-vz-ink-soft leading-relaxed ${className}`}
      >
        <p>
          <span className="font-semibold text-vz-ink">IA — </span>
          Cette page utilise une intelligence artificielle (Claude Haiku,
          hébergée en Union européenne) pour vous proposer des recommandations
          personnalisées.{" "}
          <Link
            href="/confidentialite#personal-shopper"
            className="underline underline-offset-2 hover:text-vz-teal"
          >
            En savoir plus
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div
      role="note"
      aria-label="Information sur l'usage de l'intelligence artificielle"
      className={`bg-vz-teal-soft/50 border-y border-vz-teal/20 ${className}`}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs sm:text-sm text-vz-ink-soft leading-relaxed">
        <p className="flex items-start gap-2">
          <span
            aria-hidden
            className="mt-0.5 inline-flex items-center justify-center rounded-full bg-vz-teal text-white font-semibold text-[10px] tracking-wider px-2 py-0.5 shrink-0"
          >
            IA
          </span>
          <span>
            <span className="font-semibold text-vz-ink">
              Vous interagissez avec une intelligence artificielle.
            </span>{" "}
            Personal Shopper Vintiz est alimenté par Claude Haiku
            (Anthropic, hébergement UE). Les recommandations sont
            personnalisées à partir de vos goûts.
          </span>
        </p>
        <Link
          href="/confidentialite#personal-shopper"
          className="inline-flex shrink-0 items-center gap-1 text-vz-teal font-medium hover:underline whitespace-nowrap"
        >
          En savoir plus
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
