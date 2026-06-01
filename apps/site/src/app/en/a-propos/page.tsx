import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "About — Vintiz Vernon",
  description:
    "Vintiz, premium second-hand boutique in Vernon, Normandy — 10 min from Giverny. Curated French fashion, AI personal shopper, partnership with Solidarité Textiles.",
  alternates: {
    canonical: `${SITE_URL}/en/a-propos`,
    languages: {
      "fr-FR": `${SITE_URL}/a-propos`,
      "en-US": `${SITE_URL}/en/a-propos`,
    },
  },
  openGraph: {
    title: "About | Vintiz Vernon",
    description:
      "Curated French second-hand premium fashion in Vernon, 10 min from Giverny.",
    url: `${SITE_URL}/en/a-propos`,
    type: "website",
    locale: "en_US",
  },
};

const aboutJsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  name: "About Vintiz",
  url: `${SITE_URL}/en/a-propos`,
  inLanguage: "en",
  mainEntity: {
    "@type": "Organization",
    name: "Vintiz",
    url: SITE_URL,
    logo: `${SITE_URL}/logo-teal.png`,
    description:
      "Premium second-hand boutique in Vernon (Normandy, France). Curated iconic French brands, AI personal shopper, partner of Solidarité Textiles.",
    sameAs: [
      "https://www.instagram.com/vintiz.fr/",
      "https://www.facebook.com/vintiz.fr",
      "https://www.tiktok.com/@vintiz.fr",
    ],
  },
};

const ABOUT_FAQ_EN: { q: string; a: string }[] = [
  {
    q: "Where is the Vintiz boutique?",
    a: "At 6 rue Saint-Jacques, 27200 Vernon, Normandy — 10 minutes from Giverny. Open Tuesday to Saturday, 10:30am to 7pm.",
  },
  {
    q: "What exactly does Vintiz sell?",
    a: "Premium second-hand clothing, shoes and accessories, authenticated and curated piece by piece: iconic French brands (Sandro, Maje, Sézane, Ba&sh, IRO, Polène, Isabel Marant) and designers, in excellent condition.",
  },
  {
    q: "Where do the pieces come from?",
    a: "They are sourced through our partner Solidarité Textiles, a social-economy organisation. Every piece is sorted, checked and authenticated before going on the rails.",
  },
  {
    q: "Can I buy online?",
    a: "No. Vintiz is a physical boutique in Vernon. The website showcases the selection and the Personal Shopper prepares your visit, but purchases are made in store.",
  },
  {
    q: "How does the loyalty programme work?",
    a: "The card is fully digital (Apple Wallet / Google Wallet). You earn 1 point per euro spent; a voucher is generated automatically at each threshold. Sign-up happens in store.",
  },
];

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  inLanguage: "en",
  mainEntity: ABOUT_FAQ_EN.map((item) => ({
    "@type": "Question",
    name: item.q,
    acceptedAnswer: { "@type": "Answer", text: item.a },
  })),
};

export default function AboutEnPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(aboutJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-5xl mx-auto px-6 py-16 lg:py-24 text-center">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-4">
            About
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl lg:text-6xl text-vz-ink leading-tight tracking-[-0.015em]">
            Second-hand
            <br />
            <em className="text-vz-teal not-italic">that makes sense.</em>
          </h1>
          <p className="mt-8 text-lg sm:text-xl text-vz-ink-soft max-w-2xl mx-auto leading-relaxed">
            Vintiz was born from a simple idea: bring premium second-hand to
            Vernon, where every piece is chosen for its quality, its style,
            and its ability to live several lives.
          </p>
        </section>

        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20 grid lg:grid-cols-2 gap-12 lg:gap-16 items-start">
            <div>
              <h2 className="font-display text-3xl sm:text-4xl text-vz-teal leading-tight">
                Our concept
              </h2>
              <p className="mt-2 text-sm uppercase tracking-[0.14em] text-vz-ink-mute">
                Curated premium, never bulk
              </p>
            </div>
            <div className="space-y-5 text-vz-ink-soft text-lg leading-relaxed">
              <p>
                Vintiz is about consuming differently without giving up the
                pleasure of dressing with style. Every piece is hand-picked
                for its condition, brand, and cut. No bulk sorting — only
                ready-to-wear favorites.
              </p>
              <p>
                Our go-to brands: Sandro, Maje, Sézane, Ba&amp;sh, IRO,
                Polène, The Kooples, Vanessa Bruno, Isabel Marant — plus a
                few confidential gems to discover in store.
              </p>
              <p>
                All items are bought outright: no consignment, no middleman.
                The displayed price is fair, the stock is real, and the
                piece is waiting for you on rue Saint-Jacques.
              </p>
            </div>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-6 py-16 lg:py-20 grid lg:grid-cols-3 gap-8">
          <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
            <h3 className="font-display text-xl text-vz-ink mb-3">
              Rigorous curation
            </h3>
            <p className="text-vz-ink-soft leading-relaxed">
              Every piece passes through our hands before reaching the
              racks. Condition, brand, size, price — nothing left to
              chance.
            </p>
          </div>

          <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
            <h3 className="font-display text-xl text-vz-ink mb-3">
              AI Personal Shopper
            </h3>
            <p className="text-vz-ink-soft leading-relaxed">
              Our conversational AI analyzes your preferences and suggests a
              tailored selection from our real in-store inventory.
              Continuous learning loop, opt-in only, deactivable any time.
            </p>
            <Link
              href="/en/personal-shopper"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-vz-teal hover:underline"
            >
              Learn more
            </Link>
          </div>

          <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
            <h3 className="font-display text-xl text-vz-ink mb-3">
              Loyalty card
            </h3>
            <p className="text-vz-ink-soft leading-relaxed">
              €1 spent = 1 point. Three tiers (Bronze, Silver, Gold) with
              progressive perks. Virtual Apple Wallet and Google Wallet
              card, so you never forget it.
            </p>
          </div>
        </section>

        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
                Our partner
              </p>
              <h2 className="font-display text-3xl sm:text-4xl text-vz-teal leading-tight">
                Solidarité Textiles,
                <br />
                fashion that creates ties.
              </h2>
              <div className="mt-6 space-y-4 text-vz-ink-soft text-lg leading-relaxed">
                <p>
                  Our garments, shoes and accessories are sorted by our
                  partner <strong>Solidarité Textiles</strong>, a textile
                  sorting center based in Normandy.
                </p>
                <p>
                  Pieces are collected from drop-off bins across the Rouen
                  Normandie metropolitan area, then sorted by hand by
                  workers in social-reintegration programs. Vintiz then
                  picks up the premium selection to offer in store.
                </p>
                <p>
                  This is what lets us guarantee: a real circular economy,
                  supported local jobs, and full traceability of every
                  piece.
                </p>
              </div>
              <a
                href="https://solidaritetextiles.com"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 inline-flex items-center gap-2 rounded-full border border-vz-teal/40 px-6 py-3 text-sm font-medium text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
              >
                Discover Solidarité Textiles
              </a>
            </div>

            <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
              <h3 className="font-display text-xl text-vz-ink mb-5">
                Our commitments, in plain words
              </h3>
              <ul className="space-y-4 text-vz-ink leading-relaxed">
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Outright purchase.</strong> We buy our stock —
                    you don&apos;t wait to retrieve a deposit.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Traced sourcing</strong> via Solidarité Textiles
                    — work-based reintegration.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Non-resellable pieces</strong> redirected to
                    recycling/donation partners — never thrown away.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Annual impact report</strong>: kilos repurposed,
                    reuse rate, share remitted to Solidarité Textiles.
                    Published publicly from 2027.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* FAQ — factual answers (SEO + AI/SGE answer engines) */}
        <section className="max-w-3xl mx-auto px-6 py-16">
          <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight mb-8">
            Frequently asked questions
          </h2>
          <div className="space-y-6">
            {ABOUT_FAQ_EN.map((item) => (
              <div key={item.q}>
                <h3 className="font-display text-lg text-vz-ink mb-2">{item.q}</h3>
                <p className="text-vz-ink-soft leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="max-w-4xl mx-auto px-6 py-20 text-center">
          <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight">
            Want a preview?
          </h2>
          <p className="mt-5 text-lg text-vz-ink-soft leading-relaxed">
            Try our AI Personal Shopper, or come see us at 6 rue
            Saint-Jacques.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/en/personal-shopper"
              className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Discover the AI Personal Shopper
            </Link>
            <Link
              href="/a-propos"
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
