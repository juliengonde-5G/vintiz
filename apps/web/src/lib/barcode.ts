/**
 * Barcode scanner helpers — détection des mauvaises configurations.
 *
 * La douchette Inateck BCST-35 / 160B se présente en USB-HID (clavier).
 * Si elle est réglée en disposition US (QWERTY) alors que la tablette est
 * en FR (AZERTY), un code numérique comme « 1234567890 » est interprété
 * par l'OS comme la rangée des chiffres AZERTY, ce qui donne :
 *
 *     1 → &   2 → é   3 → "   4 → '   5 → (
 *     6 → -   7 → è   8 → _   9 → ç   0 → à
 *
 * Côté Vintiz on ne peut pas remapper après coup (l'OS livre déjà des
 * caractères imprimables, pas des scancodes). Mais on PEUT détecter la
 * mojibake et afficher à la caissière un message clair plutôt qu'un
 * « produit introuvable » trompeur.
 *
 * Heuristique : un vrai code-barres (EAN-13, UPC, Code 128 numérique) est
 * 100 % alphanumérique. Une chaîne layout-mismatch contient une majorité
 * de caractères spéciaux. Seuil à 50 % d'alphanumériques : tolère les
 * codes Code 128 contenant quelques séparateurs (`-`, `.`, `/`) tout en
 * attrapant les mojibakes purs.
 */

const ALPHANUMERIC_RE = /[A-Za-z0-9]/g;

const REMEDIATION =
  'Douchette en mauvaise disposition clavier (QWERTY au lieu d\'AZERTY). ' +
  'Scanne le code « French Keyboard » de la notice Inateck (BCST-35) ' +
  'pour la repasser en FR.';

/** Returns true when the input looks like mojibake produced by a
 *  keyboard-layout mismatch between the scanner and the OS. */
export function looksLikeScannerMojibake(raw: string): boolean {
  const s = raw ?? '';
  if (s.length < 3) return false;
  const alnum = (s.match(ALPHANUMERIC_RE) || []).length;
  return alnum / s.length < 0.5;
}

export const SCANNER_MOJIBAKE_MESSAGE = REMEDIATION;
