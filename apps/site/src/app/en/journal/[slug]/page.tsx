import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import {
  findArticleEn,
  JOURNAL_ARTICLES_EN,
  recentArticlesEn,
  type JournalArticleEn,
} from "@/data/journal-articles.en";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

interface PageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return JOURNAL_ARTICLES_EN.map((a) => ({ slug: a.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const article = findArticleEn(params.slug);
  if (!article) {
    return { title: "Article not found", robots: { index: false } };
  }
  return {
    title: article.title,
    description: article.excerpt.slice(0, 160),
    alternates: {
      canonical: `${SITE_URL}/en/journal/${article.slug}`,
      languages: {
        "fr-FR": `${SITE_URL}/journal/${article.slug}`,
        "en-US": `${SITE_URL}/en/journal/${article.slug}`,
      },
    },
    openGraph: {
      title: `${article.title} | Vintiz Journal`,
      description: article.excerpt,
      url: `${SITE_URL}/en/journal/${article.slug}`,
      type: "article",
      locale: "en_US",
      publishedTime: article.published_at,
      authors: [article.author],
    },
  };
}

/**
 * Lightweight in-house Markdown renderer — `## heading` (h2) plus paragraphs.
 * Inline `[text](url)` links are parsed without recursion (no nesting).
 * Mirrors the FR `journal/[slug]` renderer.
 */
function renderMarkdown(body: string) {
  const blocks = body.trim().split(/\n\n+/);
  return blocks.map((block, idx) => {
    if (block.startsWith("## ")) {
      return (
        <h2
          key={idx}
          className="font-display text-2xl sm:text-3xl text-vz-teal mt-12 mb-4 leading-tight"
        >
          {block.slice(3).trim()}
        </h2>
      );
    }
    return (
      <p
        key={idx}
        className="text-vz-ink-soft text-lg leading-relaxed mb-5"
      >
        {parseInline(block)}
      </p>
    );
  });
}

function parseInline(text: string): React.ReactNode[] {
  const linkRe = /\[([^\]]+)\]\(([^)]+)\)/g;
  const out: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  for (const m of Array.from(text.matchAll(linkRe))) {
    const start = m.index ?? 0;
    if (start > lastIndex) out.push(text.slice(lastIndex, start));
    const isExternal = m[2].startsWith("http");
    out.push(
      <Link
        key={key++}
        href={m[2]}
        className="text-vz-teal underline-offset-2 hover:underline"
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noopener noreferrer" : undefined}
      >
        {m[1]}
      </Link>,
    );
    lastIndex = start + m[0].length;
  }
  if (lastIndex < text.length) out.push(text.slice(lastIndex));
  return out;
}

export default function ArticleEnPage({ params }: PageProps) {
  const article = findArticleEn(params.slug);
  if (!article) notFound();

  const others = recentArticlesEn().filter(
    (a) => a.slug !== article.slug,
  ) as JournalArticleEn[];

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: article.title,
    description: article.excerpt,
    datePublished: article.published_at,
    dateModified: article.published_at,
    author: { "@type": "Organization", name: article.author },
    publisher: {
      "@type": "Organization",
      name: "Vintiz",
      logo: { "@type": "ImageObject", url: `${SITE_URL}/logo-teal.png` },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${SITE_URL}/en/journal/${article.slug}`,
    },
    keywords: article.tags.join(", "),
    inLanguage: "en",
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: `${SITE_URL}/en` },
      {
        "@type": "ListItem",
        position: 2,
        name: "Journal",
        item: `${SITE_URL}/en/journal`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: article.title,
        item: `${SITE_URL}/en/journal/${article.slug}`,
      },
    ],
  };

  const date = new Date(article.published_at).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <article className="max-w-3xl mx-auto px-6 py-12 lg:py-16">
          <Link
            href="/en/journal"
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
            All articles
          </Link>

          <p className="text-xs uppercase tracking-[0.14em] text-vz-ink-mute mb-3">
            {date} · {article.reading_minutes} min · {article.author}
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            {article.title}
          </h1>
          <p className="mt-5 text-lg text-vz-teal-deep leading-relaxed">
            {article.excerpt}
          </p>

          <div className="mt-8 flex flex-wrap gap-2">
            {article.tags.map((t) => (
              <span
                key={t}
                className="inline-flex items-center rounded-full bg-vz-teal-soft text-vz-teal-deep px-3 py-1 text-xs font-medium"
              >
                {t}
              </span>
            ))}
          </div>

          <div className="mt-10">{renderMarkdown(article.body)}</div>

          <div className="mt-16 pt-10 border-t border-black/5">
            <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-4">
              Keep reading
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              {others.slice(0, 2).map((a) => (
                <Link
                  key={a.slug}
                  href={`/en/journal/${a.slug}`}
                  className="group rounded-xl bg-vz-surface border border-black/5 p-5 hover:border-vz-teal/40 transition-colors"
                >
                  <h3 className="font-display text-lg text-vz-ink group-hover:text-vz-teal transition-colors">
                    {a.title}
                  </h3>
                  <p className="mt-2 text-sm text-vz-ink-soft leading-relaxed line-clamp-2">
                    {a.excerpt}
                  </p>
                </Link>
              ))}
            </div>
          </div>

          <p className="mt-12 text-sm text-vz-ink-mute italic">
            <Link
              href={`/journal/${article.slug}`}
              className="hover:text-vz-teal"
            >
              Lire en français
            </Link>
          </p>
        </article>
      </main>
      <PublicFooter />
    </>
  );
}
