"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";
import WalletCard from "@/components/WalletCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LoyaltyPayload {
  loyalty: { points: number; membership_number: string } | null;
}

const FAQ = [
  {
    q: "Comment je gagne des points ?",
    a: "1 € dépensé en boutique = 1 point. Les points sont crédités automatiquement à chaque passage en caisse, dès que votre carte est identifiée.",
  },
  {
    q: "Comment j'utilise mes points ?",
    a: "Tous les 100 points, un bon d'achat de 8 € est généré automatiquement et associé à votre carte. Il s'applique au prochain passage en caisse, valable 6 mois.",
  },
  {
    q: "Mes points expirent-ils ?",
    a: "Oui, les points expirent au bout de 24 mois sans activité (achat ou utilisation). Un passage en boutique remet le compteur à zéro.",
  },
  {
    q: "Puis-je désactiver ma carte ?",
    a: "Oui, à tout moment depuis votre espace Confidentialité ou en boutique. La désactivation est irréversible mais la carte peut être recréée plus tard.",
  },
];

export default function AccountFidelitePage() {
  const [email, setEmail] = useState("");
  const [data, setData] = useState<LoyaltyPayload | null>(null);
  const [openIdx, setOpenIdx] = useState<number | null>(null);

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
    const res = await fetch(
      `${API_URL}/api/crm/clients/lookup?email=${encodeURIComponent(target)}`,
      { cache: "no-store" }
    );
    if (res.ok) {
      setData(await res.json());
    }
  };

  if (!email) {
    return (
      <AccountShell title="Ma fidélité" intro="Connectez-vous pour afficher votre carte.">
        <Link href="/account/login" className="text-vz-teal underline">
          Se connecter
        </Link>
      </AccountShell>
    );
  }

  if (data && !data.loyalty) {
    return (
      <AccountShell title="Ma fidélité" intro="Adhésion en boutique pour démarrer.">
        <div className="bg-vz-accent-soft/30 border border-vz-accent-soft rounded-2xl p-6 max-w-2xl">
          <p className="text-gray-700 mb-3">
            Vous n&apos;avez pas encore de carte fidélité Vintiz. L&apos;adhésion est
            digitale, sans formulaire papier — passez en boutique à Vernon, on
            vous crée la carte en 30 secondes.
          </p>
          <p className="text-sm text-gray-500">
            6 rue Saint-Jacques · 27200 Vernon · Du mardi au samedi
          </p>
        </div>
      </AccountShell>
    );
  }

  return (
    <AccountShell title="Ma fidélité" intro="Présentez ce QR à la caisse pour cumuler vos points.">
      {data?.loyalty && (
        <div className="space-y-8">
          <WalletCard email={email} showBigQr />
          <section>
            <h2 className="text-xl font-display font-semibold text-black mb-3">
              Mécanique simple
            </h2>
            <ul className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <li className="bg-white rounded-2xl p-4 shadow-sm">
                <p className="text-3xl font-display text-vz-teal">1 €</p>
                <p className="text-sm text-gray-600">= 1 point cumulé</p>
              </li>
              <li className="bg-white rounded-2xl p-4 shadow-sm">
                <p className="text-3xl font-display text-vz-teal">100 pts</p>
                <p className="text-sm text-gray-600">= bon d&apos;achat 8 €</p>
              </li>
              <li className="bg-white rounded-2xl p-4 shadow-sm">
                <p className="text-3xl font-display text-vz-teal">24 mois</p>
                <p className="text-sm text-gray-600">de validité sans activité</p>
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-display font-semibold text-black mb-3">
              Questions fréquentes
            </h2>
            <div className="space-y-2">
              {FAQ.map((item, idx) => {
                const open = openIdx === idx;
                return (
                  <details
                    key={item.q}
                    open={open}
                    onToggle={(e) => {
                      const detailsEl = e.currentTarget as HTMLDetailsElement;
                      if (detailsEl.open) setOpenIdx(idx);
                      else if (openIdx === idx) setOpenIdx(null);
                    }}
                    className="bg-white rounded-xl shadow-sm p-4"
                  >
                    <summary className="cursor-pointer font-medium text-black">
                      {item.q}
                    </summary>
                    <p className="text-sm text-gray-600 mt-2">{item.a}</p>
                  </details>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </AccountShell>
  );
}
