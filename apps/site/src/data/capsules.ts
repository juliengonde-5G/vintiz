/**
 * Capsules mensuelles « Les pépites de Vernon » (audit O9).
 *
 * Chaque capsule = sélection éditoriale curée par l'équipe Vintiz pour
 * le mois en cours, mise en avant publiquement comme un mini-événement.
 * Inspiration : modèle Imparfaite « les perles du mois ».
 *
 * Structure éditable côté repo (no-DB) — quand un PR ajoute une capsule
 * pour le mois suivant, le site la sert automatiquement à la date prévue.
 */

import { type VitrineProduct, findProduct } from "./vitrine-products";

export interface VitrineCapsule {
  /** Slug pour URL : ex. "mai-2026". */
  slug: string;
  /** Titre éditorial. */
  title: string;
  /** Sous-titre / accroche. */
  tagline: string;
  /** Date de publication (ISO 8601). */
  published_at: string;
  /** Mois éditorial (YYYY-MM). */
  month: string;
  /** Texte éditorial — 2-4 paragraphes. */
  intro: string;
  /** Liste des slugs produits inclus dans la capsule. */
  product_slugs: string[];
  /** Clôture éditoriale. */
  outro?: string;
}

export const CAPSULES: VitrineCapsule[] = [
  {
    slug: "mai-2026",
    title: "Les pépites de Vernon — Mai 2026",
    tagline: "10 pièces curées pour le printemps Slow Fashion",
    published_at: "2026-05-01T00:00:00Z",
    month: "2026-05",
    intro:
      "Mai à Vernon, c'est l'envie de pièces fluides, de couleurs douces et de blazers qu'on attache d'un bouton négligent. Notre équipe a sélectionné 10 pièces parmi nos arrivages d'avril chez Solidarité Textiles — chacune avec son propre caractère, sa marque, et le sourire de l'équipe qui l'a triée et nettoyée pour vous.",
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
      "Toutes ces pièces existent en un seul exemplaire. Réservation 24-48h possible avant votre passage en boutique — il suffit de nous écrire.",
  },
];

export function findCapsule(slug: string): VitrineCapsule | undefined {
  return CAPSULES.find((c) => c.slug === slug);
}

export function currentCapsule(): VitrineCapsule | undefined {
  // Capsule la plus récente, par date publication descendante
  const sorted = [...CAPSULES].sort((a, b) =>
    b.published_at.localeCompare(a.published_at),
  );
  return sorted[0];
}

export function capsuleProducts(c: VitrineCapsule): VitrineProduct[] {
  return c.product_slugs
    .map((s) => findProduct(s))
    .filter((p): p is VitrineProduct => p !== undefined);
}
