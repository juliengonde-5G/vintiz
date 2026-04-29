"use client";

import { useEffect, useState, FormEvent } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Option {
  key: string;
  label: string;
  emoji?: string;
}

interface Catalogue {
  styles: Option[];
  occasions: Option[];
  price_buckets: Option[];
}

export default function OnboardingPage() {
  const [email, setEmail] = useState("");
  const [emailLocked, setEmailLocked] = useState(false);
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [loadingCatalogue, setLoadingCatalogue] = useState(true);

  const [styles, setStyles] = useState<Set<string>>(new Set());
  const [occasions, setOccasions] = useState<Set<string>>(new Set());
  const [priceBuckets, setPriceBuckets] = useState<Set<string>>(new Set());

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setLoadingCatalogue(true);
    fetch(`${API_URL}/api/crm/onboarding/options`, { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => setCatalogue(data))
      .catch(() => setError("Impossible de charger les options."))
      .finally(() => setLoadingCatalogue(false));
  }, []);

  // Pre-fill email from query string if the customer arrived via a magic
  // link from /account.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("email");
    if (fromQuery) {
      setEmail(fromQuery);
      setEmailLocked(true);
    }
  }, []);

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, key: string) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setter(next);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Renseignez l'email associé à votre carte fidélité.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/onboarding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          liked_style_keys: Array.from(styles),
          preferred_occasions: Array.from(occasions),
          preferred_price_buckets: Array.from(priceBuckets),
          preferred_categories: [],
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.detail || "Erreur lors de l'enregistrement.");
      } else {
        setDone(true);
      }
    } catch {
      setError("Impossible de contacter le serveur.");
    }
    setSubmitting(false);
  };

  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-vz-bg py-12 px-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-3xl font-bold text-black font-display mb-2">
            Personnalisez votre Personal Shopper
          </h1>
          <p className="text-gray-600 mb-8">
            En 1 minute, dites-nous ce qui vous plaît : nous calibrons votre
            sélection de pièces, en attendant que vos achats parlent
            d&apos;eux-mêmes.
          </p>

          {done ? (
            <div className="bg-white rounded-2xl shadow-sm p-8 text-center space-y-4">
              <p className="text-2xl">✨</p>
              <h2 className="text-xl font-semibold text-black">
                Profil enregistré
              </h2>
              <p className="text-gray-600">
                Votre Personal Shopper est calibré. À votre prochaine visite en
                boutique, demandez la sélection à Sophie&nbsp;!
              </p>
              <Link
                href="/account"
                className="inline-block px-4 py-2 bg-vz-teal text-white rounded-lg hover:bg-vz-teal-deep"
              >
                Voir mon espace
              </Link>
            </div>
          ) : loadingCatalogue ? (
            <div className="text-center text-gray-500 py-12">Chargement…</div>
          ) : catalogue ? (
            <form
              onSubmit={submit}
              className="space-y-8 bg-white rounded-2xl shadow-sm p-6"
            >
              {/* Email */}
              <section>
                <label className="block text-sm font-medium text-black mb-2">
                  Email associé à votre carte fidélité
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={emailLocked || submitting}
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vz-teal disabled:bg-gray-50"
                  placeholder="prenom.nom@exemple.fr"
                />
              </section>

              {/* Style picker */}
              <section>
                <h2 className="text-lg font-semibold text-black mb-1">
                  1. Quel(s) style(s) vous parle(nt) ?
                </h2>
                <p className="text-xs text-gray-500 mb-3">
                  Sélectionnez ceux qui vous correspondent — vous pouvez en
                  prendre plusieurs ou aucun.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {catalogue.styles.map((s) => {
                    const active = styles.has(s.key);
                    return (
                      <button
                        type="button"
                        key={s.key}
                        onClick={() => toggle(styles, setStyles, s.key)}
                        className={`flex flex-col items-center gap-1 p-4 rounded-xl border-2 transition-all ${
                          active
                            ? "border-vz-teal bg-vz-teal-soft/50"
                            : "border-gray-200 bg-white hover:border-vz-accent-soft"
                        }`}
                      >
                        <span className="text-2xl">{s.emoji || "✦"}</span>
                        <span className="text-sm font-medium">{s.label}</span>
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* Occasions */}
              <section>
                <h2 className="text-lg font-semibold text-black mb-1">
                  2. Pour quelles occasions ?
                </h2>
                <p className="text-xs text-gray-500 mb-3">
                  Une ou plusieurs.
                </p>
                <div className="flex flex-wrap gap-2">
                  {catalogue.occasions.map((o) => {
                    const active = occasions.has(o.key);
                    return (
                      <button
                        type="button"
                        key={o.key}
                        onClick={() => toggle(occasions, setOccasions, o.key)}
                        className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                          active
                            ? "bg-vz-teal text-white border-vz-teal"
                            : "bg-white text-gray-600 border-gray-200 hover:border-vz-teal"
                        }`}
                      >
                        {o.label}
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* Price buckets */}
              <section>
                <h2 className="text-lg font-semibold text-black mb-1">
                  3. Quel budget par pièce ?
                </h2>
                <p className="text-xs text-gray-500 mb-3">
                  Cela nous aide à filtrer les bonnes affaires.
                </p>
                <div className="flex flex-wrap gap-2">
                  {catalogue.price_buckets.map((p) => {
                    const active = priceBuckets.has(p.key);
                    return (
                      <button
                        type="button"
                        key={p.key}
                        onClick={() => toggle(priceBuckets, setPriceBuckets, p.key)}
                        className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                          active
                            ? "bg-vz-accent-soft text-vz-accent border-vz-accent-soft"
                            : "bg-white text-gray-600 border-gray-200 hover:border-vz-accent-soft"
                        }`}
                      >
                        {p.label}
                      </button>
                    );
                  })}
                </div>
              </section>

              {error && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting || !email.trim()}
                className="w-full py-3 bg-vz-teal text-white font-medium rounded-lg hover:bg-vz-teal-deep disabled:opacity-50"
              >
                {submitting ? "Enregistrement…" : "Calibrer mon Personal Shopper"}
              </button>
              <p className="text-xs text-gray-400 text-center">
                Vos choix nourrissent uniquement votre Personal Shopper. Vous
                pouvez les modifier ou les retirer à tout moment depuis votre{" "}
                <Link href="/account" className="text-vz-teal underline">
                  espace données
                </Link>
                .
              </p>
            </form>
          ) : (
            <div className="text-red-600">{error}</div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
