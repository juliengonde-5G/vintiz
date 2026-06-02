import Link from "next/link";
import {
  CONDITION_LABEL,
  type ProductCondition,
  type VitrineProduct,
  discountPercent as demoDiscount,
} from "@/data/vitrine-products";
import {
  type ApiProduct,
  discountPercent as apiDiscount,
  PUBLIC_CONDITION_LABELS,
} from "@/lib/storefront-api";
import { mediaUrl } from "@/lib/media";

const CONDITION_LABEL_EN: Record<ProductCondition, string> = {
  excellent: "Excellent condition",
  "tres-bon": "Very good condition",
  bon: "Good condition",
};

const CONDITION_LABEL_EN_API: Record<NonNullable<ApiProduct["condition"]>, string> = {
  excellent: "Excellent condition",
  "tres-bon": "Very good condition",
  bon: "Good condition",
};

interface ProductCardProps {
  /** Soit une fiche vitrine statique (data/vitrine-products), soit une fiche API publique. */
  product: VitrineProduct | ApiProduct;
  /** "fr" (default) keeps FR pages untouched; "en" renders English chrome. */
  locale?: "fr" | "en";
}

/**
 * Card produit pour la grille `/produits` et les blocs « pièces
 * similaires ». Mobile-first : grille 2 colonnes en `<sm`.
 *
 * Accepte indifféremment :
 *   - une fiche démo (``VitrineProduct``) → couleur swatch en placeholder
 *   - une fiche API (``ApiProduct``) → photo storefront détourée si dispo,
 *     sinon initiale typographique de la marque
 */
export default function ProductCard({
  product,
  locale = "fr",
}: ProductCardProps) {
  const isEn = locale === "en";
  const isApi = !("swatch" in product);

  const sold = isApi ? !product.available : !(product as VitrineProduct).available;
  const photoUrl = isApi ? (product as ApiProduct).photo_url : null;
  const swatch = !isApi ? (product as VitrineProduct).swatch : "bg-vz-bg-alt";
  const discount = isApi
    ? apiDiscount(product as ApiProduct)
    : demoDiscount(product as VitrineProduct);

  const conditionKey = (product as ApiProduct).condition ?? "tres-bon";
  const conditionLabel = isApi
    ? isEn
      ? CONDITION_LABEL_EN_API[conditionKey as keyof typeof CONDITION_LABEL_EN_API]
      : PUBLIC_CONDITION_LABELS[conditionKey as keyof typeof PUBLIC_CONDITION_LABELS]
    : isEn
      ? CONDITION_LABEL_EN[(product as VitrineProduct).condition]
      : CONDITION_LABEL[(product as VitrineProduct).condition];

  return (
    <Link
      href={`/produits/${product.slug}`}
      className="group block bg-vz-surface rounded-2xl overflow-hidden border border-black/5 hover:border-vz-teal/30 transition-colors"
      aria-label={`${product.brand} — ${product.name}`}
    >
      <div
        className={`relative aspect-[3/4] ${photoUrl ? "bg-vz-bg-alt" : swatch} flex items-center justify-center overflow-hidden`}
      >
        {photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl(photoUrl)}
            alt={`${product.brand} — ${product.name}`}
            className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500"
            loading="lazy"
          />
        ) : (
          /* Placeholder typographique tant que la photo storefront n'est pas générée */
          <span
            aria-hidden
            className="font-display text-2xl sm:text-3xl text-white/95 mix-blend-difference tracking-tight text-center px-3 leading-tight"
          >
            {product.brand}
          </span>
        )}

        {discount !== null && !sold && (
          <span className="absolute top-3 left-3 inline-flex items-center rounded-full bg-vz-accent text-white text-[11px] font-semibold px-2.5 py-0.5 tracking-wider">
            -{discount}%
          </span>
        )}
        {sold && (
          <span className="absolute inset-0 flex items-center justify-center bg-vz-ink/70 text-white font-display text-xl tracking-wider">
            {isEn ? "Sold" : "Vendu"}
          </span>
        )}
      </div>

      <div className="p-4 flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.12em] text-vz-ink-mute font-medium">
          {product.brand}
        </p>
        <h3 className="text-sm font-medium text-vz-ink line-clamp-2 leading-snug">
          {product.name}
        </h3>
        <p className="text-xs text-vz-ink-mute">
          {isEn ? "Size" : "Taille"} {product.size} · {product.color} ·{" "}
          {conditionLabel}
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-base font-semibold text-vz-teal">
            {product.price_eur} €
          </span>
          {product.retail_price_eur && product.retail_price_eur > product.price_eur && (
            <span className="text-xs text-vz-ink-mute line-through">
              {product.retail_price_eur} €
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
