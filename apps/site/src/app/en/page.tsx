import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import {
  FRENCH_ICONIC_BRANDS,
  frenchIconicProducts,
} from "@/data/vitrine-products";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Vintiz Vernon — Premium second-hand French fashion, 10 min from Giverny",
  description:
    "Curated French second-hand premium boutique in Vernon, Normandy — 10 min from Giverny, 50 min from Paris. Sandro, Maje, Sézane, Polène, IRO, authenticated. AI Personal Shopper.",
  alternates: {
    canonical: `${SITE_URL}/en`,
    languages: {
      "fr-FR": SITE_URL,
      "en-US": `${SITE_URL}/en`,
    },
  },
  openGraph: {
    title: "Vintiz Vernon — Premium second-hand French fashion",
    description:
      "10 min from Giverny. Sandro, Maje, Sézane, Polène — authenticated. AI Personal Shopper.",
    url: `${SITE_URL}/en`,
    type: "website",
    locale: "en_US",
    images: [{ url: `${SITE_URL}/og-image.png`, width: 1200, height: 630 }],
  },
};

const homeJsonLd = {
  "@context": "https://schema.org",
  "@type": "ClothingStore",
  name: "Vintiz",
  url: SITE_URL,
  inLanguage: ["en", "fr"],
  description:
    "Premium second-hand boutique in Vernon, Normandy. Curated French iconic brands (Sandro, Maje, Sézane, Polène, IRO, Isabel Marant), AI personal shopper, partner of Solidarité Textiles. 10 min from Giverny.",
  address: {
    "@type": "PostalAddress",
    streetAddress: "6 rue Saint-Jacques",
    addressLocality: "Vernon",
    postalCode: "27200",
    addressRegion: "Normandy",
    addressCountry: "FR",
  },
  geo: { "@type": "GeoCoordinates", latitude: 49.0926, longitude: 1.4773 },
  openingHoursSpecification: [
    {
      "@type": "OpeningHoursSpecification",
      dayOfWeek: ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      opens: "10:30",
      closes: "19:00",
    },
  ],
  paymentAccepted: ["Cash", "Credit Card", "Debit Card"],
  currenciesAccepted: "EUR",
};

export default function HomeEnPage() {
  const featured = frenchIconicProducts()
    .filter((p) => p.available)
    .slice(0, 4);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(homeJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-5xl mx-auto px-6 py-16 lg:py-24 text-center">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-4">
            Premium second-hand · Vernon, Normandy · 10 min from Giverny
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl lg:text-6xl text-vz-ink leading-tight tracking-[-0.015em]">
            French iconic fashion,
            <br />
            <em className="text-vz-teal not-italic">a second life.</em>
          </h1>
          <p className="mt-8 text-lg sm:text-xl text-vz-ink-soft max-w-2xl mx-auto leading-relaxed">
            On your way to Giverny? Stop at Vintiz. Curated French second-hand
            premium — Sandro, Maje, Sézane, Polène, IRO, Isabel Marant —
            authenticated by hand, paired with an AI personal shopper that
            learns your style.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/produits/made-in-france"
              className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-8 py-3.5 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Browse iconic French brands
            </Link>
            <Link
              href="/en/personal-shopper"
              className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-8 py-3.5 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
            >
              Try the AI Personal Shopper
            </Link>
          </div>
        </section>

        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20">
            <h2 className="font-display text-3xl sm:text-4xl text-vz-ink mb-12 text-center leading-tight">
              Why visit Vintiz on your Giverny day-trip
            </h2>
            <div className="grid md:grid-cols-3 gap-8">
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Hand-picked French iconic brands
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  {Array.from(FRENCH_ICONIC_BRANDS).slice(0, 6).join(", ")} and
                  more — curated one piece at a time, authenticated by our
                  team in Vernon.
                </p>
              </div>
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  AI Personal Shopper, English-friendly
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Tell us your style, sizes, brands, budget. Our AI cross-
                  references with our real in-store inventory. Reserve your
                  pieces 24-48h before you arrive.
                </p>
              </div>
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Tax-free shopping
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Non-EU residents are eligible for VAT refund (20% on most
                  items). Just ask at the counter — we handle the paperwork
                  on the spot.
                </p>
              </div>
            </div>
          </div>
        </section>

        {featured.length > 0 && (
          <section className="max-w-7xl mx-auto px-6 py-16 lg:py-20">
            <div className="flex items-end justify-between mb-10">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-2">
                  In store this week
                </p>
                <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight">
                  A glimpse of what awaits
                </h2>
              </div>
              <Link
                href="/produits/made-in-france"
                className="hidden sm:inline-flex items-center gap-1 text-sm font-medium text-vz-teal hover:underline"
              >
                See all
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
              {featured.map((p) => (
                <Link
                  key={p.slug}
                  href={`/produits/${p.slug}`}
                  className="group block rounded-2xl bg-vz-surface border border-black/5 overflow-hidden hover:border-vz-teal/40 transition-colors"
                >
                  <div
                    className={`aspect-[3/4] ${p.swatch} flex items-end p-4`}
                  >
                    <span className="text-xs uppercase tracking-[0.14em] text-white/85 bg-black/20 px-2 py-1 rounded">
                      {p.brand}
                    </span>
                  </div>
                  <div className="p-4">
                    <h3 className="font-display text-base text-vz-ink leading-tight group-hover:text-vz-teal transition-colors line-clamp-2">
                      {p.name}
                    </h3>
                    <p className="mt-2 text-vz-teal font-medium">
                      €{p.price_eur}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-4xl mx-auto px-6 py-16 lg:py-20 text-center">
            <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight">
              How to come to Vernon
            </h2>
            <p className="mt-5 text-lg text-vz-ink-soft leading-relaxed">
              Vintiz, 6 rue Saint-Jacques, 27200 Vernon, Normandy.
              <br />
              Open Tuesday to Saturday, 10:30 AM — 7:00 PM.
            </p>
            <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl mx-auto text-vz-ink-soft text-sm">
              <li>
                <span className="text-vz-ink-mute">From Giverny:</span> ~10
                min by car
              </li>
              <li>
                <span className="text-vz-ink-mute">From Paris Saint-Lazare:</span>{" "}
                ~50 min by train + 10 min walk
              </li>
              <li>
                <span className="text-vz-ink-mute">From Rouen:</span> ~45 min
                by car (A13)
              </li>
              <li>
                <span className="text-vz-ink-mute">From CDG:</span> ~1h15 by
                car
              </li>
            </ul>
            <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                href="/en/contact"
                className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
              >
                Visit us
              </Link>
              <Link
                href="/en/a-propos"
                className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-7 py-3 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
              >
                Our story
              </Link>
              <Link
                href="/"
                className="inline-flex items-center justify-center rounded-full text-vz-ink-mute px-7 py-3 text-sm font-medium hover:text-vz-teal transition-colors"
              >
                Lire en français
              </Link>
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
