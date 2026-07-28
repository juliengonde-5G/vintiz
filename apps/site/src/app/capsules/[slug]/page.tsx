import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ProductCard from "@/components/ProductCard";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { CAPSULES, capsuleProducts, findCapsule } from "@/data/capsules";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export function generateStaticParams() {
  return CAPSULES.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const capsule = findCapsule(slug);
  if (!capsule) {
    return { title: "Capsule introuvable", robots: { index: false } };
  }
  return {
    title: capsule.title,
    description: `${capsule.tagline}. ${capsule.intro.slice(0, 100)}…`,
    alternates: {
      canonical: `${SITE_URL}/capsules/${capsule.slug}`,
      languages: {
        "fr-FR": `${SITE_URL}/capsules/${capsule.slug}`,
        "en-US": `${SITE_URL}/en/capsules/${capsule.slug}`,
      },
    },
    openGraph: {
      title: `${capsule.title} | Vintiz`,
      description: capsule.tagline,
      url: `${SITE_URL}/capsules/${capsule.slug}`,
      type: "article",
      locale: "fr_FR",
    },
  };
}

export default async function CapsulePage({ params }: PageProps) {
  const { slug } = await params;
  const capsule = findCapsule(slug);
  if (!capsule) notFound();

  const products = capsuleProducts(capsule);

  // JSON-LD : CollectionPage avec hasPart → ItemList
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: capsule.title,
    description: capsule.tagline,
    url: `${SITE_URL}/capsules/${capsule.slug}`,
    datePublished: capsule.published_at,
    hasPart: {
      "@type": "ItemList",
      numberOfItems: products.length,
      itemListElement: products.map((p, i) => ({
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
        <section className="max-w-4xl mx-auto px-6 py-12 lg:py-16">
          <Link
            href="/capsules"
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
            Toutes les capsules
          </Link>

          <p className="text-xs uppercase tracking-[0.14em] text-vz-ink-mute mb-3">
            {new Date(capsule.published_at).toLocaleDateString("fr-FR", {
              year: "numeric",
              month: "long",
            })}{" "}
            · {products.length} pièces
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            {capsule.title}
          </h1>
          <p className="mt-3 text-lg text-vz-teal font-medium">
            {capsule.tagline}
          </p>
          <div className="mt-8 prose prose-base max-w-none text-vz-ink-soft leading-relaxed">
            <p>{capsule.intro}</p>
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-6 pb-16">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 sm:gap-6">
            {products.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>
        </section>

        {capsule.outro && (
          <section className="bg-vz-bg-alt border-t border-black/5">
            <div className="max-w-3xl mx-auto px-6 py-12 text-center">
              <p className="text-lg text-vz-ink-soft leading-relaxed italic">
                {capsule.outro}
              </p>
              <Link
                href="/contact"
                className="mt-6 inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
              >
                Nous écrire
              </Link>
            </div>
          </section>
        )}
      </main>
      <PublicFooter />
    </>
  );
}
