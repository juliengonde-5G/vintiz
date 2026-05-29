"use client";

import { useEffect, useState, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AccountShell from "@/components/account/AccountShell";
import AiBadge from "@/components/AiBadge";
import AiDisclaimer from "@/components/AiDisclaimer";
import { mediaUrl } from "@/lib/media";
import { formatPriceCents } from "@/lib/format";

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

export default function AccountShopperPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [emailLocked, setEmailLocked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [gate, setGate] = useState<GateReason>(null);
  const [items, setItems] = useState<ShopperItem[]>([]);
  // Assumed-empty-state copy returned by the live feed when there's no taste
  // signal yet or nothing in stock matches (PS 360 §3.2 / §5.2).
  const [feedMessage, setFeedMessage] = useState("");
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
        setFeedMessage(body.message ?? "");
        setEmailLocked(true);
      }
    } catch {
      setError("Erreur réseau.");
    }
    setLoading(false);
  };

  /**
   * Consentement explicite RGPD (art. 6-1-a + art. 7) au profilage IA.
   * Posté avec une `source` distincte selon la décision de la cliente —
   * critique pour démontrer le consentement en cas de contrôle CNIL.
   */
  const recordProfilingDecision = async (granted: boolean) => {
    setToggleBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/personal-shopper/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          enabled: granted,
          source: granted
            ? "site_ps_consent_screen_grant"
            : "site_ps_consent_screen_decline",
        }),
      });
      if (!res.ok) {
        setError(
          granted
            ? "Activation impossible. Réessayez."
            : "Enregistrement impossible. Réessayez.",
        );
        setToggleBusy(false);
        return;
      }
      if (granted) {
        await loadFeed();
      } else {
        // Refus poli : on enregistre Consent(granted=False) côté serveur,
        // puis on ramène la cliente sur son espace avec un message
        // expliquant comment réactiver à tout moment.
        try {
          window.sessionStorage.setItem(
            "vintiz_account_flash",
            "Personal Shopper non activé. Vous pouvez l'activer à tout moment depuis cette page.",
          );
        } catch {
          /* sessionStorage indispo en mode privé — pas grave */
        }
        router.push("/account");
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
        {/* AI Act art. 50 — disclaimer permanent visible avant toute interaction. */}
        <AiDisclaimer variant="inline" className="mb-6" />

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
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vz-teal focus:border-vz-teal mb-3"
            />
            <button
              type="submit"
              disabled={loading || !email}
              className="w-full bg-vz-teal text-white py-3 rounded-lg font-medium hover:bg-vz-teal/90 disabled:opacity-50"
            >
              {loading ? "Chargement…" : "Voir mes recommandations"}
            </button>
            <p className="text-xs text-gray-500 mt-3">
              Nouveau ? <Link href="/account/login" className="text-vz-teal underline">Connectez-vous par email</Link>{" "}
              pour récupérer votre carte de fidélité.
            </p>
          </form>
        )}

        {gate === "loyalty_required" && (
          <div className="bg-vz-accent-soft/30 border border-vz-accent-soft rounded-2xl p-6 max-w-2xl">
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
              className="inline-block bg-vz-teal text-white px-5 py-2 rounded-lg font-medium"
            >
              Adhérer en boutique
            </Link>
          </div>
        )}

        {gate === "profiling_consent_required" && (
          <section
            aria-labelledby="ps-consent-title"
            className="bg-vz-surface border border-vz-teal/20 rounded-2xl p-6 sm:p-8 max-w-3xl shadow-sm"
          >
            <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
              Consentement explicite — RGPD article 6-1-a
            </p>
            <h2
              id="ps-consent-title"
              className="text-2xl font-display font-semibold text-vz-ink mb-3 leading-tight"
            >
              Activez votre Personal Shopper IA
            </h2>
            <p className="text-vz-ink-soft leading-relaxed mb-6">
              Pour vous proposer des pièces qui correspondent vraiment à votre
              style, nous analysons vos préférences via une intelligence
              artificielle. Avant d&apos;activer le service, voici exactement
              ce que nous faisons et ce que vous contrôlez.
            </p>

            <div className="grid sm:grid-cols-2 gap-5 mb-6">
              <div className="rounded-xl bg-vz-bg-alt/60 p-4">
                <h3 className="font-display text-base text-vz-ink mb-2">
                  Données analysées
                </h3>
                <ul className="text-sm text-vz-ink-soft space-y-1.5">
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">•</span>
                    <span>Historique d&apos;achats (3 derniers en priorité)</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">•</span>
                    <span>Préférences déclarées (tailles, couleurs, marques)</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">•</span>
                    <span>Clics sur les recommandations précédentes</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">•</span>
                    <span>Contexte de visite (saison, météo Vernon)</span>
                  </li>
                </ul>
              </div>

              <div className="rounded-xl bg-vz-bg-alt/60 p-4">
                <h3 className="font-display text-base text-vz-ink mb-2">
                  Vos droits, à tout moment
                </h3>
                <ul className="text-sm text-vz-ink-soft space-y-1.5">
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">→</span>
                    <span>Désactiver le service en un clic</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">→</span>
                    <span>Exporter vos données (article&nbsp;20 RGPD)</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">→</span>
                    <span>Demander la suppression du profil</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-vz-teal">→</span>
                    <span>Demander l&apos;intervention d&apos;un humain</span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="rounded-xl bg-vz-teal-soft/40 border border-vz-teal/20 p-4 text-sm text-vz-ink-soft leading-relaxed mb-6">
              <p>
                <strong className="text-vz-ink">L&apos;IA utilisée :</strong>{" "}
                Claude Haiku 4.5 (Anthropic Ireland, hébergement UE).
                Anthropic ne réutilise pas vos données pour entraîner ses
                modèles.
              </p>
              <p className="mt-2">
                <strong className="text-vz-ink">Conservation :</strong>{" "}
                profil supprimé après 24&nbsp;mois sans activité ; logs de
                scoring conservés 6&nbsp;mois ; historique d&apos;achats 10&nbsp;ans
                (obligation comptable).
              </p>
              <p className="mt-2">
                <strong className="text-vz-ink">Pas d&apos;activation = pas de PS.</strong>{" "}
                Vous gardez l&apos;accès à votre fidélité, vos offres, votre
                historique et votre wallet&nbsp;— le Personal Shopper est un
                service distinct, optionnel et désactivable.{" "}
                <Link
                  href="/confidentialite#personal-shopper"
                  className="underline underline-offset-2 hover:text-vz-teal"
                >
                  Politique complète
                </Link>
                .
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => recordProfilingDecision(true)}
                disabled={toggleBusy}
                className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {toggleBusy ? "Enregistrement…" : "J'accepte et j'active mon Personal Shopper"}
              </button>
              <button
                onClick={() => recordProfilingDecision(false)}
                disabled={toggleBusy}
                className="inline-flex items-center justify-center rounded-full border border-vz-ink/20 text-vz-ink px-7 py-3 text-sm font-medium hover:bg-vz-ink hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Continuer sans Personal Shopper
              </button>
            </div>

            <p className="mt-4 text-xs text-vz-ink-mute">
              Votre choix est tracé dans nos registres avec horodatage et version
              de politique en cours, conformément à l&apos;article&nbsp;7-1 RGPD.
              Vous pouvez le modifier à tout moment depuis votre espace client.
            </p>
          </section>
        )}

        {emailLocked && !gate && (
          <>
            <form
              onSubmit={submitSearch}
              className="mb-3 flex flex-col sm:flex-row gap-2"
              aria-describedby="shopper-search-hint"
            >
              <label htmlFor="shopper-search" className="sr-only">
                Recherche libre, interprétée par notre IA
              </label>
              <input
                id="shopper-search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder='Ex : "t-shirt blanc taille M"'
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
              />
              <button
                type="submit"
                disabled={searchBusy || !searchQuery.trim()}
                className="bg-vz-teal text-white px-6 py-3 rounded-lg font-medium hover:bg-vz-teal/90 disabled:opacity-50"
              >
                {searchBusy ? "…" : "Rechercher"}
              </button>
            </form>
            <p
              id="shopper-search-hint"
              className="text-xs text-vz-ink-mute mb-8"
            >
              Votre requête est interprétée par notre IA pour extraire taille,
              couleur et marque, puis croisée avec le stock réel de la boutique.
            </p>

            {searchResults === null && items.length === 0 && !loading ? (
              <AssumedEmptyState message={feedMessage} />
            ) : (
              <ProductGrid
                items={searchResults ?? items}
                empty="Aucun produit ne correspond à cette recherche."
                cacheHit={searchResults ? searchCacheHit : false}
              />
            )}
          </>
        )}

        {error && (
          <div className="mt-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
        )}
      </>
    </AccountShell>
  );
}

/**
 * Assumed empty state for the live feed (PS 360 §3.2 "assumer l'attente").
 * Shown when the member has no taste signal yet or nothing in stock matches —
 * we own the wait rather than padding with generic stock.
 */
function AssumedEmptyState({ message }: { message: string }) {
  return (
    <section className="bg-vz-surface border border-vz-line rounded-2xl p-8 max-w-2xl text-center">
      <p className="text-3xl mb-3">🪡</p>
      <h2 className="text-xl font-display font-semibold text-vz-ink mb-2">
        Rien de neuf pour vous aujourd&apos;hui
      </h2>
      <p className="text-vz-ink-soft leading-relaxed mb-6">
        {message ||
          "Dès qu'une pièce qui vous ressemble arrive en boutique, on vous écrit. Notre stock est unique et tourne vite — pas de pièce générique ici."}
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link
          href="/account/onboarding"
          className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-6 py-3 text-sm font-medium hover:bg-vz-teal-deep"
        >
          Affiner mon profil
        </Link>
        <Link
          href="/account/selection"
          className="inline-flex items-center justify-center rounded-full border border-vz-line text-vz-ink px-6 py-3 text-sm font-medium hover:border-vz-teal"
        >
          Voir la sélection du moment
        </Link>
      </div>
      <p className="mt-4 text-xs text-vz-ink-mute">
        Vous recevrez une alerte e-mail dès qu&apos;une nouveauté correspond à
        vos goûts.
      </p>
    </section>
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
      {/*
        AI Act art. 50-2 — marquage machine-readable des sorties IA :
        data-ai-generated="true" + role="region" + aria-label sur le
        conteneur, badge IA sur chaque card.
      */}
      <section
        aria-label="Recommandations générées par intelligence artificielle"
        data-ai-generated="true"
        data-ai-source="claude-haiku-4-5"
        className="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        {items.map((item) => (
          <article
            key={item.product_id}
            data-ai-generated="true"
            aria-label={`Recommandation IA : ${item.name}`}
            className="relative bg-white rounded-2xl shadow-sm overflow-hidden flex flex-col"
          >
            <div className="aspect-square bg-gray-100 relative">
              {item.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={mediaUrl(item.photo_url)} alt={item.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-4xl text-gray-300">
                  👗
                </div>
              )}
              <AiBadge className="absolute top-2 left-2 shadow-sm" />
            </div>
            <div className="p-3 flex-1 flex flex-col gap-1">
              <h3 className="text-sm font-medium text-black line-clamp-2">{item.name}</h3>
              <p className="text-xs text-gray-500">
                {[item.size, item.color].filter(Boolean).join(" · ") || "—"}
              </p>
              <p className="text-base font-semibold text-vz-teal mt-auto">{formatPriceCents(item.price_cents)}</p>
              <p className="text-xs text-gray-500">En boutique · Vernon</p>
            </div>
          </article>
        ))}
      </section>
    </>
  );
}
