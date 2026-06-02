import type { MetadataRoute } from 'next';
import { CAPSULES } from '@/data/capsules';
import { JOURNAL_ARTICLES } from '@/data/journal-articles';
import { brandSlug } from '@/data/vitrine-products';
import { listPublicProducts } from '@/lib/storefront-api';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://vintiz.fr';

// Sitemap régénéré toutes les 10 min — synchrone avec le cache produits
// (ISR 5 min) en gardant une marge pour Google qui ne re-fetch pas le
// sitemap aussi vite que ça.
export const revalidate = 600;

/**
 * Sitemap = uniquement les URLs publiques *indexables*. Les pages légales
 * (mentions, CGV, confidentialité) sont en `noindex` côté metadata, on
 * ne les soumet donc pas à Google — sinon signal contradictoire.
 *
 * Les fiches produit indisponibles sont aussi exclues : leur metadata
 * met `robots.index = false` quand `available === false`.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const homeLastModified = new Date('2026-05-08T00:00:00Z');
  const newPagesLastModified = new Date('2026-05-08T00:00:00Z');
  const productsLastModified = new Date();

  // On tire le catalogue de l'API publique : produits dispo + marques
  // observées dans le rayon réel. Si l'API tombe, le helper retombe sur
  // le dataset démo — donc le sitemap reste utilisable.
  const apiProducts = await listPublicProducts();
  const availableProducts = apiProducts.filter((p) => p.available);
  const brandsFromInventory = Array.from(
    new Set(
      availableProducts
        .map((p) => p.brand)
        .filter((b): b is string => Boolean(b)),
    ),
  );

  const productEntries: MetadataRoute.Sitemap = availableProducts.map((p) => ({
    url: `${SITE_URL}/produits/${p.slug}`,
    lastModified: productsLastModified,
    changeFrequency: 'weekly',
    priority: 0.6,
  }));

  const brandEntries: MetadataRoute.Sitemap = brandsFromInventory.map(
    (brand) => ({
      url: `${SITE_URL}/produits/marque/${brandSlug(brand)}`,
      lastModified: productsLastModified,
      changeFrequency: 'weekly',
      priority: 0.7,
    }),
  );

  // Miroir EN des pages marque (mêmes slugs de marque).
  const brandEntriesEn: MetadataRoute.Sitemap = brandsFromInventory.map(
    (brand) => ({
      url: `${SITE_URL}/en/produits/marque/${brandSlug(brand)}`,
      lastModified: productsLastModified,
      changeFrequency: 'weekly',
      priority: 0.65,
    }),
  );

  const capsuleEntries: MetadataRoute.Sitemap = CAPSULES.map((c) => ({
    url: `${SITE_URL}/capsules/${c.slug}`,
    lastModified: new Date(c.published_at),
    changeFrequency: 'monthly',
    priority: 0.7,
  }));

  // Miroir EN des capsules (slugs partagés avec le FR).
  const capsuleEntriesEn: MetadataRoute.Sitemap = CAPSULES.map((c) => ({
    url: `${SITE_URL}/en/capsules/${c.slug}`,
    lastModified: new Date(c.published_at),
    changeFrequency: 'monthly',
    priority: 0.65,
  }));

  const journalEntries: MetadataRoute.Sitemap = JOURNAL_ARTICLES.map((a) => ({
    url: `${SITE_URL}/journal/${a.slug}`,
    lastModified: new Date(a.published_at),
    changeFrequency: 'monthly',
    priority: 0.65,
  }));

  // Miroir EN des articles de journal (slugs partagés avec le FR).
  const journalEntriesEn: MetadataRoute.Sitemap = JOURNAL_ARTICLES.map(
    (a) => ({
      url: `${SITE_URL}/en/journal/${a.slug}`,
      lastModified: new Date(a.published_at),
      changeFrequency: 'monthly',
      priority: 0.6,
    }),
  );

  return [
    {
      url: `${SITE_URL}/`,
      lastModified: homeLastModified,
      changeFrequency: 'weekly',
      priority: 1.0,
    },
    {
      url: `${SITE_URL}/produits`,
      lastModified: productsLastModified,
      changeFrequency: 'weekly',
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/produits/made-in-france`,
      lastModified: productsLastModified,
      changeFrequency: 'weekly',
      priority: 0.85,
    },
    {
      url: `${SITE_URL}/personal-shopper`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/a-propos`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/contact`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/capsules`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/journal`,
      lastModified: newPagesLastModified,
      changeFrequency: 'weekly',
      priority: 0.75,
    },
    {
      url: `${SITE_URL}/en`,
      lastModified: newPagesLastModified,
      changeFrequency: 'weekly',
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/en/personal-shopper`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/en/a-propos`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/en/contact`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/en/produits`,
      lastModified: productsLastModified,
      changeFrequency: 'weekly',
      priority: 0.85,
    },
    {
      url: `${SITE_URL}/en/capsules`,
      lastModified: newPagesLastModified,
      changeFrequency: 'monthly',
      priority: 0.65,
    },
    {
      url: `${SITE_URL}/en/journal`,
      lastModified: newPagesLastModified,
      changeFrequency: 'weekly',
      priority: 0.7,
    },
    ...brandEntries,
    ...brandEntriesEn,
    ...capsuleEntries,
    ...capsuleEntriesEn,
    ...journalEntries,
    ...journalEntriesEn,
    ...productEntries,
  ];
}
