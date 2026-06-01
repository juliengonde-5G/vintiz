/**
 * Informations légales centralisées (mentions légales + CGV).
 *
 * ⚠️ POINT UNIQUE À COMPLÉTER — remplacez chaque valeur `PLACEHOLDER`
 * (« À COMPLÉTER ») par la donnée réelle d'immatriculation. Tant qu'un champ
 * obligatoire reste à compléter, un bandeau « mentions provisoires » s'affiche
 * en haut des pages /mentions-legales et /cgv (voir LegalDraftNotice).
 *
 * Ces mentions sont obligatoires (LCEN art. 6-III, C. com. art. R123-237,
 * C. conso art. L612-1 pour le médiateur).
 */

export const LEGAL_PLACEHOLDER = "À COMPLÉTER";

export interface LegalMediator {
  name: string;
  url: string;
  address: string;
}

export interface LegalInfo {
  /** Nom commercial / dénomination affichée. */
  tradeName: string;
  /** Forme juridique : SAS, SARL, EI, micro-entreprise… */
  legalForm: string;
  /** Capital social (ex. « 10 000 € »). Laisser PLACEHOLDER si non-société. */
  capital: string;
  /** N° SIREN / SIRET. */
  siret: string;
  /** N° RCS + ville du greffe (ex. « RCS Évreux 123 456 789 »). */
  rcs: string;
  /** N° TVA intracommunautaire (si assujetti). */
  vatNumber: string;
  /** Directeur / responsable de la publication. */
  publicationDirector: string;
  /** Téléphone de contact. */
  phone: string;
  /** Email de contact. */
  email: string;
  /** Médiateur de la consommation désigné (obligatoire, art. L612-1). */
  mediator: LegalMediator;
}

// ───────────────────────────────────────────────────────────────────────────
// ▼▼▼ REMPLIR ICI ▼▼▼  (remplacez les LEGAL_PLACEHOLDER par les vraies valeurs)
// ───────────────────────────────────────────────────────────────────────────
export const LEGAL_INFO: LegalInfo = {
  tradeName: "Vintiz",
  legalForm: LEGAL_PLACEHOLDER,
  capital: LEGAL_PLACEHOLDER,
  siret: LEGAL_PLACEHOLDER,
  rcs: LEGAL_PLACEHOLDER,
  vatNumber: LEGAL_PLACEHOLDER,
  publicationDirector: LEGAL_PLACEHOLDER,
  phone: LEGAL_PLACEHOLDER,
  email: "contact@vintiz.fr",
  mediator: {
    name: LEGAL_PLACEHOLDER,
    url: LEGAL_PLACEHOLDER,
    address: LEGAL_PLACEHOLDER,
  },
};
// ───────────────────────────────────────────────────────────────────────────
// ▲▲▲ FIN DE LA ZONE À REMPLIR ▲▲▲
// ───────────────────────────────────────────────────────────────────────────

/** `true` si une valeur est encore le placeholder (donc à compléter). */
export function isPlaceholder(value: string): boolean {
  return !value || value.trim() === LEGAL_PLACEHOLDER;
}

/** Liste lisible des champs encore à renseigner (vide = tout est complété). */
export function legalMissingFields(info: LegalInfo = LEGAL_INFO): string[] {
  const missing: string[] = [];
  const checks: [string, string][] = [
    ["forme juridique", info.legalForm],
    ["capital social", info.capital],
    ["SIREN / SIRET", info.siret],
    ["RCS", info.rcs],
    ["N° TVA intracommunautaire", info.vatNumber],
    ["directeur de la publication", info.publicationDirector],
    ["téléphone", info.phone],
    ["médiateur de la consommation", info.mediator.name],
  ];
  for (const [label, value] of checks) {
    if (isPlaceholder(value)) missing.push(label);
  }
  return missing;
}

/** `true` quand toutes les mentions obligatoires sont renseignées. */
export const LEGAL_IS_COMPLETE = legalMissingFields().length === 0;

/** Affiche une valeur ou un libellé neutre si elle est encore en placeholder. */
export function legalValue(value: string): string {
  return isPlaceholder(value) ? LEGAL_PLACEHOLDER : value;
}
