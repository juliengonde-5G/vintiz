"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, FormEvent } from "react";

const INSTAGRAM_URL = "https://www.instagram.com/vintiz.vernon/";
const FACEBOOK_URL = "https://www.facebook.com/vintiz.vernon";
const TIKTOK_URL = "https://www.tiktok.com/@vintiz.vernon";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PreviewProduct {
  id: string;
  name: string;
  brand: string | null;
  size: string | null;
  sale_price: number;
  photo_url: string | null;
}

const PLACEHOLDER_PRODUCTS: PreviewProduct[] = [
  { id: "p1", name: "Marinière", brand: "Petit Bateau", size: "36", sale_price: 18, photo_url: null },
  { id: "p2", name: "Robe lin écru", brand: "Sandro", size: "38", sale_price: 78, photo_url: null },
  { id: "p3", name: "Veste en jean", brand: "Sézane", size: "M", sale_price: 54, photo_url: null },
  { id: "p4", name: "Pull cachemire", brand: "Maje", size: "S", sale_price: 42, photo_url: null },
  { id: "p5", name: "Pantalon large", brand: "Ba&sh", size: "38", sale_price: 62, photo_url: null },
  { id: "p6", name: "Sac bandoulière", brand: "Polène", size: "—", sale_price: 195, photo_url: null },
];

const STAT_GRADIENTS = [
  "linear-gradient(140deg, #cdd6c8, #8aa092)",
  "linear-gradient(140deg, #e8d4c2, #c2937a)",
  "linear-gradient(140deg, #ddd9c8, #8e7b57)",
  "linear-gradient(140deg, #cde5df, #0b7a6a)",
  "linear-gradient(140deg, #ffd5e5, #e84e8b)",
  "linear-gradient(140deg, #d8cbb6, #b9a486)",
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [products, setProducts] = useState<PreviewProduct[]>(PLACEHOLDER_PRODUCTS);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/inventory/products?limit=6&display=true`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        const list: PreviewProduct[] = (Array.isArray(data) ? data : data.products || [])
          .slice(0, 6)
          .map((p: Record<string, unknown>) => ({
            id: String(p.id),
            name: String(p.name || ""),
            brand: (p.brand as string) || null,
            size: (p.size as string) || null,
            sale_price: Number(p.sale_price || 0),
            photo_url: (p.photo_url as string) || null,
          }));
        if (list.length > 0) setProducts(list);
      })
      .catch(() => {
        // Keep placeholders on network failure — landing must always render.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!consent) {
      setStatus("error");
      setMessage("Merci de cocher la case de consentement pour recevoir nos e-mails.");
      return;
    }
    setStatus("loading");
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, consent, source: "site_landing" }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("success");
        setMessage(data.message);
        setEmail("");
        setConsent(false);
      } else {
        setStatus("error");
        setMessage(data.error || data.detail || "Une erreur est survenue.");
      }
    } catch {
      setStatus("error");
      setMessage("Une erreur est survenue. Veuillez réessayer.");
    }
  }

  return (
    <main className="min-h-screen flex flex-col bg-vz-bg">
      {/* Top bar */}
      <header className="border-b border-vz-line">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2" aria-label="Vintiz Vernon">
            <Image src="/logo-teal.png" alt="Vintiz" width={36} height={36} className="h-8 w-auto" />
            <span className="font-display text-xl text-vz-ink">Vintiz</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <a href="#selection" className="text-vz-ink-soft hover:text-vz-teal transition-colors">
              Sélection
            </a>
            <Link href="/account" className="text-vz-teal font-medium hover:text-vz-teal-deep transition-colors">
              Mon espace
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero — LandingSauge */}
      <section className="border-b border-vz-line">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-24">
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-vz-teal">
            Capsule · Printemps pré-aimé
          </p>
          <h1 className="mt-4 font-display font-[450] text-5xl md:text-7xl text-vz-ink leading-[1.05] tracking-[-0.015em]">
            Tout a déjà
            <br />
            <em className="not-italic">une histoire.</em>
          </h1>
          <p className="mt-6 text-lg md:text-xl text-vz-ink-soft max-w-xl leading-relaxed">
            {products.length > 0 ? products.length : "Plusieurs"} pièces sélectionnées à Vernon. Documentées une à une.
            À porter de nouveau.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#selection"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-vz-teal text-white font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Voir la sélection
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </a>
            <Link
              href="/account/login"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-full border border-vz-ink/15 text-vz-ink hover:bg-white transition-colors"
            >
              Espace fidélité
            </Link>
          </div>
        </div>
      </section>

      {/* Stats bar — 3 chiffres clés sur séparateurs verticaux */}
      <section className="border-b border-vz-line bg-vz-bg-alt/50">
        <div className="max-w-6xl mx-auto px-6 py-10 grid grid-cols-3 divide-x divide-vz-line">
          <div className="px-4">
            <p className="font-display text-3xl md:text-4xl font-[450] text-vz-ink">482</p>
            <p className="text-xs uppercase tracking-[0.18em] text-vz-ink-mute mt-1">pièces actives</p>
          </div>
          <div className="px-4">
            <p className="font-display text-3xl md:text-4xl font-[450] text-vz-ink">68 %</p>
            <p className="text-xs uppercase tracking-[0.18em] text-vz-ink-mute mt-1">marques premium</p>
          </div>
          <div className="px-4">
            <p className="font-display text-3xl md:text-4xl font-[450] text-vz-ink">
              241<span className="font-mono text-xl text-vz-ink-mute"> kg</span>
            </p>
            <p className="text-xs uppercase tracking-[0.18em] text-vz-ink-mute mt-1">non-jetés</p>
          </div>
        </div>
      </section>

      {/* Pieces grid */}
      <section id="selection" className="border-b border-vz-line">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="flex items-baseline justify-between mb-8">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.22em] text-vz-teal">
                Le rayon
              </p>
              <h2 className="font-display text-3xl md:text-4xl text-vz-ink mt-2">
                À découvrir cette semaine
              </h2>
            </div>
            <Link href="/account" className="hidden md:inline-flex items-center gap-1 text-sm font-medium text-vz-teal hover:text-vz-teal-deep">
              Voir mon espace →
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
            {products.map((p, i) => (
              <article key={p.id} className="bg-vz-surface rounded-vz-lg border border-vz-line overflow-hidden">
                <div
                  className="aspect-[4/5] flex items-end p-3"
                  style={{
                    background: p.photo_url
                      ? `url(${p.photo_url}) center/cover`
                      : STAT_GRADIENTS[i % STAT_GRADIENTS.length],
                  }}
                >
                  <span className="font-mono text-[10px] tracking-[0.2em] uppercase text-white/90 bg-black/30 px-2 py-0.5 rounded">
                    N° {String(i + 1).padStart(3, "0")}
                  </span>
                </div>
                <div className="p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute">
                    {p.brand || "Sans marque"}
                  </p>
                  <p className="mt-1 font-display text-base text-vz-ink leading-tight">
                    <em className="not-italic">{p.name}</em>
                    {p.size && <span className="text-vz-ink-soft text-sm">, T. {p.size}</span>}
                  </p>
                  <p className="mt-2 flex items-baseline justify-between">
                    <span className="font-display text-lg text-vz-teal">{p.sale_price.toFixed(0)} €</span>
                    <span className="text-xs text-vz-ink-mute">à essayer en boutique</span>
                  </p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Newsletter (kept, demoted to a band below the fold) */}
      <section id="newsletter" className="border-b border-vz-line bg-vz-surface">
        <div className="max-w-3xl mx-auto px-6 py-14 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-vz-teal">
            Avant tout le monde
          </p>
          <h2 className="font-display text-2xl md:text-3xl text-vz-ink mt-3">
            Soyez la première informée
          </h2>
          <p className="text-sm text-vz-ink-mute mt-2 max-w-xl mx-auto">
            Ouverture de la boutique, ventes privées, nouveautés — pas de spam, vous pouvez vous désabonner en un clic.
          </p>
          {status === "success" ? (
            <div className="mt-6 inline-block bg-vz-teal-soft border border-vz-teal/30 rounded-lg p-4 text-vz-teal-deep">
              {message}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3 max-w-lg mx-auto">
              <div className="flex flex-col sm:flex-row gap-3">
                <label htmlFor="email" className="sr-only">Adresse email</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="votre@email.fr"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="flex-1 px-4 py-3 rounded-lg bg-vz-bg border border-vz-line text-vz-ink placeholder:text-vz-ink-mute focus:outline-none focus:ring-2 focus:ring-vz-teal"
                />
                <button
                  type="submit"
                  disabled={status === "loading" || !consent}
                  className="px-6 py-3 bg-vz-teal text-white font-medium rounded-lg hover:bg-vz-teal-deep disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                >
                  {status === "loading" ? "Envoi…" : "Me prévenir"}
                </button>
              </div>
              <label className="flex items-start gap-2 text-left text-xs text-vz-ink-mute cursor-pointer">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  required
                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-vz-line text-vz-teal focus:ring-vz-teal"
                />
                <span>
                  J&apos;accepte de recevoir par e-mail les actualités de Vintiz (ouverture, ventes privées,
                  nouveautés). Je peux me désinscrire à tout moment via le lien présent dans chaque e-mail.
                </span>
              </label>
            </form>
          )}
          {status === "error" && <p className="mt-3 text-sm text-red-600">{message}</p>}
        </div>
      </section>

      {/* Reverse note + social */}
      <section className="bg-vz-bg-alt">
        <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-vz-teal">
              Engagement
            </p>
            <p className="font-display text-lg text-vz-ink mt-2">
              Les invendus sont reversés à <em>Solidarité Textiles</em>.
            </p>
            <p className="text-sm text-vz-ink-mute mt-1">
              6 rue Saint-Jacques · 27200 Vernon · ouvert mardi-samedi 10h-19h.
            </p>
          </div>
          <div className="flex gap-3">
            <a href={INSTAGRAM_URL} target="_blank" rel="noopener noreferrer" aria-label="Instagram"
              className="w-11 h-11 rounded-full border border-vz-line flex items-center justify-center text-vz-ink hover:bg-vz-teal hover:text-white hover:border-vz-teal transition-colors">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="20" height="20" rx="5" />
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
              </svg>
            </a>
            <a href={FACEBOOK_URL} target="_blank" rel="noopener noreferrer" aria-label="Facebook"
              className="w-11 h-11 rounded-full border border-vz-line flex items-center justify-center text-vz-ink hover:bg-vz-teal hover:text-white hover:border-vz-teal transition-colors">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
              </svg>
            </a>
            <a href={TIKTOK_URL} target="_blank" rel="noopener noreferrer" aria-label="TikTok"
              className="w-11 h-11 rounded-full border border-vz-line flex items-center justify-center text-vz-ink hover:bg-vz-teal hover:text-white hover:border-vz-teal transition-colors">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5" />
              </svg>
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-black text-white">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/logo-rose.png" alt="" width={36} height={36} className="h-7 w-auto opacity-90" />
            <p className="font-mono text-[11px] tracking-[0.18em] uppercase text-white/40">
              © 2026 Vintiz · Vernon · Normandie
            </p>
          </div>
          <div className="flex gap-5 font-mono text-[11px] tracking-[0.18em] uppercase text-white/40">
            <Link href="/mentions-legales" className="hover:text-vz-accent-soft transition-colors">
              Mentions légales
            </Link>
            <Link href="/cgv" className="hover:text-vz-accent-soft transition-colors">
              CGV
            </Link>
            <Link href="/confidentialite" className="hover:text-vz-accent-soft transition-colors">
              Confidentialité
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
