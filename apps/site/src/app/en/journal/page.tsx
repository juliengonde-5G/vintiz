import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import { recentArticlesEn } from "@/data/journal-articles.en";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Vintiz Journal — premium second-hand in Vernon",
  description:
    "The Vintiz Vernon journal: authenticating iconic pieces, French labels second-hand, AI stylist tips — 10 min from Giverny.",
  alternates: {
    canonical: `${SITE_URL}/en/journal`,
    languages: {
      "fr-FR": `${SITE_URL}/journal`,
      "en-US": `${SITE_URL}/en/journal`,
    },
  },
  openGraph: {
    title: "Journal | Vintiz Vernon",
    description:
      "Vintiz editorial articles: iconic brands, authentication, circular fashion in Vernon.",
    url: `${SITE_URL}/en/journal`,
    type: "website",
    locale: "en_US",
  },
};

export default function JournalIndexEnPage() {
  const articles = recentArticlesEn();

  const blogJsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: "Vintiz Journal",
    url: `${SITE_URL}/en/journal`,
    inLanguage: "en",
    blogPost: articles.map((a) => ({
      "@type": "BlogPosting",
      headline: a.title,
      url: `${SITE_URL}/en/journal/${a.slug}`,
      datePublished: a.published_at,
      author: { "@type": "Organization", name: a.author },
    })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(blogJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-5xl mx-auto px-6 py-12 lg:py-16">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Journal
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            The Vintiz journal,
            <br />
            <em className="text-vz-teal not-italic">written by our team.</em>
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Authenticating iconic pieces, decoding French labels second-hand,
            stylist tips — one article a month, written in store in Vernon.
          </p>

          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {articles.map((a) => {
              const date = new Date(a.published_at).toLocaleDateString(
                "en-GB",
                { year: "numeric", month: "long", day: "numeric" },
              );
              return (
                <Link
                  key={a.slug}
                  href={`/en/journal/${a.slug}`}
                  className="group rounded-2xl bg-vz-surface border border-black/5 p-6 hover:border-vz-teal/40 transition-colors flex flex-col"
                >
                  <p className="text-xs uppercase tracking-[0.14em] text-vz-ink-mute mb-3">
                    {date} · {a.reading_minutes} min
                  </p>
                  <h2 className="font-display text-xl text-vz-ink leading-snug group-hover:text-vz-teal transition-colors">
                    {a.title}
                  </h2>
                  <p className="mt-3 text-vz-ink-soft leading-relaxed flex-1">
                    {a.excerpt}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {a.tags.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center rounded-full bg-vz-teal-soft text-vz-teal-deep px-3 py-1 text-xs font-medium"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </Link>
              );
            })}
          </div>

          {articles.length === 0 && (
            <p className="mt-10 text-vz-ink-mute">
              The journal is coming soon. The first article will appear in
              June 2026.
            </p>
          )}

          <p className="mt-12 text-sm text-vz-ink-mute italic">
            <Link href="/journal" className="hover:text-vz-teal">
              Lire en français
            </Link>
          </p>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
