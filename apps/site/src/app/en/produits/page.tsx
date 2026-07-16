import type { Metadata } from "next";
import Link from "next/link";
import ProductCard from "@/components/ProductCard";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { brandSlug, type ProductCategory } from "@/data/vitrine-products";
import {
  CATEGORY_LABEL_EN,
  FRENCH_ICONIC_BRANDS,
  PRODUCTS_EN,
} from "@/data/vitrine-products.en";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Shop — premium second-hand in Vernon | Vintiz",
  description:
    "Our selection of premium second-hand pieces in Vernon (10 min from Giverny). Sandro, Maje, Sézane, Ba&sh, IRO, Polène, Isabel Marant — one-of-a-kind, authenticated pieces.",
  alternates: {
    canonical: `${SITE_URL}/en/produits`,
    languages: {
      "fr-FR": `${SITE_URL}/produits`,
      "en-US": `${SITE_URL}/en/produits`,
    },
  },
  openGraph: {
    title: "Shop | Vintiz Vernon",
    description:
      "Our selection of premium second-hand pieces curated in Vernon, Normandy.",
    url: `${SITE_URL}/en/produits`,
    type: "website",
    locale: "en_US",
  },
};

interface PageProps {
  searchParams?: Promise<{ categorie?: string }>;
}

export default async function ProductsEnPage({ searchParams }: PageProps) {
  const query = await searchParams;
  const requested = query?.categorie?.toLowerCase();

  const allCategories = Array.from(
    new Set(PRODUCTS_EN.map((p) => p.category)),
  ) as ProductCategory[];
  const activeCategory: ProductCategory | null =
    requested && allCategories.includes(requested as ProductCategory)
      ? (requested as ProductCategory)
      : null;

  const filtered = activeCategory
    ? PRODUCTS_EN.filter((p) => p.category === activeCategory)
    : PRODUCTS_EN;

  // Sort: available first, then alphabetically by brand
  const sorted = [...filtered].sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    return a.brand.localeCompare(b.brand);
  });

  // ItemList JSON-LD — helps Google understand the nature of the page
  const itemListJsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: activeCategory
      ? `${CATEGORY_LABEL_EN[activeCategory]} premium second-hand — Vintiz Vernon`
      : "Vintiz shop — premium second-hand pieces",
    url: activeCategory
      ? `${SITE_URL}/en/produits?categorie=${activeCategory}`
      : `${SITE_URL}/en/produits`,
    inLanguage: "en",
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
            Shop
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Our selection
            <br />
            <em className="text-vz-teal not-italic">in Vernon.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Every piece below exists in a single copy and is waiting for you on
            rue Saint-Jacques. Spotted something you love? Email us to check
            it&apos;s still available, then come and try it on.
          </p>

          {/* Pre-opening placeholder notice */}
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
              Pre-opening preview. Final photographs of the pieces will go
              online by the boutique opening in September&nbsp;2026.{" "}
              <Link
                href="/#newsletter"
                className="underline underline-offset-2 hover:text-vz-teal"
              >
                Get notified
              </Link>
              .
            </p>
          </div>

          {/* Iconic French brand shortcuts */}
          <div className="mt-8 flex flex-wrap gap-2">
            {Array.from(FRENCH_ICONIC_BRANDS).map((b) => (
              <Link
                key={b}
                href={`/en/produits/marque/${brandSlug(b)}`}
                className="inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium bg-vz-surface border border-black/10 text-vz-ink hover:border-vz-teal/40 hover:text-vz-teal transition-colors"
              >
                {b}
              </Link>
            ))}
          </div>

          {/* Category filters */}
          <nav
            aria-label="Filter by category"
            className="mt-10 flex flex-wrap gap-2"
          >
            <Link
              href="/en/produits"
              className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                activeCategory === null
                  ? "bg-vz-teal text-white"
                  : "bg-vz-surface border border-black/10 text-vz-ink hover:border-vz-teal/40"
              }`}
            >
              All ({PRODUCTS_EN.length})
            </Link>
            {allCategories.map((cat) => {
              const count = PRODUCTS_EN.filter(
                (p) => p.category === cat,
              ).length;
              const active = cat === activeCategory;
              return (
                <Link
                  key={cat}
                  href={`/en/produits?categorie=${cat}`}
                  className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-vz-teal text-white"
                      : "bg-vz-surface border border-black/10 text-vz-ink hover:border-vz-teal/40"
                  }`}
                >
                  {CATEGORY_LABEL_EN[cat]} ({count})
                </Link>
              );
            })}
          </nav>

          {/* Product grid — 2 cols mobile, 3 tablet, 4 desktop */}
          <div className="mt-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6">
            {sorted.map((p) => (
              <ProductCard key={p.slug} product={p} locale="en" />
            ))}
          </div>

          {sorted.length === 0 && (
            <p className="mt-10 text-center text-vz-ink-mute">
              No pieces in this category right now.
            </p>
          )}

          <p className="mt-12 text-sm text-vz-ink-mute">
            A piece caught your eye?{" "}
            <Link
              href="/en/contact"
              className="underline underline-offset-2 hover:text-vz-teal"
            >
              Email us
            </Link>{" "}
            to check its availability, or come and see it directly at 6 rue
            Saint-Jacques.
          </p>

          <p className="mt-6 text-sm text-vz-ink-mute italic">
            <Link href="/produits" className="hover:text-vz-teal">
              Lire en français
            </Link>
          </p>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
