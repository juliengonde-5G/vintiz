import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import ProductCard from "@/components/ProductCard";
import {
  getPublicProduct,
  discountPercent,
  PUBLIC_CATEGORY_LABELS,
  PUBLIC_CONDITION_LABELS,
} from "@/lib/storefront-api";
import { brandSlug } from "@/data/vitrine-products";
import { mediaUrl } from "@/lib/media";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

// La fiche détail est dynamique : on supprime le SSG pré-build pour que
// les nouvelles pièces ajoutées par le manager apparaissent sans
// régénération forcée. Cache ISR 5 min comme la liste.
export const revalidate = 300;
// Pas de generateStaticParams : Next génère à la demande (et cache).
export const dynamicParams = true;

interface PageProps {
  params: { slug: string };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const product = await getPublicProduct(params.slug);
  if (!product) {
    return {
      title: "Pièce introuvable",
      robots: { index: false, follow: false },
    };
  }
  const categoryLabel = product.category
    ? PUBLIC_CATEGORY_LABELS[product.category]
    : "Pièce";
  const conditionLabel = product.condition
    ? PUBLIC_CONDITION_LABELS[product.condition].toLowerCase()
    : "état soigné";
  const title = `${product.brand ?? categoryLabel} — ${product.name} (taille ${product.size ?? "—"})`;
  const description = `${product.brand ?? "Pièce sélectionnée"} ${product.name}, taille ${product.size ?? "—"}, ${product.color ?? "—"}, ${conditionLabel}. Authentifiée et sélectionnée par notre équipe à Vernon.`;
  return {
    title,
    description,
    alternates: { canonical: `${SITE_URL}/produits/${product.slug}` },
    // Si la pièce n'est plus disponible, on garde la page accessible mais
    // hors index pour ne pas pourrir le SEO avec des fiches mortes.
    robots: product.available ? undefined : { index: false, follow: true },
    openGraph: {
      title: `${title} | Vintiz`,
      description,
      url: `${SITE_URL}/produits/${product.slug}`,
      type: "website",
      locale: "fr_FR",
      images: product.photo_url
        ? [{ url: mediaUrl(product.photo_url) }]
        : undefined,
    },
  };
}

export default async function ProductPage({ params }: PageProps) {
  const product = await getPublicProduct(params.slug);
  if (!product) {
    notFound();
  }

  const discount = discountPercent(product);
  const related = product.related;
  const categoryLabel = product.category
    ? PUBLIC_CATEGORY_LABELS[product.category]
    : "Pièce";

  // JSON-LD Product (Schema.org) — Google peut afficher prix, dispo,
  // état dans les rich results « shopping ».
  const productJsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: `${product.brand ?? categoryLabel} — ${product.name}`,
    description: product.description ?? "",
    brand: product.brand ? { "@type": "Brand", name: product.brand } : undefined,
    category: categoryLabel,
    color: product.color ?? undefined,
    size: product.size ?? undefined,
    image: product.photos.length > 0
      ? product.photos.map((u) => mediaUrl(u))
      : undefined,
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

  // Fil d'Ariane structuré (BreadcrumbList).
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Accueil", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Boutique", item: `${SITE_URL}/produits` },
      {
        "@type": "ListItem",
        position: 3,
        name: categoryLabel,
        item: `${SITE_URL}/produits?categorie=${product.category ?? ""}`,
      },
      {
        "@type": "ListItem",
        position: 4,
        name: `${product.brand ?? ""} — ${product.name}`,
        item: `${SITE_URL}/produits/${product.slug}`,
      },
    ],
  };

  const conditionLabel = product.condition
    ? PUBLIC_CONDITION_LABELS[product.condition]
    : "—";

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(productJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
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
              href={`/produits?categorie=${product.category ?? ""}`}
              className="hover:text-vz-teal"
            >
              {categoryLabel}
            </Link>
            <span className="mx-2">/</span>
            <span className="text-vz-ink">{product.brand}</span>
          </nav>

          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16">
            {/* Visuel principal — photo storefront (détourée) en priorité */}
            <div className="space-y-3">
              <div
                className={`relative aspect-[3/4] ${
                  product.photo_url ? "bg-vz-bg-alt" : "bg-vz-ink"
                } rounded-2xl overflow-hidden flex items-center justify-center`}
              >
                {product.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={mediaUrl(product.photo_url)}
                    alt={`${product.brand} — ${product.name}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span
                    aria-hidden
                    className="font-display text-4xl sm:text-6xl text-white/95 mix-blend-difference text-center px-6 leading-tight tracking-tight"
                  >
                    {product.brand}
                  </span>
                )}
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
              {/* Miniatures secondaires */}
              {product.photos.length > 1 && (
                <div className="grid grid-cols-4 gap-2">
                  {product.photos.slice(0, 4).map((url, i) => (
                    <div
                      key={i}
                      className="aspect-square rounded-lg overflow-hidden bg-vz-bg-alt"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={mediaUrl(url)}
                        alt=""
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>
                  ))}
                </div>
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
                {product.brand && (
                  <>
                    <dt className="text-vz-ink-mute">Marque</dt>
                    <dd className="text-vz-ink font-medium">
                      <Link
                        href={`/produits/marque/${brandSlug(product.brand)}`}
                        className="underline underline-offset-2 hover:text-vz-teal"
                      >
                        {product.brand}
                      </Link>
                    </dd>
                  </>
                )}
                {product.category && (
                  <>
                    <dt className="text-vz-ink-mute">Catégorie</dt>
                    <dd className="text-vz-ink font-medium">
                      <Link
                        href={`/produits?categorie=${product.category}`}
                        className="underline underline-offset-2 hover:text-vz-teal"
                      >
                        {categoryLabel}
                      </Link>
                    </dd>
                  </>
                )}
                {product.size && (
                  <>
                    <dt className="text-vz-ink-mute">Taille</dt>
                    <dd className="text-vz-ink font-medium">{product.size}</dd>
                  </>
                )}
                {product.color && (
                  <>
                    <dt className="text-vz-ink-mute">Couleur</dt>
                    <dd className="text-vz-ink font-medium">{product.color}</dd>
                  </>
                )}
                {product.condition && (
                  <>
                    <dt className="text-vz-ink-mute">État</dt>
                    <dd className="text-vz-ink font-medium">{conditionLabel}</dd>
                  </>
                )}
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

              {product.description && (
                <div className="mt-8 prose prose-sm max-w-none text-vz-ink-soft leading-relaxed">
                  <p>{product.description}</p>
                </div>
              )}

              {/* CTA desktop (le sticky mobile est plus bas) */}
              <div className="mt-8 hidden sm:flex flex-col sm:flex-row gap-3">
                {product.available ? (
                  <>
                    <Link
                      href={`/contact?subject=disponibilite%20${encodeURIComponent(product.slug)}`}
                      className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
                    >
                      Demander à la voir
                    </Link>
                    <a
                      href={`mailto:contact@vintiz.fr?subject=Disponibilit%C3%A9%20%E2%80%94%20${encodeURIComponent(
                        product.slug,
                      )}&body=Bonjour%2C%0A%0ACette%20pi%C3%A8ce%20est-elle%20toujours%20disponible%20%3A%20${encodeURIComponent(
                        (product.brand ?? "") + " — " + product.name,
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
              <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm">
                {product.brand && (
                  <Link
                    href={`/produits/marque/${brandSlug(product.brand)}`}
                    className="font-medium text-vz-teal underline underline-offset-4 hover:text-vz-teal-deep"
                  >
                    Voir plus de {product.brand} →
                  </Link>
                )}
                {product.category && (
                  <Link
                    href={`/produits?categorie=${product.category}`}
                    className="font-medium text-vz-teal underline underline-offset-4 hover:text-vz-teal-deep"
                  >
                    Toute la catégorie {categoryLabel} →
                  </Link>
                )}
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
            href={`/contact?subject=disponibilite%20${encodeURIComponent(product.slug)}`}
            className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-5 py-2.5 text-sm font-medium whitespace-nowrap"
          >
            Demander à la voir
          </Link>
        </div>
      )}

      <PublicFooter />
    </>
  );
}
