"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import WalletCard from "@/components/WalletCard";

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
  product_barcode: string;
  sale_price: number;
  status: string;
  expires_at: string | null;
  created_at: string | null;
}

function formatCurrency(v: number): string {
  return v.toFixed(2).replace(".", ",") + " €";
}

function formatDate(s: string | null): string {
  if (!s) return "-";
  return new Date(s).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export default function AccountDataPage() {
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
    setActionMsg("");
    setData(null);
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
        // Fire and forget — reservations are a nice-to-have on the page.
        fetch(
          `${API_URL}/api/reservations/lookup?email=${encodeURIComponent(email)}`,
          { cache: "no-store" }
        )
          .then(async (r) => {
            if (r.ok) {
              const payload = await r.json();
              setReservations(payload.reservations || []);
            } else {
              setReservations([]);
            }
          })
          .catch(() => setReservations([]));
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
        const blob = new Blob([JSON.stringify(json, null, 2)], {
          type: "application/json",
        });
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
    if (
      !confirm(
        "Confirmer la demande de suppression de votre compte ? Vous disposez de 30 jours pour annuler."
      )
    ) {
      return;
    }
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
            ? "Une demande est déjà en cours. Suppression définitive prévue le " +
              formatDate(body.purge_after) +
              "."
            : "Demande enregistrée. Vos données seront supprimées le " +
              formatDate(body.purge_after) +
              ". Vous pouvez annuler tant que cette date n'est pas atteinte."
        );
        // Refresh state
        setData({
          ...data,
          client: { ...data.client, deletion_pending: true },
        });
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
        setData({
          ...data,
          client: { ...data.client, deletion_pending: false },
        });
      }
    } catch {
      setActionMsg("Erreur réseau.");
    }
    setBusy(false);
  };

  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-cream py-12 px-4">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-3xl font-bold text-black font-display mb-2">
            Mes données personnelles
          </h1>
          <p className="text-gray-600 mb-8">
            Conformément au RGPD, vous pouvez à tout moment consulter, exporter
            ou demander la suppression des données que Vintiz détient sur vous.
          </p>

          {!data && (
            <form
              onSubmit={lookup}
              className="bg-white rounded-2xl shadow-sm p-6 space-y-4"
            >
              <label className="block text-sm font-medium text-black">
                Adresse email associée à votre compte
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="mt-1 w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal"
                  placeholder="prenom.nom@exemple.fr"
                />
              </label>
              <button
                type="submit"
                disabled={loading || !email}
                className="w-full py-3 bg-teal text-white font-medium rounded-lg hover:bg-teal-700 disabled:opacity-50"
              >
                {loading ? "Recherche…" : "Accéder à mes données"}
              </button>
              {error && (
                <p className="text-sm text-red-600 text-center">{error}</p>
              )}
            </form>
          )}

          {data && (
            <div className="space-y-6">
              <section className="bg-white rounded-2xl shadow-sm p-6">
                <h2 className="text-lg font-semibold text-black mb-3">
                  {data.client.first_name} {data.client.last_name}
                </h2>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-gray-500">Email</dt>
                    <dd className="font-medium">{data.client.email}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Téléphone</dt>
                    <dd className="font-medium">
                      {data.client.phone || "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Newsletter email</dt>
                    <dd className="font-medium">
                      {data.client.email_optin ? "Activée" : "Désactivée"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">SMS marketing</dt>
                    <dd className="font-medium">
                      {data.client.sms_optin ? "Activé" : "Désactivé"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Solde avoir</dt>
                    <dd className="font-medium text-teal">
                      {formatCurrency(data.client.avoir_balance)}
                    </dd>
                  </div>
                  {data.loyalty && (
                    <div>
                      <dt className="text-gray-500">Carte fidélité</dt>
                      <dd className="font-medium capitalize">
                        {data.loyalty.tier} — {data.loyalty.points} points
                      </dd>
                    </div>
                  )}
                </dl>
                {data.client.email && (
                  <div className="mt-4">
                    <WalletCard email={data.client.email} />
                  </div>
                )}
              </section>

              {reservations.filter((r) => r.status === "active").length > 0 && (
                <section className="bg-white rounded-2xl shadow-sm p-6">
                  <h2 className="text-lg font-semibold text-black mb-3">
                    Vos pièces réservées
                  </h2>
                  <ul className="divide-y divide-gray-100">
                    {reservations
                      .filter((r) => r.status === "active")
                      .map((r) => (
                        <li key={r.id} className="py-3">
                          <div className="flex justify-between gap-3">
                            <div>
                              <p className="font-medium text-black">
                                {r.product_name}
                              </p>
                              <p className="text-xs text-gray-400">
                                Réservée jusqu&apos;au{" "}
                                {r.expires_at
                                  ? new Date(r.expires_at).toLocaleString(
                                      "fr-FR",
                                      {
                                        day: "2-digit",
                                        month: "long",
                                        hour: "2-digit",
                                        minute: "2-digit",
                                      },
                                    )
                                  : "—"}
                              </p>
                            </div>
                            <span className="font-semibold text-teal whitespace-nowrap">
                              {formatCurrency(r.sale_price)}
                            </span>
                          </div>
                        </li>
                      ))}
                  </ul>
                  <p className="mt-3 text-xs text-gray-500">
                    Passez en boutique au 36 rue d&apos;Albuféra avant l&apos;expiration
                    pour récupérer vos pièces.
                  </p>
                </section>
              )}

              <section className="bg-white rounded-2xl shadow-sm p-6">
                <h2 className="text-lg font-semibold text-black mb-3">
                  Vos derniers achats ({data.recent_transactions.length})
                </h2>
                {data.recent_transactions.length === 0 ? (
                  <p className="text-sm text-gray-400">
                    Aucun achat enregistré.
                  </p>
                ) : (
                  <ul className="divide-y divide-gray-100">
                    {data.recent_transactions.map((tx) => (
                      <li
                        key={tx.id}
                        className="py-2 flex justify-between text-sm"
                      >
                        <span className="text-gray-600">
                          #{tx.transaction_number} —{" "}
                          {formatDate(tx.created_at)}
                        </span>
                        <span className="font-medium text-teal">
                          {formatCurrency(tx.total_ttc)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="bg-white rounded-2xl shadow-sm p-6">
                <h2 className="text-lg font-semibold text-black mb-3">
                  Vos droits RGPD
                </h2>
                <div className="space-y-3">
                  <button
                    type="button"
                    onClick={exportData}
                    disabled={busy}
                    className="w-full py-3 bg-teal text-white rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50"
                  >
                    Télécharger mes données (JSON)
                  </button>

                  {data.client.deletion_pending ? (
                    <button
                      type="button"
                      onClick={cancelDeletion}
                      disabled={busy}
                      className="w-full py-3 bg-white text-orange-700 border border-orange-300 rounded-lg font-medium hover:bg-orange-50 disabled:opacity-50"
                    >
                      Annuler la demande de suppression
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={requestDeletion}
                      disabled={busy}
                      className="w-full py-3 bg-white text-red-700 border border-red-300 rounded-lg font-medium hover:bg-red-50 disabled:opacity-50"
                    >
                      Demander la suppression de mon compte
                    </button>
                  )}
                </div>

                {actionMsg && (
                  <p className="mt-3 text-sm text-gray-700 bg-cream p-3 rounded">
                    {actionMsg}
                  </p>
                )}

                <p className="mt-4 text-xs text-gray-500">
                  La suppression est différée de 30 jours afin de pouvoir
                  l&apos;annuler. Pendant ce délai, votre compte reste actif.
                  Pour plus d&apos;informations, consultez notre{" "}
                  <Link
                    href="/confidentialite"
                    className="text-teal underline"
                  >
                    politique de confidentialité
                  </Link>
                  .
                </p>
              </section>

              <button
                type="button"
                onClick={() => {
                  setData(null);
                  setEmail("");
                  setActionMsg("");
                }}
                className="text-sm text-gray-500 underline hover:text-gray-700"
              >
                ← Rechercher un autre compte
              </button>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
