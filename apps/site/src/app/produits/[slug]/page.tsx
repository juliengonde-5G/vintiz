import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import ProductCard from "@/components/ProductCard";
import {
  CATEGORY_LABEL,
  CONDITION_LABEL,
  PRODUCTS,
  discountPercent,
  findProduct,
  relatedProducts,
} from "@/data/vitrine-products";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

interface PageProps {
  params: { slug: string };
}

// Pré-rendre toutes les fiches produit au build (toutes en SSG).
export function generateStaticParams() {
  return PRODUCTS.map((p) => ({ slug: p.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const product = findProduct(params.slug);
  if (!product) {
    return {
      title: "Pièce introuvable",
      robots: { index: false, follow: false },
    };
  }
  const title = `${product.brand} — ${product.name} (taille ${product.size})`;
  const description = `${product.brand} ${product.name}, taille ${product.size}, ${product.color}, ${CONDITION_LABEL[product.condition].toLowerCase()}. Authentifiée et sélectionnée par notre équipe à Vernon.`;
  return {
    title,
    description,
    alternates: { canonical: `${SITE_URL}/produits/${product.slug}` },
    // Si la pièce n'est plus disponible, on garde la page accessible mais
    // hors index pour ne pas pourrir le SEO avec des fiches mortes.
    robots: product.available
      ? undefined
      : { index: false, follow: true },
    openGraph: {
      title: `${title} | Vintiz`,
      description,
      url: `${SITE_URL}/produits/${product.slug}`,
      type: "website",
      locale: "fr_FR",
    },
  };
}

export default function ProductPage({ params }: PageProps) {
  const product = findProduct(params.slug);
  if (!product) {
    notFound();
  }

  const discount = discountPercent(product);
  const related = relatedProducts(product);

  // JSON-LD Product (Schema.org) — Google peut afficher prix, dispo,
  // état dans les rich results « shopping ».
  const productJsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: `${product.brand} — ${product.name}`,
    description: product.description,
    brand: { "@type": "Brand", name: product.brand },
    category: CATEGORY_LABEL[product.category],
    color: product.color,
    size: product.size,
    itemCondition:
      product.condition === "excellent"
        ? "https://schema.org/NewCondition"
        : "https://schema.org/UsedCondition",
    offers: {
      "@type": "Offer",
      url: `${SITE_URL}/produits/${product.slug}`,
      priceCurrency: "EUR",
      price: product.price_eur.toFixed(2),
      availability: product.available
        ? "https://schema.org/InStock"
        : "https://schema.org/SoldOut",
      itemCondition: "https://schema.org/UsedCondition",
      seller: {
        "@type": "ClothingStore",
        name: "Vintiz",
        url: SITE_URL,
        address: {
          "@type": "PostalAddress",
          streetAddress: "6 rue Saint-Jacques",
          addressLocality: "Vernon",
          postalCode: "27200",
          addressCountry: "FR",
        },
      },
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(productJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg pb-24 sm:pb-12">
        <section className="max-w-6xl mx-auto px-6 py-8 lg:py-12">
          {/* Fil d'Ariane */}
          <nav
            aria-label="Fil d'Ariane"
            className="text-xs text-vz-ink-mute mb-6"
          >
            <Link href="/produits" className="hover:text-vz-teal">
              Boutique
            </Link>
            <span className="mx-2">/</span>
            <Link
              href={`/produits?categorie=${product.category}`}
              className="hover:text-vz-teal"
            >
              {CATEGORY_LABEL[product.category]}
            </Link>
            <span className="mx-2">/</span>
            <span className="text-vz-ink">{product.brand}</span>
          </nav>

          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16">
            {/* Visuel placeholder */}
            <div
              className={`relative aspect-[3/4] ${product.swatch} rounded-2xl overflow-hidden flex items-center justify-center`}
            >
              <span
                aria-hidden
                className="font-display text-4xl sm:text-6xl text-white/95 mix-blend-difference text-center px-6 leading-tight tracking-tight"
              >
                {product.brand}
              </span>
              {discount !== null && product.available && (
                <span className="absolute top-4 left-4 inline-flex items-center rounded-full bg-vz-accent text-white text-sm font-semibold px-3 py-1 tracking-wider">
                  -{discount}%
                </span>
              )}
              {!product.available && (
                <span className="absolute inset-0 flex items-center justify-center bg-vz-ink/70 text-white font-display text-3xl tracking-wider">
                  Vendu
                </span>
              )}
            </div>

            {/* Détails produit */}
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-2">
                {product.brand}
              </p>
              <h1 className="font-display font-[450] text-3xl sm:text-4xl text-vz-ink leading-tight">
                {product.name}
              </h1>

              <div className="mt-6 flex items-baseline gap-3">
                <span className="text-3xl font-semibold text-vz-teal">
                  {product.price_eur} €
                </span>
                {product.retail_price_eur &&
                  product.retail_price_eur > product.price_eur && (
                    <span className="text-base text-vz-ink-mute line-through">
                      {product.retail_price_eur} € neuf
                    </span>
                  )}
                {discount !== null && (
                  <span className="text-sm text-vz-accent font-semibold">
                    -{discount}%
                  </span>
                )}
              </div>

              <dl className="mt-8 grid grid-cols-2 gap-y-4 text-sm">
                <dt className="text-vz-ink-mute">Marque</dt>
                <dd className="text-vz-ink font-medium">{product.brand}</dd>
                <dt className="text-vz-ink-mute">Catégorie</dt>
                <dd className="text-vz-ink font-medium">
                  {CATEGORY_LABEL[product.category]}
                </dd>
                <dt className="text-vz-ink-mute">Taille</dt>
                <dd className="text-vz-ink font-medium">{product.size}</dd>
                <dt className="text-vz-ink-mute">Couleur</dt>
                <dd className="text-vz-ink font-medium">{product.color}</dd>
                <dt className="text-vz-ink-mute">État</dt>
                <dd className="text-vz-ink font-medium">
                  {CONDITION_LABEL[product.condition]}
                </dd>
                <dt className="text-vz-ink-mute">Disponibilité</dt>
                <dd
                  className={`font-medium ${
                    product.available ? "text-vz-teal" : "text-vz-ink-mute"
                  }`}
                >
                  {product.available
                    ? "Disponible en boutique"
                    : "Vendue — fiche conservée pour mémoire"}
                </dd>
              </dl>

              <div className="mt-8 prose prose-sm max-w-none text-vz-ink-soft leading-relaxed">
                <p>{product.description}</p>
              </div>

              {/* CTA desktop (le sticky mobile est plus bas) */}
              <div className="mt-8 hidden sm:flex flex-col sm:flex-row gap-3">
                {product.available ? (
                  <>
                    <Link
                      href={`/contact?subject=reservation%20${encodeURIComponent(product.slug)}`}
                      className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
                    >
                      Réserver 24-48h
                    </Link>
                    <a
                      href={`mailto:contact@vintiz.fr?subject=R%C3%A9servation%20%E2%80%94%20${encodeURIComponent(
                        product.slug,
                      )}&body=Bonjour%2C%0A%0AJe%20souhaite%20r%C3%A9server%20cette%20pi%C3%A8ce%20%3A%20${encodeURIComponent(
                        product.brand + " — " + product.name,
                      )}%0A%0AMerci%20%21`}
                      className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-7 py-3 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
                    >
                      Nous écrire
                    </a>
                  </>
                ) : (
                  <Link
                    href="/produits"
                    className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-7 py-3 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    Voir les pièces disponibles
                  </Link>
                )}
              </div>

              <p className="mt-6 text-xs text-vz-ink-mute leading-relaxed">
                Pièce unique sourcée et triée par notre équipe à Vernon
                (partenariat Solidarité Textiles). Aucun retour digital — la
                pièce est à essayer sur place.
              </p>
            </div>
          </div>
        </section>

        {/* Pièces similaires */}
        {related.length > 0 && (
          <section className="bg-vz-bg-alt border-y border-black/5">
            <div className="max-w-6xl mx-auto px-6 py-12">
              <h2 className="font-display text-2xl sm:text-3xl text-vz-ink mb-8">
                Pourrait aussi vous plaire
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-6">
                {related.map((p) => (
                  <ProductCard key={p.slug} product={p} />
                ))}
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Sticky CTA mobile uniquement */}
      {product.available && (
        <div className="sm:hidden fixed bottom-0 inset-x-0 z-40 border-t border-black/10 bg-vz-surface/98 backdrop-blur-md px-4 py-3 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-vz-ink-mute truncate">{product.brand}</p>
            <p className="text-base font-semibold text-vz-teal">
              {product.price_eur} €
            </p>
          </div>
          <Link
            href={`/contact?subject=reservation%20${encodeURIComponent(product.slug)}`}
            className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-5 py-2.5 text-sm font-medium whitespace-nowrap"
          >
            Réserver 24-48h
          </Link>
        </div>
      )}

      <PublicFooter />
    </>
  );
}
