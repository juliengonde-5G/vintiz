import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ProductCard from "@/components/ProductCard";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { brandSlug } from "@/data/vitrine-products";
import {
  findBrandBySlugEn,
  listAvailableBrandsEn,
  productsByBrandEn,
} from "@/data/vitrine-products.en";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

interface PageProps {
  params: Promise<{ brand: string }>;
}

export function generateStaticParams() {
  return listAvailableBrandsEn().map((b) => ({ brand: brandSlug(b) }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { brand: brandParam } = await params;
  const brand = findBrandBySlugEn(brandParam);
  if (!brand) {
    return { title: "Brand not found", robots: { index: false } };
  }
  const products = productsByBrandEn(brand).filter((p) => p.available);
  return {
    title: `${brand} second-hand`,
    description: `Our authenticated second-hand ${brand} selection in Vernon — ${products.length} one-of-a-kind pieces. Dresses, jackets, bags and premium accessories curated by the Vintiz team.`,
    alternates: {
      canonical: `${SITE_URL}/en/produits/marque/${brandParam}`,
      languages: {
        "fr-FR": `${SITE_URL}/produits/marque/${brandParam}`,
        "en-US": `${SITE_URL}/en/produits/marque/${brandParam}`,
      },
    },
    openGraph: {
      title: `${brand} second-hand in Vernon | Vintiz`,
      description: `Authenticated second-hand ${brand} pieces, Vintiz Vernon selection.`,
      url: `${SITE_URL}/en/produits/marque/${brandParam}`,
      type: "website",
      locale: "en_US",
    },
  };
}

export default async function BrandEnPage({ params }: PageProps) {
  const { brand: brandParam } = await params;
  const brand = findBrandBySlugEn(brandParam);
  if (!brand) notFound();

  const products = productsByBrandEn(brand).sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  // Brand-targeted ItemList JSON-LD — the best signal for ranking on
  // "{brand} second-hand" / "{brand} pre-owned".
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${brand} premium second-hand — Vintiz Vernon`,
    description: `A selection of authenticated second-hand ${brand} pieces in Vernon, Normandy.`,
    url: `${SITE_URL}/en/produits/marque/${brandParam}`,
    inLanguage: "en",
    about: { "@type": "Brand", name: brand },
    hasPart: {
      "@type": "ItemList",
      numberOfItems: products.length,
      itemListElement: products.slice(0, 20).map((p, i) => ({
        "@type": "ListItem",
        position: i + 1,
        url: `${SITE_URL}/produits/${p.slug}`,
        name: `${p.brand} — ${p.name}`,
      })),
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-7xl mx-auto px-6 py-12 lg:py-16">
          <Link
            href="/en/produits"
            className="inline-flex items-center gap-1 text-xs uppercase tracking-[0.14em] text-vz-ink-mute hover:text-vz-teal mb-6"
          >
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
              <path d="M19 12H5M11 18l-6-6 6-6" />
            </svg>
            The whole shop
          </Link>

          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Brand
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            {brand}
            <br />
            <em className="text-vz-teal not-italic text-3xl sm:text-4xl">
              second-hand in Vernon.
            </em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Our authenticated second-hand {brand} selection — pieces curated
            by the Vintiz team from the premium deliveries sorted by
            Solidarité Textiles. A single unit per piece.
          </p>

          <div className="mt-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6">
            {products.map((p) => (
              <ProductCard key={p.slug} product={p} locale="en" />
            ))}
          </div>

          {products.length === 0 && (
            <p className="mt-10 text-vz-ink-mute">
              No {brand} pieces available right now. Sign up to the newsletter
              to be notified of our next deliveries.
            </p>
          )}

          <p className="mt-12 text-sm text-vz-ink-mute italic">
            <Link
              href={`/produits/marque/${brandParam}`}
              className="hover:text-vz-teal"
            >
              Lire en français
            </Link>
          </p>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
