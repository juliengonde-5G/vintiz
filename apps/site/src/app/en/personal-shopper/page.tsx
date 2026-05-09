import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "AI Personal Shopper — Vintiz Vernon",
  description:
    "AI-powered personal shopper for premium second-hand fashion in Vernon, France — 10 min from Giverny. Sandro, Maje, Sézane, Polène, IRO authenticated.",
  alternates: {
    canonical: `${SITE_URL}/en/personal-shopper`,
    languages: {
      "fr-FR": `${SITE_URL}/personal-shopper`,
      "en-US": `${SITE_URL}/en/personal-shopper`,
    },
  },
  openGraph: {
    title: "AI Personal Shopper | Vintiz Vernon",
    description:
      "Curated French second-hand premium fashion + AI personal shopping, 10 min from Giverny.",
    url: `${SITE_URL}/en/personal-shopper`,
    type: "website",
    locale: "en_US",
  },
};

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Vintiz AI Personal Shopper",
  serviceType: "Personal Shopping",
  description:
    "AI-powered personal shopping service for curated premium second-hand fashion in Vernon, France. Backed by Claude Haiku (Anthropic, EU hosting), opt-in only, GDPR-compliant.",
  provider: {
    "@type": "ClothingStore",
    name: "Vintiz",
    url: SITE_URL,
    address: {
      "@type": "PostalAddress",
      streetAddress: "6 rue Saint-Jacques",
      addressLocality: "Vernon",
      postalCode: "27200",
      addressRegion: "Normandy",
      addressCountry: "FR",
    },
  },
  areaServed: [
    { "@type": "City", name: "Vernon" },
    { "@type": "City", name: "Giverny" },
  ],
  inLanguage: ["en", "fr"],
  url: `${SITE_URL}/en/personal-shopper`,
};

export default function PersonalShopperEnPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-5xl mx-auto px-6 py-16 lg:py-24 text-center">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-4">
            AI Personal Shopper · Vernon, Normandy
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl lg:text-6xl text-vz-ink leading-tight tracking-[-0.015em]">
            Your stylist,
            <br />
            <em className="text-vz-teal not-italic">always on hand.</em>
          </h1>
          <p className="mt-8 text-lg sm:text-xl text-vz-ink-soft max-w-2xl mx-auto leading-relaxed">
            Visiting Giverny? Stop by Vintiz on your way. Our curated
            second-hand premium selection — Sandro, Maje, Sézane, Polène,
            IRO, Isabel Marant — paired with an AI personal shopper that
            learns your style.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/account/login"
              className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-8 py-3.5 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Activate my Personal Shopper
            </Link>
            <Link
              href="/produits/made-in-france"
              className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-8 py-3.5 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
            >
              Browse iconic French brands
            </Link>
          </div>
        </section>

        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20">
            <h2 className="font-display text-3xl sm:text-4xl text-vz-ink mb-12 text-center leading-tight">
              How it works
            </h2>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <div className="font-display text-5xl text-vz-teal/30 mb-4">
                  01
                </div>
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Tell us your style
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Sizes, colors you love, brands, budget, occasion. Two
                  minutes in your client account.
                </p>
              </div>
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <div className="font-display text-5xl text-vz-teal/30 mb-4">
                  02
                </div>
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Our AI cross-references
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Claude Haiku 4.5 (Anthropic, EU hosting) crosses your
                  preferences with our real in-store inventory. Narrative
                  recommendations, not just a list.
                </p>
              </div>
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <div className="font-display text-5xl text-vz-teal/30 mb-4">
                  03
                </div>
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Reserve and collect
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  24-48h reservation. Try in store at 6 rue Saint-Jacques.
                  Take what you love, leave what you don&apos;t. Zero
                  pressure.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="max-w-4xl mx-auto px-6 py-16 lg:py-20 text-center">
          <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight">
            Visit us
          </h2>
          <p className="mt-5 text-lg text-vz-ink-soft leading-relaxed">
            Vintiz, 6 rue Saint-Jacques, 27200 Vernon, Normandy, France.
            <br />
            Open Tuesday to Saturday, 10:30 AM — 7:00 PM.
          </p>
          <p className="mt-3 text-sm text-vz-ink-mute">
            10 min from Giverny · 50 min by train from Paris Saint-Lazare ·
            Tax-free shopping for non-EU residents.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              href="/contact"
              className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Contact &amp; directions
            </Link>
            <Link
              href="/personal-shopper"
              className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-7 py-3 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
            >
              Lire en français
            </Link>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
