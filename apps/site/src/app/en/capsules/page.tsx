import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { CAPSULES_EN } from "@/data/capsules.en";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Capsules — The Vernon Gems",
  description:
    "Every month, an editorial selection curated by the Vintiz team from the premium pieces sorted by Solidarité Textiles in Vernon, Normandy.",
  alternates: {
    canonical: `${SITE_URL}/en/capsules`,
    languages: {
      "fr-FR": `${SITE_URL}/capsules`,
      "en-US": `${SITE_URL}/en/capsules`,
    },
  },
  openGraph: {
    title: "The Vernon Gems | Vintiz",
    description:
      "Monthly editorial selection of premium second-hand pieces curated in Vernon.",
    url: `${SITE_URL}/en/capsules`,
    type: "website",
    locale: "en_US",
  },
};

export default function CapsulesIndexEnPage() {
  const sorted = [...CAPSULES_EN].sort((a, b) =>
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
            The gems of
            <br />
            <em className="text-vz-teal not-italic">Vernon.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Every month, the Vintiz team curates an editorial selection from
            the premium pieces sorted by Solidarité Textiles — pieces chosen
            for their timelessness, their condition, or the story that comes
            with them.
          </p>

          <div className="mt-12 grid gap-8">
            {sorted.map((c) => (
              <Link
                key={c.slug}
                href={`/en/capsules/${c.slug}`}
                className="group block rounded-2xl border border-black/5 bg-vz-surface hover:border-vz-teal/30 transition-colors p-6 sm:p-8"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-vz-ink-mute mb-2">
                  {new Date(c.published_at).toLocaleDateString("en-GB", {
                    year: "numeric",
                    month: "long",
                  })}
                </p>
                <h2 className="font-display text-2xl sm:text-3xl text-vz-ink mb-2 group-hover:text-vz-teal transition-colors">
                  {c.title}
                </h2>
                <p className="text-vz-ink-soft">{c.tagline}</p>
                <p className="mt-3 text-sm text-vz-teal font-medium inline-flex items-center gap-1">
                  Discover the selection
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

          <p className="mt-12 text-sm text-vz-ink-mute italic">
            <Link href="/capsules" className="hover:text-vz-teal">
              Lire en français
            </Link>
          </p>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
