"use client";

import { useState, FormEvent } from "react";
import Image from "next/image";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ClientLookup {
  client: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    phone: string | null;
    email_optin: boolean;
    sms_optin: boolean;
    avoir_balance: number;
    deletion_pending: boolean;
  };
  loyalty: {
    points: number;
    total_earned: number;
    total_redeemed: number;
    tier: string;
  } | null;
  recent_transactions: {
    id: string;
    transaction_number: number;
    total_ttc: number;
    created_at: string;
  }[];
}

interface PublicReservation {
  id: string;
  product_name: string;
  sale_price: number;
  status: string;
  expires_at: string | null;
}

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  bronze: { label: "Bronze", color: "text-amber-700" },
  silver: { label: "Silver", color: "text-slate-500" },
  gold: { label: "Gold", color: "text-yellow-500" },
};

function formatCurrency(v: number) {
  return v.toFixed(2).replace(".", ",") + " €";
}

function formatDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export default function DevComptePage() {
  const [email, setEmail] = useState("");
  const [data, setData] = useState<ClientLookup | null>(null);
  const [reservations, setReservations] = useState<PublicReservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const lookup = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setData(null);
    setActionMsg("");
    try {
      const res = await fetch(
        `${API_URL}/api/crm/clients/lookup?email=${encodeURIComponent(email)}`,
        { cache: "no-store" }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.detail || "Aucun compte trouvé pour cet email.");
      } else {
        setData(body);
        fetch(
          `${API_URL}/api/reservations/lookup?email=${encodeURIComponent(email)}`,
          { cache: "no-store" }
        )
          .then(async (r) => {
            if (r.ok) {
              const p = await r.json();
              setReservations(p.reservations || []);
            }
          })
          .catch(() => {});
      }
    } catch {
      setError("Impossible de contacter le serveur. Réessayez plus tard.");
    }
    setLoading(false);
  };

  const exportData = async () => {
    if (!data) return;
    setBusy(true);
    setActionMsg("");
    try {
      const res = await fetch(
        `${API_URL}/api/crm/account/data-export?email=${encodeURIComponent(data.client.email)}`,
        { cache: "no-store" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setActionMsg(err?.detail || "Échec de l'export.");
      } else {
        const json = await res.json();
        const blob = new Blob([JSON.stringify(json, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `vintiz-mes-donnees-${data.client.email}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setActionMsg("Vos données ont été téléchargées au format JSON.");
      }
    } catch {
      setActionMsg("Erreur réseau pendant l'export.");
    }
    setBusy(false);
  };

  const requestDeletion = async () => {
    if (!data) return;
    if (!confirm("Confirmer la demande de suppression ? Vous aurez 30 jours pour annuler.")) return;
    setBusy(true);
    setActionMsg("");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/deletion-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.client.email }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionMsg(body?.detail || "Échec de la demande.");
      } else {
        setActionMsg(
          body.already_pending
            ? "Une demande est déjà en cours. Suppression prévue le " + formatDate(body.purge_after) + "."
            : "Demande enregistrée. Suppression le " + formatDate(body.purge_after) + "."
        );
        setData({ ...data, client: { ...data.client, deletion_pending: true } });
      }
    } catch {
      setActionMsg("Erreur réseau.");
    }
    setBusy(false);
  };

  const cancelDeletion = async () => {
    if (!data) return;
    setBusy(true);
    setActionMsg("");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/deletion-cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.client.email }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionMsg(body?.detail || "Échec de l'annulation.");
      } else {
        setActionMsg("Demande de suppression annulée.");
        setData({ ...data, client: { ...data.client, deletion_pending: false } });
      }
    } catch {
      setActionMsg("Erreur réseau.");
    }
    setBusy(false);
  };

  const tierInfo = data?.loyalty ? (TIER_LABELS[data.loyalty.tier] ?? { label: data.loyalty.tier, color: "text-teal" }) : null;
  const activeReservations = reservations.filter((r) => r.status === "active");

  return (
    <main className="bg-cream min-h-screen">
      {/* HERO */}
      <section className="max-w-3xl mx-auto px-6 pt-14 pb-10 text-center">
        <h1 className="font-mockSerif text-5xl md:text-6xl text-teal leading-tight">
          Mon compte
        </h1>
        <p className="mt-4 text-base md:text-lg text-black/70 leading-relaxed">
          Retrouvez votre carte fidélité, vos achats et gérez vos données
          personnelles.
        </p>
      </section>

      <div className="max-w-2xl mx-auto px-6 pb-20">
        {/* LOOKUP FORM */}
        {!data && (
          <form
            onSubmit={lookup}
            className="bg-white rounded-2xl shadow-sm p-8 space-y-5"
          >
            <div className="flex justify-center mb-2">
              <Image src="/logo-teal.png" alt="Vintiz" width={60} height={60} className="h-14 w-auto" />
            </div>
            <p className="text-center text-sm text-black/60">
              Entrez l&apos;adresse email associée à votre compte Vintiz.
            </p>
            <label className="block text-sm font-medium text-black">
              Adresse email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-1 w-full px-4 py-3 border border-black/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal bg-cream/60 placeholder:text-black/30"
                placeholder="prenom.nom@exemple.fr"
              />
            </label>
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3.5 bg-teal text-white font-medium rounded-full hover:bg-teal/90 disabled:opacity-50 transition-colors"
            >
              {loading ? "Recherche…" : "Accéder à mon compte"}
            </button>
            {error && (
              <p className="text-sm text-red-600 text-center">{error}</p>
            )}
          </form>
        )}

        {/* COMPTE DATA */}
        {data && (
          <div className="space-y-6">
            {/* CARTE FIDÉLITÉ */}
            <section className="bg-white rounded-2xl shadow-sm p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-mockSerif text-2xl text-teal">
                    {data.client.first_name} {data.client.last_name}
                  </h2>
                  <p className="text-sm text-black/50 mt-0.5">{data.client.email}</p>
                </div>
                {tierInfo && (
                  <span className={`text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full border ${tierInfo.color} border-current`}>
                    {tierInfo.label}
                  </span>
                )}
              </div>

              {data.loyalty && (
                <div className="mt-5 grid grid-cols-3 gap-3 text-center">
                  <div className="bg-cream rounded-xl py-3">
                    <p className="font-mockSerif text-3xl text-teal">{data.loyalty.points}</p>
                    <p className="text-xs text-black/50 mt-0.5">points</p>
                  </div>
                  <div className="bg-cream rounded-xl py-3">
                    <p className="font-mockSerif text-3xl text-teal">{data.loyalty.total_earned}</p>
                    <p className="text-xs text-black/50 mt-0.5">gagnés</p>
                  </div>
                  <div className="bg-cream rounded-xl py-3">
                    <p className="font-mockSerif text-3xl text-teal">{data.loyalty.total_redeemed}</p>
                    <p className="text-xs text-black/50 mt-0.5">utilisés</p>
                  </div>
                </div>
              )}

              {data.client.avoir_balance > 0 && (
                <p className="mt-4 text-sm text-center text-teal font-medium">
                  Solde avoir : <strong>{formatCurrency(data.client.avoir_balance)}</strong>
                </p>
              )}
            </section>

            {/* RÉSERVATIONS ACTIVES */}
            {activeReservations.length > 0 && (
              <section className="bg-white rounded-2xl shadow-sm p-6">
                <h2 className="font-mockSerif text-xl text-teal mb-4">
                  Pièces réservées
                </h2>
                <ul className="divide-y divide-black/5">
                  {activeReservations.map((r) => (
                    <li key={r.id} className="py-3 flex justify-between gap-4">
                      <div>
                        <p className="text-sm font-medium text-black">{r.product_name}</p>
                        {r.expires_at && (
                          <p className="text-xs text-black/40 mt-0.5">
                            Jusqu&apos;au{" "}
                            {new Date(r.expires_at).toLocaleString("fr-FR", {
                              day: "2-digit",
                              month: "long",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </p>
                        )}
                      </div>
                      <span className="font-semibold text-teal whitespace-nowrap text-sm">
                        {formatCurrency(r.sale_price)}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-black/40">
                  Passez au 6 rue Saint-Jacques avant expiration pour récupérer vos pièces.
                </p>
              </section>
            )}

            {/* HISTORIQUE ACHATS */}
            <section className="bg-white rounded-2xl shadow-sm p-6">
              <h2 className="font-mockSerif text-xl text-teal mb-4">
                Derniers achats
              </h2>
              {data.recent_transactions.length === 0 ? (
                <p className="text-sm text-black/40">Aucun achat enregistré.</p>
              ) : (
                <ul className="divide-y divide-black/5">
                  {data.recent_transactions.map((tx) => (
                    <li key={tx.id} className="py-2.5 flex justify-between text-sm">
                      <span className="text-black/60">
                        #{tx.transaction_number} — {formatDate(tx.created_at)}
                      </span>
                      <span className="font-medium text-teal">{formatCurrency(tx.total_ttc)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* RGPD */}
            <section className="bg-white rounded-2xl shadow-sm p-6">
              <h2 className="font-mockSerif text-xl text-teal mb-4">
                Mes droits RGPD
              </h2>
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={exportData}
                  disabled={busy}
                  className="w-full py-3 bg-teal text-white rounded-full font-medium hover:bg-teal/90 disabled:opacity-50 transition-colors text-sm"
                >
                  Télécharger mes données (JSON)
                </button>
                {data.client.deletion_pending ? (
                  <button
                    type="button"
                    onClick={cancelDeletion}
                    disabled={busy}
                    className="w-full py-3 border border-orange-300 text-orange-700 rounded-full font-medium hover:bg-orange-50 disabled:opacity-50 transition-colors text-sm"
                  >
                    Annuler la demande de suppression
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={requestDeletion}
                    disabled={busy}
                    className="w-full py-3 border border-red-300 text-red-700 rounded-full font-medium hover:bg-red-50 disabled:opacity-50 transition-colors text-sm"
                  >
                    Demander la suppression de mon compte
                  </button>
                )}
              </div>
              {actionMsg && (
                <p className="mt-4 text-sm text-black/70 bg-cream p-3 rounded-xl">
                  {actionMsg}
                </p>
              )}
              <p className="mt-4 text-xs text-black/40">
                La suppression est différée de 30 jours. Consultez notre{" "}
                <Link href="/confidentialite" className="text-teal underline">
                  politique de confidentialité
                </Link>
                .
              </p>
            </section>

            <button
              type="button"
              onClick={() => { setData(null); setEmail(""); setActionMsg(""); setReservations([]); }}
              className="text-sm text-black/40 hover:text-black underline"
            >
              ← Rechercher un autre compte
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
