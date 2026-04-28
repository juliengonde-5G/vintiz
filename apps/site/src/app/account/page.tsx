"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Profile {
  client: {
    first_name: string;
    last_name: string;
    email: string;
    phone: string | null;
    avoir_balance: number;
    deletion_pending: boolean;
  };
  loyalty: {
    points: number;
    membership_number: string;
  } | null;
}

export default function AccountHomePage() {
  const [email, setEmail] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem("vintiz_account_email");
    } catch {
      stored = null;
    }
    if (stored) {
      setEmail(stored);
      void load(stored);
    }
  }, []);

  const load = async (target: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_URL}/api/crm/clients/lookup?email=${encodeURIComponent(target)}`,
        { cache: "no-store" }
      );
      if (res.ok) {
        setProfile(await res.json());
      } else if (res.status === 404) {
        setError("Aucun compte trouvé pour cet email.");
      } else {
        setError("Erreur de chargement.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setLoading(false);
  };

  if (!email && !profile) {
    return (
      <AccountShell title="Mon espace" intro="Connectez-vous pour accéder à votre espace personnel.">
        <Link
          href="/account/login"
          className="inline-block bg-teal text-white px-5 py-3 rounded-lg font-medium"
        >
          Se connecter par code email
        </Link>
      </AccountShell>
    );
  }

  return (
    <AccountShell
      title="Mon espace"
      intro={profile ? `Bonjour ${profile.client.first_name} 👋` : undefined}
    >
      {loading && <p className="text-gray-500">Chargement…</p>}
      {error && <p className="text-red-700">{error}</p>}
      {profile && (
        <div className="grid gap-6 md:grid-cols-2">
          <Tile label="Carte fidélité" value={profile.loyalty?.membership_number ?? "Non membre"} hint={profile.loyalty ? `${profile.loyalty.points} points` : "Adhésion en boutique"} href="/account/fidelite" cta="Voir ma carte" />
          <Tile label="Avoir disponible" value={`${profile.client.avoir_balance.toFixed(2)} €`} hint="Utilisable au prochain passage en caisse" />
          <Tile label="Personal Shopper" value="Sélection IA" hint="Une sélection en temps réel adaptée à vos goûts" href="/account/shopper" cta="Découvrir" />
          <Tile label="Mes achats" value="Historique" hint="Tickets téléchargeables" href="/account/historique" cta="Consulter" />
          <Tile label="Sélection du moment" value="Curation manager" hint="Coups de cœur de la semaine" href="/account/selection" cta="Voir" />
          <Tile label="Confidentialité" value="RGPD" hint="Export, consentements, suppression" href="/account/rgpd" cta="Gérer" />
        </div>
      )}
    </AccountShell>
  );
}

function Tile({
  label,
  value,
  hint,
  href,
  cta,
}: {
  label: string;
  value: string;
  hint: string;
  href?: string;
  cta?: string;
}) {
  return (
    <article className="bg-white rounded-2xl shadow-sm p-5">
      <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-display font-semibold text-black">{value}</p>
      <p className="text-sm text-gray-600 mt-1">{hint}</p>
      {href && cta && (
        <Link
          href={href}
          className="mt-3 inline-block text-sm text-teal underline font-medium"
        >
          {cta} →
        </Link>
      )}
    </article>
  );
}
