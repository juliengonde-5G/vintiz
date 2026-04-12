"use client";

import { useState, useEffect, FormEvent } from "react";
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

interface PersonalShopperProduct {
  id: string;
  name: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  sale_price: number;
  category: string | null;
  trend_score: number | null;
  condition: string | null;
}

interface PersonalShopper {
  profile: { preferred_brands: string[]; preferred_size: string | null; preferred_categories: string[] };
  narrative: string;
  recommendations: PersonalShopperProduct[];
  generated_at: string;
}

export default function EspaceClientPage() {
  const [view, setView] = useState<"login" | "dashboard">("login");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [clientData, setClientData] = useState<ClientData | null>(null);
  const [loyalty, setLoyalty] = useState<LoyaltyData | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [personalShopper, setPersonalShopper] = useState<PersonalShopper | null>(null);
  const [shopperLoading, setShopperLoading] = useState(false);

  // Load personal shopper when dashboard is shown
  useEffect(() => {
    if (view === "dashboard" && email && !personalShopper) {
      setShopperLoading(true);
      fetch(`${API_URL}/api/crm/clients/personal-shopper?email=${encodeURIComponent(email)}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setPersonalShopper(data); })
        .catch(() => {})
        .finally(() => setShopperLoading(false));
    }
  }, [view, email, personalShopper]);

  // Simple client lookup by email (public endpoint)
  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/api/crm/clients/lookup?email=${encodeURIComponent(email)}`);
      if (res.ok) {
        const data = await res.json();
        setClientData(data.client);
        setLoyalty(data.loyalty || null);
        setTransactions(data.recent_transactions || []);
        setView("dashboard");
      } else if (res.status === 404) {
        setError("Aucun compte trouvé avec cet email. Demandez votre carte fidélité en boutique !");
      } else {
        setError("Erreur de connexion. Veuillez réessayer.");
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

              {/* Personal Shopper */}
              <div className="bg-white rounded-2xl p-6 shadow-sm mb-6">
                <h2 className="font-serif text-xl text-vintiz-black mb-1">
                  ✨ Votre Personal Shopper
                </h2>
                <p className="text-sm text-vintiz-black/50 mb-4">Sélection IA personnalisée pour vous</p>

                {shopperLoading && (
                  <div className="flex items-center gap-3 py-6">
                    <div className="w-5 h-5 border-2 border-vintiz-teal border-t-transparent rounded-full animate-spin" />
                    <p className="text-sm text-vintiz-black/50">Préparation de votre sélection...</p>
                  </div>
                )}

                {personalShopper && !shopperLoading && (
                  <div>
                    {/* Narrative */}
                    <div className="p-4 bg-vintiz-pink/10 rounded-xl mb-4">
                      <p className="text-sm text-vintiz-black italic leading-relaxed">&ldquo;{personalShopper.narrative}&rdquo;</p>
                    </div>

                    {/* Profile tags */}
                    {personalShopper.profile.preferred_brands.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {personalShopper.profile.preferred_size && (
                          <span className="px-3 py-1 bg-vintiz-teal/10 text-vintiz-teal text-xs rounded-full font-medium">
                            Taille {personalShopper.profile.preferred_size}
                          </span>
                        )}
                        {personalShopper.profile.preferred_brands.map(b => (
                          <span key={b} className="px-3 py-1 bg-vintiz-black/5 text-vintiz-black text-xs rounded-full">
                            {b}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Product cards */}
                    <div className="grid grid-cols-2 gap-3">
                      {personalShopper.recommendations.slice(0, 6).map(product => (
                        <div key={product.id} className="p-3 bg-vintiz-bg rounded-xl border border-vintiz-pink/20">
                          <div className="w-full h-24 bg-gradient-to-br from-vintiz-pink/20 to-vintiz-teal/10 rounded-lg mb-2 flex items-center justify-center">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-vintiz-teal/40">
                              <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>
                            </svg>
                          </div>
                          <p className="text-xs font-medium text-vintiz-black line-clamp-2 mb-1">{product.name}</p>
                          {product.brand && <p className="text-xs text-vintiz-black/50 mb-1">{product.brand}</p>}
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-bold text-vintiz-teal">{formatCurrency(product.sale_price)}</p>
                            {product.size && <p className="text-xs text-vintiz-black/40">{product.size}</p>}
                          </div>
                        </div>
                      ))}
                    </div>

                    <p className="text-xs text-vintiz-black/30 text-center mt-4">
                      Disponible en boutique · Demandez à voir ces pièces à l&apos;accueil
                    </p>
                  </div>
                )}

                {!personalShopper && !shopperLoading && (
                  <p className="text-sm text-vintiz-black/40 text-center py-4">
                    Effectuez votre premier achat en boutique pour débloquer votre sélection personnalisée.
                  </p>
                )}
              </div>

              {/* Recent Purchases */}
              <div className="bg-white rounded-2xl p-6 shadow-sm">
                <h2 className="font-serif text-xl text-vintiz-black mb-4">Mes achats récents</h2>
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
