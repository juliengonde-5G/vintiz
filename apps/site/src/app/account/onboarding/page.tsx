"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PublicHeader from "@/components/PublicHeader";
import Footer from "@/components/Footer";
import { mediaUrl } from "@/lib/media";
import { formatPriceCents } from "@/lib/format";
import { accountFetch } from "@/lib/account-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Option {
  key: string;
  label: string;
  emoji?: string;
}

interface Catalogue {
  genders: Option[];
  age_bands: Option[];
  styles: Option[];
  occasions: Option[];
  price_buckets: Option[];
  brands: Option[];
}

interface VisualCandidate {
  id: string;
  name: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  price_cents: number;
  photo_url: string | null;
}

const FALLBACK_GRADIENTS = [
  "linear-gradient(140deg, #cdd6c8, #8aa092)",
  "linear-gradient(140deg, #e8d4c2, #c2937a)",
  "linear-gradient(140deg, #ddd9c8, #8e7b57)",
  "linear-gradient(140deg, #cde5df, #0b7a6a)",
];

type Step = 1 | 2 | 3;

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);

  const [email, setEmail] = useState("");
  const [emailLocked, setEmailLocked] = useState(false);

  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [loadingCatalogue, setLoadingCatalogue] = useState(true);

  // Layer 1 — declarative (mandatory).
  const [gender, setGender] = useState<string | null>(null);
  const [ageBand, setAgeBand] = useState<string | null>(null);

  // Layer 2 — visual cold-start.
  const [candidates, setCandidates] = useState<VisualCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [liked, setLiked] = useState<Set<string>>(new Set());

  // Layer 3 — detailed (optional).
  const [styles, setStyles] = useState<Set<string>>(new Set());
  const [occasions, setOccasions] = useState<Set<string>>(new Set());
  const [priceBuckets, setPriceBuckets] = useState<Set<string>>(new Set());
  const [brands, setBrands] = useState<Set<string>>(new Set());

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

  // Pre-fill email from the magic-link session or the query string.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("email");
    if (fromQuery) {
      setEmail(fromQuery);
      setEmailLocked(true);
      return;
    }
    try {
      const stored = window.localStorage.getItem("vintiz_account_email");
      if (stored) setEmail(stored);
    } catch {
      /* private mode — let the customer type their email */
    }
  }, []);

  const toggle = (
    set: Set<string>,
    setter: (s: Set<string>) => void,
    key: string,
  ) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setter(next);
  };

  // Fetch the visual cold-start candidates once layer 1 is settled, narrowed
  // to the declared gender.
  const loadCandidates = async () => {
    setLoadingCandidates(true);
    try {
      const qs = new URLSearchParams({ n: "8" });
      if (gender && gender !== "mixte") qs.set("gender", gender);
      const res = await fetch(
        `${API_URL}/api/crm/onboarding/visual-candidates?${qs.toString()}`,
        { cache: "no-store" },
      );
      const body = await res.json().catch(() => ({}));
      setCandidates(body.items ?? []);
    } catch {
      setCandidates([]);
    }
    setLoadingCandidates(false);
  };

  const goToStep2 = () => {
    if (!email.trim()) {
      setError("Renseignez l'email associé à votre carte fidélité.");
      return;
    }
    if (!gender || !ageBand) {
      setError("Indiquez le rayon qui vous intéresse et votre tranche d'âge.");
      return;
    }
    setError("");
    setStep(2);
    if (candidates.length === 0) void loadCandidates();
  };

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const res = await accountFetch(`${API_URL}/api/crm/account/onboarding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          gender,
          age_band: ageBand,
          liked_product_ids: Array.from(liked),
          liked_style_keys: Array.from(styles),
          preferred_occasions: Array.from(occasions),
          preferred_price_buckets: Array.from(priceBuckets),
          preferred_brands: Array.from(brands),
          preferred_categories: [],
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.detail || "Erreur lors de l'enregistrement.");
      } else {
        // Persist the email so the shopper page auto-loads the selection
        // without re-asking it (#4), then land on the selection (#9). The
        // shopper handles the loyalty gate with a one-click subscribe (#3).
        try {
          window.localStorage.setItem(
            "vintiz_account_email",
            email.trim().toLowerCase(),
          );
        } catch {
          /* private mode — shopper will ask once */
        }
        setDone(true);
        router.push("/account/shopper");
      }
    } catch {
      setError("Impossible de contacter le serveur.");
    }
    setSubmitting(false);
  };

  const stepLabels = ["Vous", "Vos coups de cœur", "Affiner"];

  return (
    <>
      <PublicHeader />
      <main className="min-h-screen bg-vz-bg py-12 px-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-3xl font-bold text-vz-ink font-display mb-2">
            Activez votre Personal Shopper
          </h1>
          <p className="text-vz-ink-soft mb-8">
            Quelques secondes pour calibrer votre sélection. Dès qu&apos;une
            pièce qui vous ressemble arrive, on vous écrit — pas besoin de
            scroller, c&apos;est nous qui cherchons.
          </p>

          {done ? (
            <div className="bg-vz-surface rounded-2xl shadow-sm p-8 text-center space-y-4">
              <p className="text-2xl">✨</p>
              <h2 className="text-xl font-semibold text-vz-ink">
                Profil enregistré
              </h2>
              <p className="text-vz-ink-soft">
                Votre Personal Shopper est calibré. Vous recevrez un mot dès
                qu&apos;une pièce qui vous ressemble arrive en boutique.
              </p>
              <Link
                href="/account/shopper"
                className="inline-block px-4 py-2 bg-vz-teal text-white rounded-lg hover:bg-vz-teal-deep"
              >
                Voir ma sélection
              </Link>
            </div>
          ) : loadingCatalogue ? (
            <div className="text-center text-vz-ink-mute py-12">Chargement…</div>
          ) : catalogue ? (
            <div className="space-y-8 bg-vz-surface rounded-2xl shadow-sm p-6">
              {/* Stepper */}
              <ol className="flex items-center gap-2 text-xs font-medium">
                {stepLabels.map((label, i) => {
                  const n = (i + 1) as Step;
                  const active = step === n;
                  const doneStep = step > n;
                  return (
                    <li key={label} className="flex items-center gap-2">
                      <span
                        className={`flex h-6 w-6 items-center justify-center rounded-full ${
                          active
                            ? "bg-vz-teal text-white"
                            : doneStep
                              ? "bg-vz-teal-soft text-vz-teal-deep"
                              : "bg-vz-bg-alt text-vz-ink-mute"
                        }`}
                      >
                        {doneStep ? "✓" : n}
                      </span>
                      <span
                        className={
                          active ? "text-vz-ink" : "text-vz-ink-mute"
                        }
                      >
                        {label}
                      </span>
                      {n < 3 && <span className="text-vz-line">—</span>}
                    </li>
                  );
                })}
              </ol>

              {/* ---------------- Step 1 — Layer 1 (mandatory) ------------- */}
              {step === 1 && (
                <div className="space-y-8">
                  <section>
                    <label className="block text-sm font-medium text-vz-ink mb-2">
                      Email associé à votre carte fidélité
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      disabled={emailLocked || submitting}
                      className="w-full px-4 py-3 border border-vz-line rounded-lg focus:outline-none focus:ring-2 focus:ring-vz-teal disabled:bg-vz-bg-alt"
                      placeholder="prenom.nom@exemple.fr"
                    />
                  </section>

                  <section>
                    <h2 className="text-lg font-semibold text-vz-ink mb-1">
                      Quel rayon vous intéresse ?
                    </h2>
                    <p className="text-xs text-vz-ink-mute mb-3">
                      On adapte la sélection à ce que vous cherchez.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {catalogue.genders.map((g) => (
                        <button
                          type="button"
                          key={g.key}
                          onClick={() => setGender(g.key)}
                          className={`px-4 py-2 rounded-full border text-sm transition-colors ${
                            gender === g.key
                              ? "bg-vz-teal text-white border-vz-teal"
                              : "bg-vz-surface text-vz-ink-soft border-vz-line hover:border-vz-teal"
                          }`}
                        >
                          {g.label}
                        </button>
                      ))}
                    </div>
                  </section>

                  <section>
                    <h2 className="text-lg font-semibold text-vz-ink mb-1">
                      Votre tranche d&apos;âge
                    </h2>
                    <p className="text-xs text-vz-ink-mute mb-3">
                      Pour nuancer les styles et les marques proposés.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {catalogue.age_bands.map((a) => (
                        <button
                          type="button"
                          key={a.key}
                          onClick={() => setAgeBand(a.key)}
                          className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                            ageBand === a.key
                              ? "bg-vz-teal text-white border-vz-teal"
                              : "bg-vz-surface text-vz-ink-soft border-vz-line hover:border-vz-teal"
                          }`}
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                  </section>

                  {error && (
                    <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                      {error}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={goToStep2}
                    className="w-full py-3 bg-vz-teal text-white font-medium rounded-lg hover:bg-vz-teal-deep"
                  >
                    Continuer
                  </button>
                </div>
              )}

              {/* ---------------- Step 2 — Layer 2 (visual) --------------- */}
              {step === 2 && (
                <div className="space-y-6">
                  <section>
                    <h2 className="text-lg font-semibold text-vz-ink mb-1">
                      Vos coups de cœur
                    </h2>
                    <p className="text-xs text-vz-ink-mute mb-4">
                      Touchez les pièces qui vous plaisent — elles affinent
                      tout de suite votre profil. Étape facultative.
                    </p>
                    {loadingCandidates ? (
                      <div className="text-center text-vz-ink-mute py-8">
                        Chargement des pièces…
                      </div>
                    ) : candidates.length === 0 ? (
                      <p className="text-sm text-vz-ink-mute py-4">
                        Pas de pièce à afficher pour l&apos;instant — vous
                        pourrez revenir plus tard.
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {candidates.map((c, idx) => {
                          const isLiked = liked.has(c.id);
                          return (
                            <button
                              type="button"
                              key={c.id}
                              onClick={() => toggle(liked, setLiked, c.id)}
                              className={`group relative overflow-hidden rounded-xl border-2 text-left transition-all ${
                                isLiked
                                  ? "border-vz-teal ring-2 ring-vz-teal-soft"
                                  : "border-vz-line hover:border-vz-teal"
                              }`}
                            >
                              <div
                                className="aspect-[3/4] w-full"
                                style={{
                                  background: c.photo_url
                                    ? `url(${mediaUrl(c.photo_url)}) center/cover`
                                    : FALLBACK_GRADIENTS[
                                        idx % FALLBACK_GRADIENTS.length
                                      ],
                                }}
                              />
                              <span
                                className={`absolute top-2 right-2 flex h-7 w-7 items-center justify-center rounded-full text-sm ${
                                  isLiked
                                    ? "bg-vz-teal text-white"
                                    : "bg-vz-surface/80 text-vz-ink-mute"
                                }`}
                              >
                                {isLiked ? "♥" : "♡"}
                              </span>
                              <div className="p-2">
                                <p className="text-xs font-medium text-vz-ink truncate">
                                  {c.name}
                                </p>
                                <p className="text-xs text-vz-ink-mute">
                                  {formatPriceCents(c.price_cents)}
                                </p>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </section>

                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => setStep(1)}
                      className="px-4 py-3 rounded-lg border border-vz-line text-vz-ink-soft hover:border-vz-teal"
                    >
                      Retour
                    </button>
                    <button
                      type="button"
                      onClick={() => setStep(3)}
                      className="flex-1 py-3 bg-vz-teal text-white font-medium rounded-lg hover:bg-vz-teal-deep"
                    >
                      {liked.size > 0
                        ? `Continuer (${liked.size} sélectionnée${liked.size > 1 ? "s" : ""})`
                        : "Passer cette étape"}
                    </button>
                  </div>
                </div>
              )}

              {/* ---------------- Step 3 — Layer 3 (detailed) ------------- */}
              {step === 3 && (
                <div className="space-y-8">
                  <section>
                    <h2 className="text-lg font-semibold text-vz-ink mb-1">
                      Quel(s) style(s) vous parle(nt) ?
                    </h2>
                    <p className="text-xs text-vz-ink-mute mb-3">
                      Facultatif — un ou plusieurs.
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
                                : "border-vz-line bg-vz-surface hover:border-vz-teal"
                            }`}
                          >
                            <span className="text-2xl">{s.emoji || "✦"}</span>
                            <span className="text-sm font-medium">
                              {s.label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section>
                    <h2 className="text-lg font-semibold text-vz-ink mb-1">
                      Pour quelles occasions ?
                    </h2>
                    <div className="flex flex-wrap gap-2">
                      {catalogue.occasions.map((o) => {
                        const active = occasions.has(o.key);
                        return (
                          <button
                            type="button"
                            key={o.key}
                            onClick={() =>
                              toggle(occasions, setOccasions, o.key)
                            }
                            className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                              active
                                ? "bg-vz-teal text-white border-vz-teal"
                                : "bg-vz-surface text-vz-ink-soft border-vz-line hover:border-vz-teal"
                            }`}
                          >
                            {o.label}
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section>
                    <h2 className="text-lg font-semibold text-vz-ink mb-1">
                      Quel budget par pièce ?
                    </h2>
                    <div className="flex flex-wrap gap-2">
                      {catalogue.price_buckets.map((p) => {
                        const active = priceBuckets.has(p.key);
                        return (
                          <button
                            type="button"
                            key={p.key}
                            onClick={() =>
                              toggle(priceBuckets, setPriceBuckets, p.key)
                            }
                            className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                              active
                                ? "bg-vz-accent-soft text-vz-accent border-vz-accent-soft"
                                : "bg-vz-surface text-vz-ink-soft border-vz-line hover:border-vz-accent-soft"
                            }`}
                          >
                            {p.label}
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  {catalogue.brands.length > 0 && (
                    <section>
                      <h2 className="text-lg font-semibold text-vz-ink mb-1">
                        Des marques que vous aimez ?
                      </h2>
                      <p className="text-xs text-vz-ink-mute mb-3">
                        Facultatif — parmi celles en boutique.
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {catalogue.brands.map((b) => {
                          const active = brands.has(b.key);
                          return (
                            <button
                              type="button"
                              key={b.key}
                              onClick={() => toggle(brands, setBrands, b.key)}
                              className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
                                active
                                  ? "bg-vz-teal text-white border-vz-teal"
                                  : "bg-vz-surface text-vz-ink-soft border-vz-line hover:border-vz-teal"
                              }`}
                            >
                              {b.label}
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  )}

                  {error && (
                    <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                      {error}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => setStep(2)}
                      className="px-4 py-3 rounded-lg border border-vz-line text-vz-ink-soft hover:border-vz-teal"
                    >
                      Retour
                    </button>
                    <button
                      type="button"
                      onClick={submit}
                      disabled={submitting}
                      className="flex-1 py-3 bg-vz-teal text-white font-medium rounded-lg hover:bg-vz-teal-deep disabled:opacity-50"
                    >
                      {submitting
                        ? "Enregistrement…"
                        : "Activer mon Personal Shopper"}
                    </button>
                  </div>
                </div>
              )}

              <p className="text-xs text-vz-ink-mute text-center">
                Vos choix nourrissent uniquement votre Personal Shopper. Vous
                pouvez les modifier ou les retirer à tout moment depuis votre{" "}
                <Link href="/account/rgpd" className="text-vz-teal underline">
                  espace données
                </Link>
                .
              </p>
            </div>
          ) : (
            <div className="text-red-600">{error}</div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
