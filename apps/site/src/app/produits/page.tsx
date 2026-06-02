import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import ProductCard from "@/components/ProductCard";
import {
  listPublicProducts,
  listPublicCategories,
  type ApiProductCategory,
  PUBLIC_CATEGORY_LABELS,
} from "@/lib/storefront-api";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

// ISR — Next regenerates the page every 5 min. Stays static between
// regenerations so the page is hyper-rapide. A manager qui rétague un
// produit le voit remonter sur le site dans les 5 min, sans rebuild.
export const revalidate = 300;

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

export default async function ProduitsPage({ searchParams }: PageProps) {
  const requested = searchParams?.categorie?.toLowerCase();

  // Catalogue temps réel (API boutique) avec fallback démo. Pas de
  // pagination côté API → on filtre/trie côté serveur.
  const [products, categories] = await Promise.all([
    listPublicProducts(),
    listPublicCategories(),
  ]);

  const activeCategory: ApiProductCategory | null =
    requested && (Object.keys(PUBLIC_CATEGORY_LABELS) as string[]).includes(requested)
      ? (requested as ApiProductCategory)
      : null;

  const filtered = activeCategory
    ? products.filter((p) => p.category === activeCategory)
    : products;

  // Tri : disponibles d'abord, puis marque alphabétique
  const sorted = [...filtered].sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    return (a.brand || "").localeCompare(b.brand || "");
  });

  const itemListJsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: activeCategory
      ? `${PUBLIC_CATEGORY_LABELS[activeCategory]} seconde main premium — Vintiz Vernon`
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

  // Compte total pour le chip « Tout »
  const allCount = products.length;
  // Map des comptages (le fallback API a déjà calculé, sinon recompute
  // localement à partir de la liste qu'on a).
  const countMap = new Map<string, number>();
  for (const c of categories) countMap.set(c.key, c.count);
  if (countMap.size === 0) {
    for (const p of products) {
      if (!p.category) continue;
      countMap.set(p.category, (countMap.get(p.category) ?? 0) + 1);
    }
  }

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

          {/* Filtres catégorie — chips dynamiques basées sur les comptages API */}
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
              Tout ({allCount})
            </Link>
            {(Object.keys(PUBLIC_CATEGORY_LABELS) as ApiProductCategory[])
              .map((cat) => ({ cat, count: countMap.get(cat) ?? 0 }))
              .filter(({ count }) => count > 0)
              .map(({ cat, count }) => {
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
                    {PUBLIC_CATEGORY_LABELS[cat]} ({count})
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
