"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";
import { accountFetch } from "@/lib/account-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Coupon {
  code: string;
  discount_type: string;
  discount_value: number;
  source: string | null;
  valid_until: string | null;
  expired: boolean;
  notes: string | null;
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
}

function formatDiscount(c: Coupon): string {
  if (c.discount_type === "amount") return `-${c.discount_value.toFixed(0)} €`;
  if (c.discount_type === "percent") return `-${c.discount_value.toFixed(0)} %`;
  return `${c.discount_value}`;
}

const SOURCE_LABELS: Record<string, string> = {
  loyalty_milestone: "Palier fidélité",
  anniversary: "Anniversaire",
  manual: "Cadeau boutique",
  campaign: "Opération en cours",
};

export default function AccountOffresPage() {
  const [email, setEmail] = useState("");
  const [coupons, setCoupons] = useState<Coupon[]>([]);
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
      const res = await accountFetch(
        `${API_URL}/api/crm/account/coupons?email=${encodeURIComponent(target)}`,
        { cache: "no-store" }
      );
      if (res.ok) {
        setCoupons(await res.json());
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
      <AccountShell title="Mes offres">
        <Link href="/account/login" className="text-vz-teal underline">Se connecter</Link>
      </AccountShell>
    );
  }

  return (
    <AccountShell
      title="Mes offres"
      intro="Coupons actifs sur votre compte. Ils s'appliquent automatiquement au prochain passage en caisse."
    >
      {loading && <p className="text-gray-500">Chargement…</p>}
      {error && <p className="text-red-700">{error}</p>}
      {!loading && !error && coupons.length === 0 && (
        <p className="text-gray-600">
          Aucun coupon actif pour le moment. Cumulez 100 points sur votre carte
          fidélité pour générer un chèque cadeau de 5 € automatique.
        </p>
      )}
      {coupons.length > 0 && (
        <ul className="space-y-3">
          {coupons.map((c) => (
            <li
              key={c.code}
              className={
                "bg-white rounded-2xl shadow-sm p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 " +
                (c.expired ? "opacity-50" : "")
              }
            >
              <div>
                <p className="text-xs uppercase tracking-wider text-gray-500">
                  {SOURCE_LABELS[c.source ?? ""] ?? "Coupon"}
                </p>
                <p className="text-2xl font-display font-semibold text-vz-teal mt-1">
                  {formatDiscount(c)}
                </p>
                <p className="text-sm text-gray-600">
                  Code <strong>{c.code}</strong> · valable jusqu&apos;au {formatDate(c.valid_until)}
                </p>
                {c.notes && <p className="text-xs text-gray-500 mt-1">{c.notes}</p>}
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-vz-accent-soft/30 text-black self-start">
                {c.expired ? "Expiré" : "À utiliser en boutique"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </AccountShell>
  );
}
