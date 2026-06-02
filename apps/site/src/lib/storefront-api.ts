/**
 * Public storefront API client (apps/site → apps/api).
 *
 * Données exposées par le router ``/api/storefront/*`` :
 *   - ``GET /products?categorie=...&marque=...`` → catalogue rayon
 *   - ``GET /products/<slug>``                   → fiche détail
 *   - ``GET /categories``                        → counts par bucket
 *
 * Toutes les pages produits passent par ces fonctions (ISR Next 5 min via
 * ``revalidate``). En cas d'API injoignable, on retombe sur le catalogue
 * statique ``data/vitrine-products.ts`` pour ne pas casser la page —
 * c'est le filet vitrine pré-ouverture.
 */
import { PRODUCTS as DEMO_PRODUCTS, type VitrineProduct } from "@/data/vitrine-products";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 5 minutes de cache ISR : un manager qui retag un produit le voit
// remonter sans rebuild ; le site reste hyper rapide entre deux mises
// à jour. À ajuster si nécessaire.
const REVALIDATE_SECONDS = 300;

export type ApiProductCategory =
  | "robe"
  | "veste"
  | "pantalon"
  | "pull"
  | "chemise"
  | "jupe"
  | "chaussures"
  | "sac"
  | "accessoire";

export interface ApiProduct {
  slug: string;
  name: string;
  brand: string | null;
  category: ApiProductCategory | null;
  category_label: string | null;
  size: string | null;
  color: string | null;
  condition: "excellent" | "tres-bon" | "bon" | null;
  price_eur: number;
  photo_url: string | null;
  available: boolean;
  description: string | null;
  retail_price_eur: number | null;
}

export interface ApiProductDetail extends ApiProduct {
  photos: string[];
  related: ApiProduct[];
}

export interface ApiCategoryCount {
  key: ApiProductCategory;
  label: string;
  count: number;
}

/**
 * Convertit une fiche démo (vitrine-products.ts) vers la forme API
 * publique. Permet d'utiliser le même code de rendu côté front que
 * l'API soit branchée ou non.
 */
function demoToApi(p: VitrineProduct): ApiProduct {
  return {
    slug: p.slug,
    name: p.name,
    brand: p.brand,
    category: p.category as ApiProductCategory,
    category_label: null,
    size: p.size,
    color: p.color,
    condition: p.condition,
    price_eur: p.price_eur,
    photo_url: null,
    available: p.available,
    description: p.description,
    retail_price_eur: p.retail_price_eur ?? null,
  };
}

export interface ListProductsOptions {
  categorie?: string;
  marque?: string;
}

/**
 * Liste publique. Retourne le catalogue boutique réel ; à défaut (API
 * KO ou catalogue vide), tombe sur le jeu de démonstration vitrine pour
 * garder la page utile.
 */
export async function listPublicProducts(
  opts: ListProductsOptions = {},
): Promise<ApiProduct[]> {
  const params = new URLSearchParams();
  if (opts.categorie) params.set("categorie", opts.categorie);
  if (opts.marque) params.set("marque", opts.marque);

  try {
    const res = await fetch(
      `${API_BASE}/api/storefront/products?${params.toString()}`,
      { next: { revalidate: REVALIDATE_SECONDS, tags: ["storefront-products"] } },
    );
    if (!res.ok) throw new Error(`storefront list failed: ${res.status}`);
    const data = (await res.json()) as ApiProduct[];
    if (Array.isArray(data) && data.length > 0) return data;
  } catch (err) {
    // Logged client-side only in dev — en prod on dégrade silencieusement.
    if (process.env.NODE_ENV !== "production") {
      console.warn("[storefront] fallback demo catalog:", err);
    }
  }
  // Fallback démo
  let demo = DEMO_PRODUCTS.map(demoToApi);
  if (opts.categorie) demo = demo.filter((p) => p.category === opts.categorie);
  if (opts.marque) {
    const m = opts.marque.toLowerCase();
    demo = demo.filter((p) => (p.brand || "").toLowerCase().includes(m));
  }
  return demo;
}

export async function getPublicProduct(
  slug: string,
): Promise<ApiProductDetail | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/storefront/products/${encodeURIComponent(slug)}`,
      { next: { revalidate: REVALIDATE_SECONDS, tags: [`storefront-product-${slug}`] } },
    );
    if (res.status === 404) {
      // 404 API : peut être un slug démo, on cherche dans le fallback.
      const demo = DEMO_PRODUCTS.find((p) => p.slug === slug);
      if (!demo) return null;
      return {
        ...demoToApi(demo),
        photos: [],
        related: DEMO_PRODUCTS
          .filter((p) => p.slug !== demo.slug && p.category === demo.category)
          .slice(0, 4)
          .map(demoToApi),
      };
    }
    if (!res.ok) throw new Error(`storefront detail failed: ${res.status}`);
    return (await res.json()) as ApiProductDetail;
  } catch (err) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("[storefront] product detail fallback:", err);
    }
    const demo = DEMO_PRODUCTS.find((p) => p.slug === slug);
    if (!demo) return null;
    return {
      ...demoToApi(demo),
      photos: [],
      related: DEMO_PRODUCTS
        .filter((p) => p.slug !== demo.slug && p.category === demo.category)
        .slice(0, 4)
        .map(demoToApi),
    };
  }
}

export async function listPublicCategories(): Promise<ApiCategoryCount[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/storefront/categories`,
      { next: { revalidate: REVALIDATE_SECONDS, tags: ["storefront-categories"] } },
    );
    if (!res.ok) throw new Error(`storefront categories failed: ${res.status}`);
    const data = (await res.json()) as { categories: ApiCategoryCount[] };
    return data.categories || [];
  } catch (err) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("[storefront] categories fallback:", err);
    }
    // Recompute counts from the demo set.
    const counts = new Map<ApiProductCategory, number>();
    for (const p of DEMO_PRODUCTS) {
      const key = p.category as ApiProductCategory;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return Array.from(counts.entries()).map(([key, count]) => ({
      key,
      label: PUBLIC_CATEGORY_LABELS[key],
      count,
    }));
  }
}

// Mêmes libellés que côté API (PUBLIC_CATEGORY_LABELS) pour le fallback.
export const PUBLIC_CATEGORY_LABELS: Record<ApiProductCategory, string> = {
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

export const PUBLIC_CONDITION_LABELS: Record<NonNullable<ApiProduct["condition"]>, string> = {
  excellent: "Excellent état",
  "tres-bon": "Très bon état",
  bon: "Bon état",
};

export function discountPercent(p: ApiProduct): number | null {
  if (!p.retail_price_eur || p.retail_price_eur <= p.price_eur) return null;
  return Math.round((1 - p.price_eur / p.retail_price_eur) * 100);
}
