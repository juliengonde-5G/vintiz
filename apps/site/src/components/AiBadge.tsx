interface AiBadgeProps {
  /** Tooltip étendu — par défaut « Recommandation générée par IA ». */
  label?: string;
  className?: string;
}

/**
 * Badge « IA » — marquage visible des sorties générées par IA, à apposer
 * sur chaque card produit recommandée par Personal Shopper.
 *
 * Combiné à `data-ai-generated="true"` sur le conteneur parent, ce badge
 * satisfait le marquage **machine-readable** des sorties d'un système d'IA
 * exigé par l'AI Act art. 50-2 (UE 2024/1689).
 */
export default function AiBadge({
  label = "Recommandation générée par IA",
  className = "",
}: AiBadgeProps) {
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={`inline-flex items-center gap-1 rounded-full bg-vz-teal text-white font-semibold text-[10px] tracking-wider px-2 py-0.5 ${className}`}
    >
      <svg
        width="9"
        height="9"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M12 2v6M5.34 6.34l4.24 4.24M2 12h6M5.34 17.66l4.24-4.24M12 22v-6M18.66 17.66l-4.24-4.24M22 12h-6M18.66 6.34l-4.24 4.24" />
      </svg>
      IA
    </span>
  );
}
