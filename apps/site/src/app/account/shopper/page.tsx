"use client";

import { useEffect, useState, FormEvent } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type GateReason = "loyalty_required" | "profiling_consent_required" | null;

interface ShopperItem {
  product_id: string;
  name: string;
  price_cents: number;
  photo_url: string | null;
  zone: string | null;
  score: number;
  size: string | null;
  color: string | null;
}

interface SearchResponse {
  items: ShopperItem[];
  filters: Record<string, string | number | null>;
  cache_hit: boolean;
  normalized_query: string;
}

function formatPrice(cents: number): string {
  return (cents / 100).toFixed(2).replace(".", ",") + " €";
}

export default function AccountShopperPage() {
  const [email, setEmail] = useState("");
  const [emailLocked, setEmailLocked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [gate, setGate] = useState<GateReason>(null);
  const [items, setItems] = useState<ShopperItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ShopperItem[] | null>(null);
  const [searchCacheHit, setSearchCacheHit] = useState(false);
  const [searchBusy, setSearchBusy] = useState(false);
  const [toggleBusy, setToggleBusy] = useState(false);
  const [error, setError] = useState("");

  // Hydrate email from PR1 magic-link login if present.
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("vintiz_account_email");
      if (stored) {
        setEmail(stored);
      }
    } catch {
      /* private mode — let the customer type their email manually */
    }
  }, []);

  const loadFeed = async (e?: FormEvent) => {
    if (e) e.preventDefault();
    if (!email) return;
    setLoading(true);
    setError("");
    setGate(null);
    setItems([]);
    try {
      const res = await fetch(
        `${API_URL}/api/crm/account/personal-shopper/live?email=${encodeURIComponent(email)}`,
        { cache: "no-store" }
      );
      const body = await res.json().catch(() => ({}));
      if (res.status === 403) {
        setGate(body?.detail as GateReason);
      } else if (res.status === 404) {
        setError("Aucun compte trouvé pour cet email.");
      } else if (!res.ok) {
        setError("Impossible de charger les recommandations.");
      } else {
        setItems(body.products ?? []);
        setEmailLocked(true);
      }
    } catch {
      setError("Erreur réseau.");
    }
    setLoading(false);
  };

  const enableProfiling = async () => {
    setToggleBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/personal-shopper/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, enabled: true }),
      });
      if (res.ok) {
        await loadFeed();
      } else {
        setError("Activation impossible. Réessayez.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setToggleBusy(false);
  };

  const submitSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearchBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/personal-shopper/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, q: searchQuery }),
      });
      const body = (await res.json().catch(() => ({}))) as Partial<SearchResponse>;
      if (res.status === 403) {
        setGate((body as { detail?: GateReason })?.detail ?? "loyalty_required");
        setSearchResults(null);
      } else if (!res.ok) {
        setError("Recherche indisponible. Réessayez.");
        setSearchResults(null);
      } else {
        setSearchResults(body.items ?? []);
        setSearchCacheHit(Boolean(body.cache_hit));
      }
    } catch {
      setError("Erreur réseau.");
      setSearchResults(null);
    }
    setSearchBusy(false);
  };

  return (
    <AccountShell
      title="Mon Personal Shopper"
      intro="Une sélection en temps réel des pièces disponibles à Vernon, choisies en fonction de vos goûts. Réservé aux membres du programme fidélité Vintiz, avec votre consentement explicite."
    >
      <>
        {!emailLocked && (
          <form onSubmit={loadFeed} className="bg-white rounded-2xl shadow-sm p-6 mb-8 max-w-md">
            <label className="block text-sm font-medium text-black mb-1" htmlFor="account-email">
              Adresse email associée à votre compte
            </label>
            <input
              id="account-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@email.fr"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal focus:border-teal mb-3"
            />
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full bg-teal text-white py-3 rounded-lg font-medium hover:bg-teal/90 disabled:opacity-50"
            >
              {loading ? "Chargement…" : "Voir mes recommandations"}
            </button>
            <p className="text-xs text-gray-500 mt-3">
              Nouveau ? <Link href="/account/login" className="text-teal underline">Connectez-vous par email</Link>{" "}
              pour récupérer votre carte de fidélité.
            </p>
          </form>
        )}

        {gate === "loyalty_required" && (
          <div className="bg-pink/30 border border-pink rounded-2xl p-6 max-w-2xl">
            <h2 className="text-xl font-display font-semibold text-black mb-2">
              Réservé aux membres
            </h2>
            <p className="text-gray-700 mb-4">
              Le Personal Shopper est inclus dans la carte de fidélité Vintiz.
              Adhésion 100 % digitale, gratuite ou offerte au 1er achat selon
              l&apos;opération en cours.
            </p>
            <Link
              href="/account/login"
              className="inline-block bg-teal text-white px-5 py-2 rounded-lg font-medium"
            >
              Adhérer en boutique
            </Link>
          </div>
        )}

        {gate === "profiling_consent_required" && (
          <div className="bg-cream border border-teal/30 rounded-2xl p-6 max-w-2xl">
            <h2 className="text-xl font-display font-semibold text-black mb-2">
              Activez votre Personal Shopper
            </h2>
            <p className="text-gray-700 mb-4">
              Pour vous proposer des pièces compatibles avec votre style et votre
              historique, nous avons besoin de votre accord pour exploiter votre
              profil de goûts (consentement RGPD «&nbsp;profilage&nbsp;»). Vous
              pouvez le désactiver à tout moment.
            </p>
            <button
              onClick={enableProfiling}
              disabled={toggleBusy}
              className="bg-teal text-white px-5 py-2 rounded-lg font-medium disabled:opacity-50"
            >
              {toggleBusy ? "Activation…" : "Activer mon Personal Shopper"}
            </button>
          </div>
        )}

        {emailLocked && !gate && (
          <>
            <form onSubmit={submitSearch} className="mb-8 flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder='Ex : "t-shirt blanc taille M"'
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal focus:border-teal"
              />
              <button
                type="submit"
                disabled={searchBusy || !searchQuery.trim()}
                className="bg-teal text-white px-6 py-3 rounded-lg font-medium hover:bg-teal/90 disabled:opacity-50"
              >
                {searchBusy ? "…" : "Rechercher"}
              </button>
            </form>

            <ProductGrid
              items={searchResults ?? items}
              empty={
                searchResults
                  ? "Aucun produit ne correspond à cette recherche."
                  : "Pas encore de recommandations — passez quelques achats en boutique pour démarrer votre profil."
              }
              cacheHit={searchResults ? searchCacheHit : false}
            />
          </>
        )}

        {error && (
          <div className="mt-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
        )}
      </>
    </AccountShell>
  );
}

function ProductGrid({
  items,
  empty,
  cacheHit,
}: {
  items: ShopperItem[];
  empty: string;
  cacheHit: boolean;
}) {
  if (items.length === 0) {
    return <p className="text-gray-500">{empty}</p>;
  }
  return (
    <>
      {cacheHit && (
        <p className="text-xs text-gray-400 mb-3">Résultat servi depuis le cache (24 h)</p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {items.map((item) => (
          <article
            key={item.product_id}
            className="bg-white rounded-2xl shadow-sm overflow-hidden flex flex-col"
          >
            <div className="aspect-square bg-gray-100">
              {item.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={item.photo_url} alt={item.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-4xl text-gray-300">
                  👗
                </div>
              )}
            </div>
            <div className="p-3 flex-1 flex flex-col gap-1">
              <h3 className="text-sm font-medium text-black line-clamp-2">{item.name}</h3>
              <p className="text-xs text-gray-500">
                {[item.size, item.color].filter(Boolean).join(" · ") || "—"}
              </p>
              <p className="text-base font-semibold text-teal mt-auto">{formatPrice(item.price_cents)}</p>
              <p className="text-xs text-gray-500">En boutique · Vernon</p>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
