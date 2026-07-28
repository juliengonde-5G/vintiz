import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { CAPSULES } from "@/data/capsules";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Capsules — Les pépites de Vernon",
  description:
    "Chaque mois, une sélection éditoriale curée par l'équipe Vintiz parmi les arrivages premium de Solidarité Textiles.",
  alternates: {
    canonical: `${SITE_URL}/capsules`,
    languages: {
      "fr-FR": `${SITE_URL}/capsules`,
      "en-US": `${SITE_URL}/en/capsules`,
    },
  },
  openGraph: {
    title: "Les pépites de Vernon | Vintiz",
    description:
      "Sélection éditoriale mensuelle de pièces seconde main premium curées à Vernon.",
    url: `${SITE_URL}/capsules`,
    type: "website",
    locale: "fr_FR",
  },
};

export default function CapsulesIndexPage() {
  const sorted = [...CAPSULES].sort((a, b) =>
    b.published_at.localeCompare(a.published_at),
  );

  return (
    <>
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-5xl mx-auto px-6 py-12 lg:py-16">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Capsules
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Les pépites de
            <br />
            <em className="text-vz-teal not-italic">Vernon.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Chaque mois, l&apos;équipe Vintiz curé une sélection éditoriale
            parmi les arrivages premium triés par Solidarité Textiles —
            pièces choisies pour leur intemporalité, leur état, ou
            l&apos;histoire qui les accompagne.
          </p>

          <div className="mt-12 grid gap-8">
            {sorted.map((c) => (
              <Link
                key={c.slug}
                href={`/capsules/${c.slug}`}
                className="group block rounded-2xl border border-black/5 bg-vz-surface hover:border-vz-teal/30 transition-colors p-6 sm:p-8"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-vz-ink-mute mb-2">
                  {new Date(c.published_at).toLocaleDateString("fr-FR", {
                    year: "numeric",
                    month: "long",
                  })}
                </p>
                <h2 className="font-display text-2xl sm:text-3xl text-vz-ink mb-2 group-hover:text-vz-teal transition-colors">
                  {c.title}
                </h2>
                <p className="text-vz-ink-soft">{c.tagline}</p>
                <p className="mt-3 text-sm text-vz-teal font-medium inline-flex items-center gap-1">
                  Découvrir la sélection
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                  >
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </p>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
