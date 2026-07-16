"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";
import AccountTabs from "@/components/account/AccountTabs";
import LoyaltyHeroCard from "@/components/account/LoyaltyHeroCard";
import { accountFetch } from "@/lib/account-api";

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

interface Coupon {
  code: string;
  description: string;
  discount_eur: number;
  expires_at: string | null;
}

interface Transaction {
  id: string;
  transaction_number: number;
  total_ttc: number;
  created_at: string;
  item_count: number;
}

const ZONES: { href: string; label: string; hint: string }[] = [
  { href: "/account/fidelite", label: "Ma carte fidélité", hint: "QR + Wallet" },
  { href: "/account/shopper", label: "Personal Shopper", hint: "Sélection IA" },
  { href: "/account/selection", label: "Sélection du moment", hint: "Curation manager" },
  { href: "/account/offres", label: "Offres", hint: "Coupons actifs" },
  { href: "/account/historique", label: "Mes achats", hint: "Tickets téléchargeables" },
  { href: "/account/rgpd", label: "Confidentialité", hint: "Export, suppression" },
];

export default function AccountHomePage() {
  const [email, setEmail] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"recompenses" | "offres" | "historique">("recompenses");
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [history, setHistory] = useState<Transaction[]>([]);
  const [flash, setFlash] = useState<string | null>(null);

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
    // One-shot flash messages posés par d'autres pages (ex. décline du
    // consent Personal Shopper depuis /account/shopper).
    try {
      const msg = window.sessionStorage.getItem("vintiz_account_flash");
      if (msg) {
        setFlash(msg);
        window.sessionStorage.removeItem("vintiz_account_flash");
      }
    } catch {
      /* sessionStorage indispo en mode privé */
    }
  }, []);

  // Reload tab content lazily when switching tabs
  useEffect(() => {
    if (!email) return;
    if (tab === "offres" && coupons.length === 0) {
      accountFetch(`${API_URL}/api/crm/account/coupons?email=${encodeURIComponent(email)}`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (Array.isArray(d)) setCoupons(d as Coupon[]);
          else if (d?.coupons) setCoupons(d.coupons as Coupon[]);
        })
        .catch(() => undefined);
    }
    if (tab === "historique" && history.length === 0) {
      accountFetch(`${API_URL}/api/crm/account/transactions?email=${encodeURIComponent(email)}&limit=10`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (Array.isArray(d)) setHistory(d as Transaction[]);
          else if (d?.transactions) setHistory(d.transactions as Transaction[]);
        })
        .catch(() => undefined);
    }
  }, [tab, email, coupons.length, history.length]);

  const load = async (target: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await accountFetch(
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
          className="inline-flex items-center gap-2 bg-vz-teal text-white px-6 py-3 rounded-full font-medium hover:bg-vz-teal-deep transition-colors"
        >
          Recevoir un code par email
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </Link>
      </AccountShell>
    );
  }

  const points = profile?.loyalty?.points ?? 0;
  const featuredCoupon = coupons[0];

  return (
    <AccountShell
      title="Mon espace"
      intro={profile ? `Heureux de vous revoir, ${profile.client.first_name}.` : undefined}
    >
      {flash && (
        <div
          role="status"
          className="mb-6 rounded-xl border border-vz-teal/30 bg-vz-teal-soft/40 px-4 py-3 text-sm text-vz-ink-soft flex items-start gap-3"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            className="mt-0.5 shrink-0 text-vz-teal"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <p className="leading-relaxed">{flash}</p>
          <button
            type="button"
            onClick={() => setFlash(null)}
            aria-label="Fermer"
            className="ml-auto text-vz-ink-mute hover:text-vz-ink"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}
      {loading && <p className="text-vz-ink-mute">Chargement…</p>}
      {error && <p className="text-red-700">{error}</p>}
      {profile && (
        <div className="space-y-8">
          {/* Hero card fidélité */}
          <LoyaltyHeroCard
            firstName={profile.client.first_name}
            membershipNumber={profile.loyalty?.membership_number ?? null}
            points={points}
          />

          {/* Featured offer (encartée magenta dashed) */}
          {featuredCoupon && (
            <aside className="rounded-vz-lg p-5 bg-vz-accent-soft border-2 border-dashed border-vz-accent">
              <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-accent font-semibold">
                Offre du moment
              </p>
              <p className="mt-2 font-display text-xl text-vz-ink">
                {featuredCoupon.description || `Bon de ${featuredCoupon.discount_eur.toFixed(0)} €`}
              </p>
              <p className="mt-2 inline-block font-mono text-sm bg-white border border-vz-accent/40 rounded px-3 py-1">
                {featuredCoupon.code}
              </p>
              {featuredCoupon.expires_at && (
                <p className="mt-2 text-xs text-vz-ink-mute">
                  Valable jusqu&apos;au {new Date(featuredCoupon.expires_at).toLocaleDateString("fr-FR")}
                </p>
              )}
            </aside>
          )}

          {/* Tabs Récompenses / Offres / Historique */}
          <AccountTabs
            tabs={[
              { key: "recompenses", label: "Récompenses" },
              { key: "offres", label: "Offres" },
              { key: "historique", label: "Historique" },
            ]}
            active={tab}
            onChange={(k) => setTab(k as typeof tab)}
          >
            {tab === "recompenses" && (
              <div className="space-y-3">
                <div className="bg-vz-surface rounded-vz-lg border border-vz-line p-5">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-teal font-semibold">
                    Avoir disponible
                  </p>
                  <p className="font-display text-3xl text-vz-ink mt-2">
                    {profile.client.avoir_balance.toFixed(2)} €
                  </p>
                  <p className="text-xs text-vz-ink-mute mt-1">
                    Utilisable au prochain passage en caisse — présentez votre numéro {profile.loyalty?.membership_number}.
                  </p>
                </div>
                <p className="text-sm text-vz-ink-soft leading-relaxed">
                  Chaque euro dépensé sur un article hors promotion, solde ou remise rapporte un point. À 100 points cumulés, un chèque cadeau de
                  5 € est crédité automatiquement sur votre carte. Les points expirent après 24 mois sans activité.
                </p>
              </div>
            )}
            {tab === "offres" && (
              <div className="space-y-2">
                {coupons.length === 0 ? (
                  <p className="text-sm text-vz-ink-mute">Aucune offre active pour le moment.</p>
                ) : (
                  coupons.map((c) => (
                    <div key={c.code} className="bg-vz-surface rounded-vz-lg border border-vz-line p-4 flex items-baseline justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-vz-ink">{c.description || `Bon de ${c.discount_eur.toFixed(0)} €`}</p>
                        {c.expires_at && (
                          <p className="text-xs text-vz-ink-mute mt-0.5">
                            Jusqu&apos;au {new Date(c.expires_at).toLocaleDateString("fr-FR")}
                          </p>
                        )}
                      </div>
                      <span className="font-mono text-xs text-vz-teal-deep bg-vz-teal-soft rounded px-2 py-1 whitespace-nowrap">
                        {c.code}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
            {tab === "historique" && (
              <div className="space-y-2">
                {history.length === 0 ? (
                  <p className="text-sm text-vz-ink-mute">Vous n&apos;avez pas encore d&apos;achat enregistré.</p>
                ) : (
                  history.map((t) => (
                    <div key={t.id} className="flex items-baseline justify-between gap-3 border-b border-vz-line pb-3 last:border-0">
                      <div className="min-w-0">
                        <p className="font-mono text-xs text-vz-ink-mute">
                          #{t.transaction_number} · {new Date(t.created_at).toLocaleDateString("fr-FR")}
                        </p>
                        <p className="text-sm text-vz-ink-soft">
                          {t.item_count} article{t.item_count > 1 ? "s" : ""}
                        </p>
                      </div>
                      <p className="font-display text-base text-vz-ink">
                        {t.total_ttc.toFixed(2)} €
                      </p>
                    </div>
                  ))
                )}
                <div className="pt-2">
                  <Link href="/account/historique" className="text-sm font-medium text-vz-teal hover:text-vz-teal-deep">
                    Voir l&apos;historique complet →
                  </Link>
                </div>
              </div>
            )}
          </AccountTabs>

          {/* Zone shortcuts (chip-style, minimal) */}
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-ink-mute mb-3">
              Mon espace
            </p>
            <div className="flex flex-wrap gap-2">
              {ZONES.map((z) => (
                <Link
                  key={z.href}
                  href={z.href}
                  className="group inline-flex items-center gap-2 bg-vz-surface border border-vz-line rounded-full px-4 py-2 text-sm text-vz-ink hover:border-vz-teal hover:text-vz-teal transition-colors"
                >
                  <span>{z.label}</span>
                  <span className="text-xs text-vz-ink-mute group-hover:text-vz-teal/80">{z.hint}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </AccountShell>
  );
}
