/**
 * Catalogue VITRINE — 14 produits factices pour la page /produits avant
 * l'ouverture boutique (septembre 2026). Sera remplacé par un fetch
 * `/api/inventory/products?display=true` une fois le stock réel peuplé
 * + les photos pro shootées (cf. audit 3 §S7 + audit marketing M7).
 *
 * Marques choisies dans le sweet spot Vintiz (premium accessible, 50-300 €) :
 * Sandro, Maje, Sézane, Ba&sh, IRO, Polène, The Kooples, Vanessa Bruno,
 * Isabel Marant.
 */

export type ProductCategory =
  | "robe"
  | "veste"
  | "pantalon"
  | "pull"
  | "chemise"
  | "jupe"
  | "chaussures"
  | "sac"
  | "accessoire";

export type ProductCondition = "excellent" | "tres-bon" | "bon";

export interface VitrineProduct {
  slug: string;
  name: string;
  brand: string;
  category: ProductCategory;
  size: string;
  color: string;
  /** Couleur de fond de la card placeholder (Tailwind class). */
  swatch: string;
  condition: ProductCondition;
  price_eur: number;
  /** Prix neuf approximatif pour afficher la décote. */
  retail_price_eur?: number;
  description: string;
  /** False = vendu — la fiche reste accessible mais en `noindex`. */
  available: boolean;
}

/**
 * Marques françaises iconiques (audit TI4) — utilisées pour la
 * sélection touriste English-friendly + corner hôtels Giverny. La
 * propriété est dérivée du `brand` au runtime via `isFrenchIconic()`.
 */
export const FRENCH_ICONIC_BRANDS: ReadonlySet<string> = new Set([
  "Sandro",
  "Maje",
  "Sézane",
  "Ba&sh",
  "IRO",
  "Polène",
  "The Kooples",
  "Vanessa Bruno",
  "Isabel Marant",
  "Isabel Marant Étoile",
  "Le Tanneur",
  "A.P.C.",
  "Roseanna",
]);

export function isFrenchIconic(p: VitrineProduct): boolean {
  return FRENCH_ICONIC_BRANDS.has(p.brand);
}

export const CONDITION_LABEL: Record<ProductCondition, string> = {
  excellent: "Excellent état",
  "tres-bon": "Très bon état",
  bon: "Bon état",
};

export const CATEGORY_LABEL: Record<ProductCategory, string> = {
  robe: "Robes",
  veste: "Vestes",
  pantalon: "Pantalons",
  pull: "Pulls",
  chemise: "Chemises",
  jupe: "Jupes",
  chaussures: "Chaussures",
  sac: "Sacs",
  accessoire: "Accessoires",
};

export const PRODUCTS: VitrineProduct[] = [
  {
    slug: "robe-sandro-noire-fluide-taille-38",
    name: "Robe fluide noire ceinturée",
    brand: "Sandro",
    category: "robe",
    size: "38",
    color: "Noir",
    swatch: "bg-vz-ink",
    condition: "excellent",
    price_eur: 95,
    retail_price_eur: 285,
    description:
      "Robe mi-longue Sandro à coupe fluide, ceinture tressée en ton sur ton. Portée 2-3 fois, état impeccable. Parfaite saison printemps-été pour un déjeuner ou un dîner.",
    available: true,
  },
  {
    slug: "veste-maje-blazer-ecru-laine-taille-36",
    name: "Blazer écru en laine vierge",
    brand: "Maje",
    category: "veste",
    size: "36",
    color: "Écru",
    swatch: "bg-[#E8DCC4]",
    condition: "tres-bon",
    price_eur: 145,
    retail_price_eur: 395,
    description:
      "Blazer Maje structuré, laine vierge, doublé. Petite usure intérieure invisible portée. Le must-have demi-saison.",
    available: true,
  },
  {
    slug: "robe-sezane-fleurie-vintage-taille-m",
    name: "Robe fleurie collection Pascale",
    brand: "Sézane",
    category: "robe",
    size: "M",
    color: "Crème / fleurs roses",
    swatch: "bg-vz-accent-soft",
    condition: "excellent",
    price_eur: 75,
    retail_price_eur: 165,
    description:
      "Robe iconique Sézane, motif fleuri Pascale, manches courtes, col rond. Très peu portée. Coupe trapèze flatteuse.",
    available: true,
  },
  {
    slug: "sac-polene-numero-un-camel",
    name: "Sac N°1 — version mini",
    brand: "Polène",
    category: "sac",
    size: "Mini",
    color: "Camel",
    swatch: "bg-[#B68B5E]",
    condition: "tres-bon",
    price_eur: 220,
    retail_price_eur: 410,
    description:
      "Sac Polène N°1 mini en cuir camel, légère patine d'usage qui le rend encore plus beau. Deux compartiments, fermeture aimantée. Vendu sans dustbag.",
    available: true,
  },
  {
    slug: "veste-iro-perfecto-cuir-noir-taille-38",
    name: "Perfecto cuir agneau",
    brand: "IRO",
    category: "veste",
    size: "38",
    color: "Noir",
    swatch: "bg-black",
    condition: "tres-bon",
    price_eur: 285,
    retail_price_eur: 695,
    description:
      "Perfecto IRO en cuir d'agneau, coupe ajustée, zip argenté patiné. État cohérent avec un perfecto vintage : assoupli, rien de plus seyant.",
    available: true,
  },
  {
    slug: "pull-bash-cachemire-rose-poudre-taille-s",
    name: "Pull col rond cachemire",
    brand: "Ba&sh",
    category: "pull",
    size: "S",
    color: "Rose poudré",
    swatch: "bg-[#F4D9D5]",
    condition: "excellent",
    price_eur: 89,
    retail_price_eur: 235,
    description:
      "Pull Ba&sh en cachemire 100 %, col rond, manches longues. Lavé une fois en pressing. Tombé impeccable.",
    available: true,
  },
  {
    slug: "pantalon-kooples-tailleur-noir-taille-36",
    name: "Pantalon de tailleur droit",
    brand: "The Kooples",
    category: "pantalon",
    size: "36",
    color: "Noir",
    swatch: "bg-vz-ink-soft",
    condition: "excellent",
    price_eur: 65,
    retail_price_eur: 195,
    description:
      "Pantalon The Kooples coupe droite, taille mi-haute, plis marqués. Peu porté. Le passe-partout du dressing.",
    available: true,
  },
  {
    slug: "robe-isabel-marant-etoile-bohème-taille-38",
    name: "Robe Étoile broderies bohèmes",
    brand: "Isabel Marant Étoile",
    category: "robe",
    size: "38",
    color: "Blanc cassé",
    swatch: "bg-[#F1ECE0]",
    condition: "excellent",
    price_eur: 175,
    retail_price_eur: 385,
    description:
      "Robe Isabel Marant Étoile en coton brodé, manches longues, finitions volantées. Pièce iconique de la marque, état neuf.",
    available: true,
  },
  {
    slug: "chemise-vanessa-bruno-rayee-bleue-taille-38",
    name: "Chemise oversize rayée",
    brand: "Vanessa Bruno",
    category: "chemise",
    size: "38",
    color: "Bleu / blanc",
    swatch: "bg-[#C3D2E2]",
    condition: "tres-bon",
    price_eur: 55,
    retail_price_eur: 165,
    description:
      "Chemise Vanessa Bruno coton rayée, coupe oversize, poignets boutonnés. Petit accroc invisible côté manche, indiqué en boutique.",
    available: true,
  },
  {
    slug: "jupe-sezane-midi-camel-velours-taille-m",
    name: "Jupe midi en velours côtelé",
    brand: "Sézane",
    category: "jupe",
    size: "M",
    color: "Camel",
    swatch: "bg-[#A37449]",
    condition: "excellent",
    price_eur: 70,
    retail_price_eur: 145,
    description:
      "Jupe Sézane midi en velours côtelé camel, taille élastiquée derrière. Très peu portée, parfaite pour l'automne-hiver.",
    available: true,
  },
  {
    slug: "chaussures-sandro-mocassins-cuir-noir-taille-38",
    name: "Mocassins cuir noir",
    brand: "Sandro",
    category: "chaussures",
    size: "38",
    color: "Noir",
    swatch: "bg-[#1F1F1B]",
    condition: "tres-bon",
    price_eur: 110,
    retail_price_eur: 295,
    description:
      "Mocassins Sandro en cuir noir lisse, intérieur cuir, semelle en cuir patinée. Quelques marques d'usage sous la semelle, dessus impeccable.",
    available: true,
  },
  {
    slug: "veste-maje-tweed-rose-taille-36",
    name: "Veste tweed rose poudré",
    brand: "Maje",
    category: "veste",
    size: "36",
    color: "Rose poudré",
    swatch: "bg-vz-accent-soft",
    condition: "excellent",
    price_eur: 165,
    retail_price_eur: 425,
    description:
      "Veste Maje en tweed rose poudré, boutons dorés, doublure satin. Quasi neuve. Le coup de cœur du printemps.",
    available: true,
  },
  {
    slug: "sac-bash-baguette-cuir-noir",
    name: "Sac baguette cuir grainé",
    brand: "Ba&sh",
    category: "sac",
    size: "Standard",
    color: "Noir",
    swatch: "bg-vz-ink",
    condition: "tres-bon",
    price_eur: 95,
    retail_price_eur: 245,
    description:
      "Sac Ba&sh modèle baguette en cuir grainé, fermeture aimantée. Petite anse + bandoulière amovible. Patine légère cohérente.",
    available: false,
  },
  {
    slug: "accessoire-sezane-foulard-soie-imprime",
    name: "Foulard soie imprimé Pascale",
    brand: "Sézane",
    category: "accessoire",
    size: "Unique",
    color: "Multicolore",
    swatch: "bg-gradient-to-br from-[#E84E8B] to-[#F4D9D5]",
    condition: "excellent",
    price_eur: 35,
    retail_price_eur: 85,
    description:
      "Foulard Sézane 100 % soie imprimé collection Pascale, format 70×70 cm. État neuf, encore avec son écrin.",
    available: true,
  },
];

export function findProduct(slug: string): VitrineProduct | undefined {
  return PRODUCTS.find((p) => p.slug === slug);
}

export function relatedProducts(
  current: VitrineProduct,
  limit = 3,
): VitrineProduct[] {
  return PRODUCTS.filter(
    (p) =>
      p.slug !== current.slug &&
      p.available &&
      (p.brand === current.brand || p.category === current.category),
  ).slice(0, limit);
}

export function discountPercent(p: VitrineProduct): number | null {
  if (!p.retail_price_eur || p.retail_price_eur <= p.price_eur) return null;
  return Math.round((1 - p.price_eur / p.retail_price_eur) * 100);
}

/**
 * Slug URL-safe à partir d'un nom de marque ("Ba&sh" → "ba-sh").
 * Utilisé par les pages `/produits/marque/[brand]` (audit S16).
 */
export function brandSlug(brand: string): string {
  return brand
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[&]/g, " ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function findBrandBySlug(slug: string): string | undefined {
  const wanted = slug.toLowerCase();
  for (const p of PRODUCTS) {
    if (brandSlug(p.brand) === wanted) return p.brand;
  }
  return undefined;
}

export function listAvailableBrands(): string[] {
  const seen = new Set<string>();
  for (const p of PRODUCTS) {
    if (p.available) seen.add(p.brand);
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b));
}

export function productsByBrand(brand: string): VitrineProduct[] {
  return PRODUCTS.filter((p) => p.brand === brand);
}

export function frenchIconicProducts(): VitrineProduct[] {
  return PRODUCTS.filter(isFrenchIconic);
}
