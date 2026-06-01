/**
 * English copy mirror of the monthly "Vernon gems" capsules
 * (`capsules.ts`).
 *
 * Same `slug`, `published_at`, `month` and `product_slugs` as the French
 * source so shared URLs and hreflang line up — only `title`, `tagline` and
 * `intro`/`outro` are translated to English. Structure (which products belong
 * to a capsule) stays owned by the FR file via shared slugs.
 */

import { type VitrineProduct } from "./vitrine-products";
import { findProductEn } from "./vitrine-products.en";

export interface VitrineCapsuleEn {
  slug: string;
  title: string;
  tagline: string;
  published_at: string;
  month: string;
  intro: string;
  product_slugs: string[];
  outro?: string;
}

export const CAPSULES_EN: VitrineCapsuleEn[] = [
  {
    slug: "mai-2026",
    title: "The Vernon Gems — May 2026",
    tagline: "10 pieces curated for a slow-fashion spring",
    published_at: "2026-05-01T00:00:00Z",
    month: "2026-05",
    intro:
      "May in Vernon is all about flowing pieces, soft colours and blazers you fasten with a single careless button. Our team hand-picked 10 pieces from our April deliveries at Solidarité Textiles — each with its own character, its own label, and the smile of the team who sorted and cleaned it for you.",
    product_slugs: [
      "robe-sandro-noire-fluide-taille-38",
      "robe-sezane-fleurie-vintage-taille-m",
      "veste-maje-blazer-ecru-laine-taille-36",
      "pull-bash-cachemire-rose-poudre-taille-s",
      "chemise-vanessa-bruno-rayee-bleue-taille-38",
      "jupe-sezane-midi-camel-velours-taille-m",
      "veste-maje-tweed-rose-taille-36",
      "accessoire-sezane-foulard-soie-imprime",
      "sac-polene-numero-un-camel",
      "robe-isabel-marant-etoile-bohème-taille-38",
    ],
    outro:
      "Every one of these pieces exists in a single copy. Email us to check it's still available, then come and see it in store.",
  },
];

export function findCapsuleEn(slug: string): VitrineCapsuleEn | undefined {
  return CAPSULES_EN.find((c) => c.slug === slug);
}

export function currentCapsuleEn(): VitrineCapsuleEn | undefined {
  const sorted = [...CAPSULES_EN].sort((a, b) =>
    b.published_at.localeCompare(a.published_at),
  );
  return sorted[0];
}

export function capsuleProductsEn(c: VitrineCapsuleEn): VitrineProduct[] {
  return c.product_slugs
    .map((s) => findProductEn(s))
    .filter((p): p is VitrineProduct => p !== undefined);
}
