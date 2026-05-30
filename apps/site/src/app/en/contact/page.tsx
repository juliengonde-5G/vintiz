import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Visit us — Vintiz Vernon",
  description:
    "Vintiz, premium second-hand boutique in Vernon, Normandy — 10 min from Giverny, 50 min by train from Paris Saint-Lazare. Address, hours, directions.",
  alternates: {
    canonical: `${SITE_URL}/en/contact`,
    languages: {
      "fr-FR": `${SITE_URL}/contact`,
      "en-US": `${SITE_URL}/en/contact`,
    },
  },
  openGraph: {
    title: "Visit us | Vintiz Vernon",
    description:
      "6 rue Saint-Jacques, 27200 Vernon. 10 min from Giverny, 50 min from Paris.",
    url: `${SITE_URL}/en/contact`,
    type: "website",
    locale: "en_US",
  },
};

const contactJsonLd = {
  "@context": "https://schema.org",
  "@type": "ContactPage",
  name: "Visit Vintiz Vernon",
  url: `${SITE_URL}/en/contact`,
  inLanguage: "en",
  mainEntity: {
    "@type": "ClothingStore",
    name: "Vintiz",
    url: SITE_URL,
    email: "contact@vintiz.fr",
    address: {
      "@type": "PostalAddress",
      streetAddress: "6 rue Saint-Jacques",
      addressLocality: "Vernon",
      postalCode: "27200",
      addressRegion: "Normandy",
      addressCountry: "FR",
    },
    geo: {
      "@type": "GeoCoordinates",
      latitude: 49.0926,
      longitude: 1.4773,
    },
    openingHoursSpecification: [
      {
        "@type": "OpeningHoursSpecification",
        dayOfWeek: [
          "Tuesday",
          "Wednesday",
          "Thursday",
          "Friday",
          "Saturday",
        ],
        opens: "10:30",
        closes: "19:00",
      },
    ],
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "customer service",
        email: "contact@vintiz.fr",
        areaServed: ["FR", "GB", "US", "DE", "BE", "NL"],
        availableLanguage: ["English", "French"],
      },
    ],
  },
};

export default function ContactEnPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(contactJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-6xl mx-auto px-6 py-16 lg:py-20">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Visit us
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Come see us in Vernon.
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Vintiz is in the heart of Vernon, 5 minutes on foot from the
            collegiate church and 10 minutes by car from Giverny. A
            question, a craving, or just to say hi — every reason is a
            good one.
          </p>

          <div className="mt-12 grid lg:grid-cols-2 gap-12 lg:gap-16">
            <div className="space-y-8">
              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Address
                </h2>
                <p className="text-vz-ink leading-relaxed">
                  6 rue Saint-Jacques
                  <br />
                  27200 Vernon — Normandy, France
                </p>
                <a
                  href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-vz-teal hover:underline"
                >
                  Directions on Google Maps
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
                </a>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Hours
                </h2>
                <p className="text-vz-ink leading-relaxed">
                  Tuesday to Saturday
                  <br />
                  10:30 AM — 7:00 PM
                </p>
                <p className="mt-2 text-sm text-vz-ink-mute">
                  Closed Sunday and Monday.
                </p>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Email us
                </h2>
                <p className="text-vz-ink">
                  <a
                    href="mailto:contact@vintiz.fr"
                    className="hover:text-vz-teal transition-colors"
                  >
                    contact@vintiz.fr
                  </a>
                </p>
                <p className="mt-2 text-sm text-vz-ink-mute">
                  Reply within 48 working hours. English welcome.
                </p>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  How to come
                </h2>
                <ul className="space-y-2 text-vz-ink leading-relaxed">
                  <li>
                    <span className="text-vz-ink-mute">From Giverny:</span>{" "}
                    ~10 min by car
                  </li>
                  <li>
                    <span className="text-vz-ink-mute">
                      From Paris Saint-Lazare:
                    </span>{" "}
                    Vernon-Giverny train station, ~50 min + 10 min on foot
                  </li>
                  <li>
                    <span className="text-vz-ink-mute">From Rouen:</span>{" "}
                    ~45 min by car (A13)
                  </li>
                  <li>
                    <span className="text-vz-ink-mute">From Paris CDG:</span>{" "}
                    ~1h15 by car
                  </li>
                </ul>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Follow us
                </h2>
                <div className="flex gap-3">
                  <a
                    href="https://www.instagram.com/vintiz.fr/"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Vintiz Instagram"
                    className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                    </svg>
                  </a>
                </div>
              </section>
            </div>

            <div className="space-y-6">
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Tourist-friendly
                </h2>
                <ul className="space-y-3 text-vz-ink-soft leading-relaxed">
                  <li className="flex gap-3">
                    <span className="text-vz-teal">→</span>
                    <span>
                      Curated French iconic brands — Sandro, Maje, Sézane,
                      Polène, IRO, Isabel Marant
                    </span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-vz-teal">→</span>
                    <span>
                      Authenticated, hand-checked premium second-hand
                    </span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-vz-teal">→</span>
                    <span>
                      AI personal shopper available in English
                    </span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-vz-teal">→</span>
                    <span>
                      We email you when a matching piece arrives
                    </span>
                  </li>
                </ul>
                <div className="mt-6 flex flex-col sm:flex-row gap-2">
                  <Link
                    href="/produits/made-in-france"
                    className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-6 py-2.5 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
                  >
                    Browse iconic brands
                  </Link>
                  <Link
                    href="/en/personal-shopper"
                    className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-6 py-2.5 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    AI Personal Shopper
                  </Link>
                </div>
              </div>

              <Link
                href="/contact"
                className="block text-center text-sm text-vz-teal hover:underline"
              >
                Lire en français
              </Link>
            </div>
          </div>
        </section>

        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-12">
            <h2 className="font-display text-2xl text-vz-ink mb-6">
              The boutique on the map
            </h2>
            <div className="aspect-[16/9] sm:aspect-[21/9] rounded-2xl overflow-hidden border border-black/5 bg-vz-surface shadow-sm">
              <iframe
                title="Vintiz — 6 rue Saint-Jacques, 27200 Vernon"
                src="https://www.openstreetmap.org/export/embed.html?bbox=1.4673%2C49.0876%2C1.4873%2C49.0976&layer=mapnik&marker=49.0926%2C1.4773"
                className="w-full h-full"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
            <p className="mt-3 text-xs text-vz-ink-mute">
              Map by OpenStreetMap (no third-party cookies).{" "}
              <a
                href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2 hover:text-vz-teal"
              >
                Open in Google Maps
              </a>
              .
            </p>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
