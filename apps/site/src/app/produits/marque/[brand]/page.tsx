import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ProductCard from "@/components/ProductCard";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { brandSlug } from "@/data/vitrine-products";
import { listPublicProducts } from "@/lib/storefront-api";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

// ISR — même cache que /produits.
export const revalidate = 300;
export const dynamicParams = true;

interface PageProps {
  params: Promise<{ brand: string }>;
}

/**
 * Cherche le nom canonique d'une marque depuis un slug (« sandro »,
 * « ba-sh »). On itère sur le catalogue temps réel : si plusieurs
 * variations existent (« Sandro » vs « SANDRO »), la première
 * rencontrée gagne.
 */
async function resolveBrand(slug: string): Promise<string | null> {
  const products = await listPublicProducts();
  const wanted = slug.toLowerCase();
  for (const p of products) {
    if (p.brand && brandSlug(p.brand) === wanted) return p.brand;
  }
  return null;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { brand: brandParam } = await params;
  const brand = await resolveBrand(brandParam);
  if (!brand) {
    return { title: "Marque introuvable", robots: { index: false } };
  }
  const products = (await listPublicProducts({ marque: brand })).filter(
    (p) => p.available,
  );
  // URL canonique NORMALISÉE (brandSlug) — pas le segment brut reçu.
  // `/produits/marque/Sandro`, `/SANDRO`, `/sandro` rendent tous 200 :
  // sans normalisation, chacun se déclarait canonique de lui-même
  // → « page en double, Google a choisi une autre URL canonique » en GSC.
  const canonicalUrl = `${SITE_URL}/produits/marque/${brandSlug(brand)}`;
  return {
    title: `${brand} seconde main`,
    description: `Notre sélection ${brand} d'occasion authentifiée à Vernon — ${products.length} pièces uniques. Robes, vestes, sacs et accessoires premium curés par l'équipe Vintiz.`,
    alternates: {
      canonical: canonicalUrl,
      languages: {
        "fr-FR": canonicalUrl,
        "en-US": `${SITE_URL}/en/produits/marque/${brandSlug(brand)}`,
      },
    },
    openGraph: {
      title: `${brand} occasion à Vernon | Vintiz`,
      description: `Pièces ${brand} seconde main authentifiées, sélection Vintiz Vernon.`,
      url: canonicalUrl,
      type: "website",
      locale: "fr_FR",
    },
  };
}

export default async function BrandPage({ params }: PageProps) {
  const { brand: brandParam } = await params;
  const brand = await resolveBrand(brandParam);
  if (!brand) notFound();

  const products = (await listPublicProducts({ marque: brand })).sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${brand} seconde main premium — Vintiz Vernon`,
    description: `Sélection de pièces ${brand} d'occasion authentifiées à Vernon, Normandie.`,
    url: `${SITE_URL}/produits/marque/${brandSlug(brand)}`,
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
            href="/produits"
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
            Toute la boutique
          </Link>

          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Marque
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            {brand}
            <br />
            <em className="text-vz-teal not-italic text-3xl sm:text-4xl">
              seconde main à Vernon.
            </em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Notre sélection {brand} d&apos;occasion authentifiée — pièces
            curées par l&apos;équipe Vintiz parmi les arrivages premium
            triés par Solidarité Textiles. Une seule unité par pièce.
          </p>

          <div className="mt-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6">
            {products.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>

          {products.length === 0 && (
            <p className="mt-10 text-vz-ink-mute">
              Aucune pièce {brand} disponible pour le moment. Inscrivez-vous
              à la newsletter pour être prévenue de nos prochains arrivages.
            </p>
          )}
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
