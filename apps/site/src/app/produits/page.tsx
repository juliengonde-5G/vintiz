import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import ProductCard from "@/components/ProductCard";
import {
  CATEGORY_LABEL,
  PRODUCTS,
  type ProductCategory,
} from "@/data/vitrine-products";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Boutique",
  description:
    "Notre sélection de pièces seconde main premium à Vernon. Sandro, Maje, Sézane, Ba&sh, IRO, Polène, Isabel Marant — pièces uniques authentifiées.",
  alternates: { canonical: `${SITE_URL}/produits` },
  openGraph: {
    title: "Boutique | Vintiz Vernon",
    description:
      "Notre sélection de pièces seconde main premium curées à Vernon, Normandie.",
    url: `${SITE_URL}/produits`,
    type: "website",
    locale: "fr_FR",
  },
};

interface PageProps {
  searchParams?: { categorie?: string };
}

export default function ProduitsPage({ searchParams }: PageProps) {
  const requested = searchParams?.categorie?.toLowerCase();

  const allCategories = Array.from(
    new Set(PRODUCTS.map((p) => p.category)),
  ) as ProductCategory[];
  const activeCategory: ProductCategory | null =
    requested && allCategories.includes(requested as ProductCategory)
      ? (requested as ProductCategory)
      : null;

  const filtered = activeCategory
    ? PRODUCTS.filter((p) => p.category === activeCategory)
    : PRODUCTS;

  // Tri : disponibles d'abord, puis par marque alphabétique
  const sorted = [...filtered].sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    return a.brand.localeCompare(b.brand);
  });

  // JSON-LD ItemList — aide Google à comprendre la nature de la page
  const itemListJsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: activeCategory
      ? `${CATEGORY_LABEL[activeCategory]} seconde main premium — Vintiz Vernon`
      : "Boutique Vintiz — pièces seconde main premium",
    url: activeCategory
      ? `${SITE_URL}/produits?categorie=${activeCategory}`
      : `${SITE_URL}/produits`,
    numberOfItems: sorted.length,
    itemListElement: sorted.slice(0, 20).map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: `${p.brand} — ${p.name}`,
      url: `${SITE_URL}/produits/${p.slug}`,
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-7xl mx-auto px-6 py-12 lg:py-16">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Boutique
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Notre sélection
            <br />
            <em className="text-vz-teal not-italic">à Vernon.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Chaque pièce ci-dessous existe en un seul exemplaire et vous
            attend rue Saint-Jacques. Une pièce vous plaît ? Écrivez-nous pour
            vérifier qu&apos;elle est toujours disponible, puis passez l&apos;essayer.
          </p>

          {/* Notice placeholder pré-ouverture */}
          <div className="mt-6 inline-flex items-start gap-2 rounded-xl bg-vz-teal-soft/40 border border-vz-teal/20 px-4 py-3 text-sm text-vz-ink-soft max-w-2xl">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
              className="mt-0.5 shrink-0 text-vz-teal"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <p className="leading-relaxed">
              Aperçu pré-ouverture. Les photographies définitives des pièces
              seront mises en ligne d&apos;ici l&apos;ouverture boutique en
              septembre&nbsp;2026.{" "}
              <Link
                href="/#newsletter"
                className="underline underline-offset-2 hover:text-vz-teal"
              >
                Soyez prévenue
              </Link>
              .
            </p>
          </div>

          {/* Filtres catégorie */}
          <nav
            aria-label="Filtrer par catégorie"
            className="mt-10 flex flex-wrap gap-2"
          >
            <Link
              href="/produits"
              className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                activeCategory === null
                  ? "bg-vz-teal text-white"
                  : "bg-vz-surface border border-black/10 text-vz-ink hover:border-vz-teal/40"
              }`}
            >
              Tout ({PRODUCTS.length})
            </Link>
            {allCategories.map((cat) => {
              const count = PRODUCTS.filter((p) => p.category === cat).length;
              const active = cat === activeCategory;
              return (
                <Link
                  key={cat}
                  href={`/produits?categorie=${cat}`}
                  className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-vz-teal text-white"
                      : "bg-vz-surface border border-black/10 text-vz-ink hover:border-vz-teal/40"
                  }`}
                >
                  {CATEGORY_LABEL[cat]} ({count})
                </Link>
              );
            })}
          </nav>

          {/* Grille produits — 2 cols mobile, 3 tablet, 4 desktop */}
          <div className="mt-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6">
            {sorted.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>

          {sorted.length === 0 && (
            <p className="mt-10 text-center text-vz-ink-mute">
              Aucune pièce dans cette catégorie pour le moment.
            </p>
          )}

          <p className="mt-12 text-sm text-vz-ink-mute">
            Une pièce vous tape dans l&apos;œil ?{" "}
            <Link
              href="/contact"
              className="underline underline-offset-2 hover:text-vz-teal"
            >
              Écrivez-nous
            </Link>{" "}
            pour vérifier sa disponibilité, ou venez la voir directement au 6
            rue Saint-Jacques.
          </p>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
