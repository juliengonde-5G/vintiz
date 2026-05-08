import Link from "next/link";
import {
  CONDITION_LABEL,
  type VitrineProduct,
  discountPercent,
} from "@/data/vitrine-products";

interface ProductCardProps {
  product: VitrineProduct;
}

/**
 * Card produit pour la grille `/produits` et les blocs « pièces
 * similaires ». Mobile-first : grille 2 colonnes en `<sm`.
 *
 * Pas de photo réelle pour l'instant — un swatch coloré + le nom de la
 * marque en gros sert de placeholder visuel jusqu'au shoot pro
 * (cf. audit marketing M7).
 */
export default function ProductCard({ product }: ProductCardProps) {
  const discount = discountPercent(product);
  const sold = !product.available;

  return (
    <Link
      href={`/produits/${product.slug}`}
      className="group block bg-vz-surface rounded-2xl overflow-hidden border border-black/5 hover:border-vz-teal/30 transition-colors"
      aria-label={`${product.brand} — ${product.name}`}
    >
      <div
        className={`relative aspect-[3/4] ${product.swatch} flex items-center justify-center overflow-hidden`}
      >
        {/* Placeholder typographique tant que les photos pro ne sont pas shootées */}
        <span
          aria-hidden
          className="font-display text-2xl sm:text-3xl text-white/95 mix-blend-difference tracking-tight text-center px-3 leading-tight"
        >
          {product.brand}
        </span>

        {discount !== null && !sold && (
          <span className="absolute top-3 left-3 inline-flex items-center rounded-full bg-vz-accent text-white text-[11px] font-semibold px-2.5 py-0.5 tracking-wider">
            -{discount}%
          </span>
        )}
        {sold && (
          <span className="absolute inset-0 flex items-center justify-center bg-vz-ink/70 text-white font-display text-xl tracking-wider">
            Vendu
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
          Taille {product.size} · {product.color} · {CONDITION_LABEL[product.condition]}
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
