import type { MetadataRoute } from 'next';
import { PRODUCTS } from '@/data/vitrine-products';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://vintiz.fr';

/**
 * Sitemap = uniquement les URLs publiques *indexables*. Les pages légales
 * (mentions, CGV, confidentialité) sont en `noindex` côté metadata, on
 * ne les soumet donc pas à Google — sinon signal contradictoire.
 *
 * Les fiches produit indisponibles sont aussi exclues : leur metadata
 * met `robots.index = false` quand `available === false`.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const homeLastModified = new Date('2026-05-08T00:00:00Z');
  const newPagesLastModified = new Date('2026-05-08T00:00:00Z');
  const productsLastModified = new Date('2026-05-08T00:00:00Z');

  const productEntries: MetadataRoute.Sitemap = PRODUCTS.filter(
    (p) => p.available,
  ).map((p) => ({
    url: `${SITE_URL}/produits/${p.slug}`,
    lastModified: productsLastModified,
    changeFrequency: 'weekly',
    priority: 0.6,
  }));

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
    ...productEntries,
  ];
}
