import type { Metadata } from "next";
import Link from "next/link";
import ProductCard from "@/components/ProductCard";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import {
  FRENCH_ICONIC_BRANDS,
  frenchIconicProducts,
} from "@/data/vitrine-products";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Made in France iconic — Vernon",
  description:
    "Sélection de marques françaises iconiques en seconde main premium à Vernon, à 10 minutes de Giverny. Sandro, Maje, Sézane, Polène, IRO, Isabel Marant.",
  alternates: { canonical: `${SITE_URL}/produits/made-in-france` },
  openGraph: {
    title: "Made in France iconic | Vintiz Vernon",
    description:
      "Iconic French fashion brands curated as second-hand premium in Vernon, 10 minutes from Giverny.",
    url: `${SITE_URL}/produits/made-in-france`,
    type: "website",
    locale: "fr_FR",
  },
};

export default function MadeInFrancePage() {
  const products = frenchIconicProducts().sort((a, b) => {
    if (a.available !== b.available) return a.available ? -1 : 1;
    return a.brand.localeCompare(b.brand);
  });

  return (
    <>
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-7xl mx-auto px-6 py-12 lg:py-16">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Sélection touriste · Made in France
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Iconic French Fashion,
            <br />
            <em className="text-vz-teal not-italic">second-hand premium.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            À 10 minutes de Giverny, retrouvez les marques françaises
            iconiques — Sandro, Maje, Sézane, Polène, IRO, Isabel Marant —
            curées par notre équipe à Vernon. Pièces uniques, état
            authentifié, prix justes.
          </p>

          <p className="mt-3 text-sm text-vz-ink-mute italic">
            Coming soon in English.
          </p>

          <div className="mt-8 flex flex-wrap gap-2">
            {Array.from(FRENCH_ICONIC_BRANDS).map((b) => (
              <Link
                key={b}
                href={`/produits/marque/${b
                  .toLowerCase()
                  .replace(/[&]/g, " ")
                  .replace(/[^a-z0-9]+/g, "-")
                  .replace(/^-+|-+$/g, "")}`}
                className="inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium bg-vz-surface border border-black/10 text-vz-ink hover:border-vz-teal/40 hover:text-vz-teal transition-colors"
              >
                {b}
              </Link>
            ))}
          </div>

          <div className="mt-12 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6">
            {products.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>

          {products.length === 0 && (
            <p className="mt-10 text-vz-ink-mute">
              Pas de pièces iconiques disponibles pour l&apos;instant.
            </p>
          )}
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
