import type { Metadata } from "next";
import Link from "next/link";
import ProductCard from "@/components/ProductCard";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import {
  FRENCH_ICONIC_BRANDS,
  brandSlug,
  frenchIconicProducts,
} from "@/data/vitrine-products";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Iconic French fashion, second-hand — Vintiz Vernon",
  description:
    "Curated French iconic brands, second-hand premium in Vernon (10 min from Giverny). Sandro, Maje, Sézane, Polène, IRO, Isabel Marant — authenticated by hand.",
  alternates: {
    canonical: `${SITE_URL}/en/produits`,
    languages: {
      "fr-FR": `${SITE_URL}/produits/made-in-france`,
      "en-US": `${SITE_URL}/en/produits`,
    },
  },
  openGraph: {
    title: "Iconic French fashion, second-hand | Vintiz Vernon",
    description:
      "Sandro, Maje, Sézane, Polène, IRO — premium second-hand in Vernon, 10 min from Giverny.",
    url: `${SITE_URL}/en/produits`,
    type: "website",
    locale: "en_US",
  },
};

export default function ProductsEnPage() {
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
            Tourist selection · Made in France
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Iconic French Fashion,
            <br />
            <em className="text-vz-teal not-italic">second-hand premium.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            10 min from Giverny, browse French iconic brands — Sandro, Maje,
            Sézane, Polène, IRO, Isabel Marant — curated by our Vernon team.
            One-of-a-kind pieces, authenticated condition, fair pricing.
          </p>

          <p className="mt-3 text-sm text-vz-ink-mute">
            Reserve any piece 24-48h before your visit by emailing
            contact@vintiz.fr or via the AI Personal Shopper.
          </p>

          <div className="mt-8 flex flex-wrap gap-2">
            {Array.from(FRENCH_ICONIC_BRANDS).map((b) => (
              <Link
                key={b}
                href={`/produits/marque/${brandSlug(b)}`}
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
              No iconic pieces available right now — check back next week.
            </p>
          )}

          <p className="mt-12 text-sm text-vz-ink-mute italic">
            <Link href="/produits/made-in-france" className="hover:text-vz-teal">
              Lire en français
            </Link>
          </p>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
