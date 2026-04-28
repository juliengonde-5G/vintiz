/**
 * Vintiz transaction history item (charte v2).
 *
 * One row of the espace client `/account/historique` list. Pure
 * presentational — wrap in <ul> on the consumer side.
 */

interface TransactionItem {
  name: string;
  quantity: number;
  line_total: number;
}

interface HistoryItemProps {
  transactionNumber: number;
  transactionType: "sale" | "refund" | string;
  totalTtc: number;
  /** ISO timestamp. */
  createdAt: string | null;
  items: TransactionItem[];
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function formatPrice(value: number): string {
  return value.toFixed(2).replace(".", ",") + " €";
}

export function HistoryItem({
  transactionNumber,
  transactionType,
  totalTtc,
  createdAt,
  items,
}: HistoryItemProps) {
  return (
    <li className="bg-white rounded-2xl shadow-sm p-4">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div>
          <p className="text-xs uppercase tracking-wider text-gray-500">
            {transactionType === "refund" ? "Retour" : "Achat"} #{transactionNumber}
          </p>
          <p className="text-sm text-gray-600">{formatDate(createdAt)}</p>
        </div>
        <p className="text-xl font-display font-semibold text-teal">
          {formatPrice(totalTtc)}
        </p>
      </div>
      {items.length > 0 && (
        <ul className="text-sm text-gray-600 space-y-0.5">
          {items.map((it, idx) => (
            <li key={idx} className="flex justify-between gap-3">
              <span className="truncate">
                {it.quantity} × {it.name}
              </span>
              <span className="shrink-0">{formatPrice(it.line_total)}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
