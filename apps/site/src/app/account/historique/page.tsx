"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TxItem {
  name: string;
  quantity: number;
  line_total: number;
}

interface Tx {
  id: string;
  transaction_number: number;
  transaction_type: string;
  total_ttc: number;
  created_at: string | null;
  items: TxItem[];
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export default function AccountHistoriquePage() {
  const [email, setEmail] = useState("");
  const [transactions, setTransactions] = useState<Tx[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("vintiz_account_email");
      if (stored) {
        setEmail(stored);
        void load(stored);
      }
    } catch {
      /* noop */
    }
  }, []);

  const load = async (target: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_URL}/api/crm/account/transactions?email=${encodeURIComponent(target)}`,
        { cache: "no-store" }
      );
      if (res.ok) {
        setTransactions(await res.json());
      } else if (res.status === 404) {
        setError("Aucun compte trouvé.");
      } else {
        setError("Erreur de chargement.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setLoading(false);
  };

  if (!email) {
    return (
      <AccountShell title="Mon historique">
        <Link href="/account/login" className="text-teal underline">Se connecter</Link>
      </AccountShell>
    );
  }

  return (
    <AccountShell
      title="Mon historique"
      intro="Vos achats et retours en boutique, du plus récent au plus ancien."
    >
      {loading && <p className="text-gray-500">Chargement…</p>}
      {error && <p className="text-red-700">{error}</p>}
      {!loading && transactions.length === 0 && !error && (
        <p className="text-gray-600">Aucun achat enregistré pour le moment.</p>
      )}
      <ul className="space-y-3">
        {transactions.map((tx) => (
          <li key={tx.id} className="bg-white rounded-2xl shadow-sm p-4">
            <div className="flex items-center justify-between gap-3 mb-2">
              <div>
                <p className="text-xs uppercase tracking-wider text-gray-500">
                  {tx.transaction_type === "refund" ? "Retour" : "Achat"} #{tx.transaction_number}
                </p>
                <p className="text-sm text-gray-600">{formatDate(tx.created_at)}</p>
              </div>
              <p className="text-xl font-display font-semibold text-teal">
                {tx.total_ttc.toFixed(2)} €
              </p>
            </div>
            {tx.items.length > 0 && (
              <ul className="text-sm text-gray-600 space-y-0.5">
                {tx.items.map((it, idx) => (
                  <li key={idx} className="flex justify-between gap-3">
                    <span className="truncate">
                      {it.quantity} × {it.name}
                    </span>
                    <span className="shrink-0">{it.line_total.toFixed(2)} €</span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </AccountShell>
  );
}
