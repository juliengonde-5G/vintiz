/**
 * Description SumUp d'un paiement CB — détail du panier lisible côté SumUp.
 *
 * Quand un encaissement CB aboutit mais que la vente Vintiz n'est jamais
 * validée (vente « orpheline »), la seule trace côté SumUp est cette
 * description. En y mettant le détail des articles, le dashboard SumUp et
 * le reçu emailé suffisent à réconcilier l'encaissement. Bonus confiance
 * client : le libellé du reçu SumUp devient parlant.
 *
 * Format : `Vintiz 12,50€: 2x Robe Zara 8€; Sac cuir 5€`
 *   - préfixe "Vintiz" + total TTC (survit à toute troncature),
 *   - puis chaque ligne `qty x nom prix€` (qty omise si 1), séparées par "; ",
 *   - remise ligne → prix unitaire effectif affiché.
 *
 * Contrainte dure : le backend valide max_length=255 (CBInitiateRequest) et
 * SumUp tronque aussi. Si ça dépasse, on coupe au dernier article complet qui
 * tient et on ajoute `; +N art.` (résultat garanti ≤ 255). Texte simple
 * uniquement (pas d'emoji, espaces ASCII) — les accents sont OK.
 */

const MAX_LENGTH = 255;

/** Sous-ensemble de CartItem nécessaire au libellé — helper pur, testable. */
export interface DescriptionItem {
  name: string;
  price: number;
  quantity: number;
  /** Remise ligne en % (0 = aucune). */
  discount?: number;
}

/** "12,50" / "8" — virgule française, décimales omises si le montant est rond. */
function formatEuro(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  if (Number.isInteger(rounded)) return String(rounded);
  return rounded.toFixed(2).replace('.', ',');
}

/** Une ligne panier → `2x Robe Zara 8€` (qty omise si 1, prix effectif remisé). */
function itemLabel(item: DescriptionItem): string {
  const effectivePrice = item.price * (1 - (item.discount || 0) / 100);
  const name = item.name.replace(/\s+/g, ' ').trim();
  const qty = item.quantity > 1 ? `${item.quantity}x ` : '';
  return `${qty}${name} ${formatEuro(effectivePrice)}€`;
}

export function buildSumUpDescription(
  items: DescriptionItem[],
  total: number,
): string {
  const prefix = `Vintiz ${formatEuro(total)}€`;
  if (items.length === 0) return prefix;

  const labels = items.map(itemLabel);

  // Rend la description avec les ``shown`` premiers articles ; les suivants
  // sont résumés en `+N art.` pour que le total reste toujours visible.
  const render = (shown: number): string => {
    const rest = labels.length - shown;
    const parts = labels.slice(0, shown);
    if (rest > 0) parts.push(`+${rest} art.`);
    return `${prefix}: ${parts.join('; ')}`;
  };

  // Coupe au dernier article complet qui tient dans les 255 caractères.
  let shown = labels.length;
  while (shown > 0 && render(shown).length > MAX_LENGTH) shown--;
  const description = render(shown);
  // Cas pathologique (total ou résumé démesuré) : troncature brute en garde-fou.
  return description.length > MAX_LENGTH
    ? description.slice(0, MAX_LENGTH)
    : description;
}
