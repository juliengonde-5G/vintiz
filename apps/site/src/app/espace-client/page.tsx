"use client";

import { useState, FormEvent } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.vintiz.fr";

interface ClientData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
}

interface LoyaltyData {
  points: number;
  total_earned: number;
  total_redeemed: number;
  tier: string;
}

interface Transaction {
  id: string;
  transaction_number: number;
  total_ttc: number;
  created_at: string;
}

export default function EspaceClientPage() {
  const [view, setView] = useState<"login" | "dashboard">("login");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [clientData, setClientData] = useState<ClientData | null>(null);
  const [loyalty, setLoyalty] = useState<LoyaltyData | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [token, setToken] = useState("");

  // Simple client lookup by email (public endpoint)
  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      // First, try to find the client via the public API
      const res = await fetch(`${API_URL}/api/crm/clients/lookup?email=${encodeURIComponent(email)}`);
      if (res.ok) {
        const data = await res.json();
        setClientData(data.client);
        setLoyalty(data.loyalty || null);
        setTransactions(data.recent_transactions || []);
        setToken(data.token || "");
        setView("dashboard");
      } else if (res.status === 404) {
        setError("Aucun compte trouve avec cet email. Demandez votre carte fidelite en boutique !");
      } else {
        setError("Erreur de connexion. Veuillez reessayer.");
      }
    } catch {
      setError("Impossible de contacter le serveur.");
    }
    setLoading(false);
  };

  const formatCurrency = (v: number) => v.toFixed(2).replace(".", ",") + "\u00A0\u20AC";

  const formatDate = (d: string) => {
    const date = new Date(d);
    return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}/${date.getFullYear()}`;
  };

  const tierLabel = (t: string) => {
    if (t === "gold") return "Gold";
    if (t === "silver") return "Silver";
    return "Bronze";
  };

  const tierColor = (t: string) => {
    if (t === "gold") return "text-yellow-600 bg-yellow-50";
    if (t === "silver") return "text-gray-600 bg-gray-100";
    return "text-orange-700 bg-orange-50";
  };

  return (
    <>
      <Navbar />

      <section className="pt-28 pb-16 px-6 bg-vintiz-bg min-h-screen">
        <div className="max-w-2xl mx-auto">
          {view === "login" ? (
            <>
              <div className="text-center mb-10">
                <h1 className="font-serif text-4xl text-vintiz-black mb-4">
                  Espace <em className="text-vintiz-teal">Client</em>
                </h1>
                <p className="text-vintiz-black/60">
                  Consultez vos points fidelite et votre historique d&apos;achats.
                </p>
              </div>

              <div className="bg-white rounded-2xl p-8 shadow-sm">
                <form onSubmit={handleLogin} className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-vintiz-black mb-1.5">
                      Adresse email
                    </label>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-3 rounded-lg border border-vintiz-pink/40 bg-white text-vintiz-black focus:outline-none focus:ring-2 focus:ring-vintiz-teal/40 focus:border-vintiz-teal"
                      placeholder="votre@email.com"
                    />
                  </div>
                  {error && (
                    <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">{error}</div>
                  )}
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full px-6 py-3 bg-vintiz-teal text-white font-medium rounded-lg hover:bg-vintiz-teal/90 disabled:opacity-50 transition-colors"
                  >
                    {loading ? "Connexion..." : "Acceder a mon espace"}
                  </button>
                </form>
                <p className="text-xs text-vintiz-black/40 text-center mt-4">
                  Pas encore inscrit(e) ? Demandez votre carte fidelite en boutique.
                </p>
              </div>
            </>
          ) : (
            <>
              {/* Client Dashboard */}
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h1 className="font-serif text-3xl text-vintiz-black">
                    Bonjour, <em className="text-vintiz-teal">{clientData?.first_name}</em>
                  </h1>
                  <p className="text-vintiz-black/50">{clientData?.email}</p>
                </div>
                <button
                  onClick={() => { setView("login"); setClientData(null); }}
                  className="text-sm text-vintiz-black/40 hover:text-vintiz-teal transition-colors"
                >
                  Deconnexion
                </button>
              </div>

              {/* Loyalty Card */}
              {loyalty && (
                <div className="bg-gradient-to-br from-vintiz-teal to-vintiz-teal/80 rounded-2xl p-8 text-white mb-6">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <p className="text-sm text-white/70">Carte fidelite</p>
                      <p className="font-serif text-2xl mt-1">VINTIZ</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${tierColor(loyalty.tier)}`}>
                      {tierLabel(loyalty.tier)}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="text-3xl font-bold">{loyalty.points}</p>
                      <p className="text-xs text-white/60 mt-1">Points disponibles</p>
                    </div>
                    <div>
                      <p className="text-3xl font-bold">{loyalty.total_earned}</p>
                      <p className="text-xs text-white/60 mt-1">Points cumules</p>
                    </div>
                    <div>
                      <p className="text-3xl font-bold">{formatCurrency(loyalty.points * 0.05)}</p>
                      <p className="text-xs text-white/60 mt-1">Valeur en bon</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Recent Purchases */}
              <div className="bg-white rounded-2xl p-6 shadow-sm">
                <h2 className="font-serif text-xl text-vintiz-black mb-4">Mes achats recents</h2>
                {transactions.length === 0 ? (
                  <p className="text-vintiz-black/40 text-center py-6">Aucun achat pour le moment</p>
                ) : (
                  <div className="space-y-3">
                    {transactions.map((tx) => (
                      <div key={tx.id} className="flex items-center justify-between p-4 bg-vintiz-bg rounded-lg">
                        <div>
                          <p className="text-sm font-medium text-vintiz-black">Ticket #{tx.transaction_number}</p>
                          <p className="text-xs text-vintiz-black/40">{formatDate(tx.created_at)}</p>
                        </div>
                        <p className="font-bold text-vintiz-teal">{formatCurrency(tx.total_ttc)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </section>

      <Footer />
    </>
  );
}
