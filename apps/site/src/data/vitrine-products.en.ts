/**
 * English translations of the VITRINE catalogue (`vitrine-products.ts`).
 *
 * Same shape, same slugs, same prices/images/brand/available flags — only
 * the human-readable `name`, `description` and `color` are translated to
 * English. The FR file remains the single source of truth for structure
 * (slugs, swatches, pricing); this file is a thin locale overlay consumed
 * by the `/en/*` pages.
 *
 * We re-export the helper functions against the EN dataset so the EN pages
 * mirror the FR ones one-to-one.
 */

import {
  FRENCH_ICONIC_BRANDS,
  PRODUCTS as FR_PRODUCTS,
  type ProductCategory,
  type ProductCondition,
  type VitrineProduct,
  brandSlug,
  discountPercent,
  isFrenchIconic,
} from "./vitrine-products";

export { FRENCH_ICONIC_BRANDS, brandSlug, discountPercent, isFrenchIconic };
export type { ProductCategory, ProductCondition, VitrineProduct };

export const CONDITION_LABEL_EN: Record<ProductCondition, string> = {
  excellent: "Excellent condition",
  "tres-bon": "Very good condition",
  bon: "Good condition",
};

export const CATEGORY_LABEL_EN: Record<ProductCategory, string> = {
  robe: "Dresses",
  veste: "Jackets",
  pantalon: "Trousers",
  pull: "Knitwear",
  chemise: "Shirts",
  jupe: "Skirts",
  chaussures: "Shoes",
  sac: "Bags",
  accessoire: "Accessories",
};

/**
 * Per-slug English overrides for the free-text fields. Anything not listed
 * here falls back to the FR value (defensive: a new FR product still renders).
 */
interface ProductEnOverride {
  name: string;
  color: string;
  description: string;
}

const EN_OVERRIDES: Record<string, ProductEnOverride> = {
  "robe-sandro-noire-fluide-taille-38": {
    name: "Black belted flowing dress",
    color: "Black",
    description:
      "Sandro midi dress with a fluid cut and a tonal braided belt. Worn two or three times, in flawless condition. A perfect spring-summer piece for lunch or dinner.",
  },
  "veste-maje-blazer-ecru-laine-taille-36": {
    name: "Ecru virgin-wool blazer",
    color: "Ecru",
    description:
      "Structured Maje blazer in virgin wool, fully lined. Minor inner wear, invisible when worn. The mid-season must-have.",
  },
  "robe-sezane-fleurie-vintage-taille-m": {
    name: "Pascale collection floral dress",
    color: "Cream / pink florals",
    description:
      "Iconic Sézane dress with the Pascale floral print, short sleeves and a round neck. Barely worn. A flattering A-line cut.",
  },
  "sac-polene-numero-un-camel": {
    name: "Numéro Un bag — mini version",
    color: "Camel",
    description:
      "Polène Numéro Un mini in camel leather, with a light patina from use that only makes it more beautiful. Two compartments, magnetic closure. Sold without dustbag.",
  },
  "veste-iro-perfecto-cuir-noir-taille-38": {
    name: "Lambskin biker jacket",
    color: "Black",
    description:
      "IRO biker jacket in lambskin, fitted cut, with patinated silver zips. Condition in keeping with a vintage biker jacket: beautifully broken in, nothing more flattering.",
  },
  "pull-bash-cachemire-rose-poudre-taille-s": {
    name: "Round-neck cashmere jumper",
    color: "Powder pink",
    description:
      "Ba&sh jumper in 100% cashmere, round neck, long sleeves. Dry-cleaned once. Falls beautifully.",
  },
  "pantalon-kooples-tailleur-noir-taille-36": {
    name: "Straight-leg tailored trousers",
    color: "Black",
    description:
      "The Kooples straight-cut trousers, mid-high waist, with sharp creases. Lightly worn. The wardrobe staple that goes with everything.",
  },
  "robe-isabel-marant-etoile-bohème-taille-38": {
    name: "Étoile bohemian embroidered dress",
    color: "Off-white",
    description:
      "Isabel Marant Étoile dress in embroidered cotton, long sleeves, with ruffled finishes. An iconic piece from the label, in as-new condition.",
  },
  "chemise-vanessa-bruno-rayee-bleue-taille-38": {
    name: "Striped oversize shirt",
    color: "Blue / white",
    description:
      "Vanessa Bruno striped cotton shirt, oversize cut, buttoned cuffs. A small invisible snag on the sleeve, flagged in store.",
  },
  "jupe-sezane-midi-camel-velours-taille-m": {
    name: "Corduroy midi skirt",
    color: "Camel",
    description:
      "Sézane midi skirt in camel corduroy, with an elasticated back waist. Barely worn, perfect for autumn-winter.",
  },
  "chaussures-sandro-mocassins-cuir-noir-taille-38": {
    name: "Black leather loafers",
    color: "Black",
    description:
      "Sandro loafers in smooth black leather, leather lining, patinated leather sole. A few wear marks under the sole, uppers in flawless condition.",
  },
  "veste-maje-tweed-rose-taille-36": {
    name: "Powder-pink tweed jacket",
    color: "Powder pink",
    description:
      "Maje jacket in powder-pink tweed, gold buttons, satin lining. Almost new. The favourite of the season.",
  },
  "sac-bash-baguette-cuir-noir": {
    name: "Grained-leather baguette bag",
    color: "Black",
    description:
      "Ba&sh baguette bag in grained leather, magnetic closure. Short handle plus a detachable shoulder strap. A light, even patina.",
  },
  "accessoire-sezane-foulard-soie-imprime": {
    name: "Pascale printed silk scarf",
    color: "Multicolour",
    description:
      "Sézane scarf in 100% silk with the Pascale collection print, 70×70 cm. As-new condition, still in its gift box.",
  },
};

/**
 * EN view of the catalogue: structural fields untouched, free text swapped
 * to English (falling back to the FR value when an override is missing).
 */
export const PRODUCTS_EN: VitrineProduct[] = FR_PRODUCTS.map((p) => {
  const override = EN_OVERRIDES[p.slug];
  if (!override) return p;
  return {
    ...p,
    name: override.name,
    color: override.color,
    description: override.description,
  };
});

export function findProductEn(slug: string): VitrineProduct | undefined {
  return PRODUCTS_EN.find((p) => p.slug === slug);
}

export function frenchIconicProductsEn(): VitrineProduct[] {
  return PRODUCTS_EN.filter(isFrenchIconic);
}

export function listAvailableBrandsEn(): string[] {
  const seen = new Set<string>();
  for (const p of PRODUCTS_EN) {
    if (p.available) seen.add(p.brand);
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b));
}

export function findBrandBySlugEn(slug: string): string | undefined {
  const wanted = slug.toLowerCase();
  for (const p of PRODUCTS_EN) {
    if (brandSlug(p.brand) === wanted) return p.brand;
  }
  return undefined;
}

export function productsByBrandEn(brand: string): VitrineProduct[] {
  return PRODUCTS_EN.filter((p) => p.brand === brand);
}
