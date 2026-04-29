"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, FormEvent } from "react";

const INSTAGRAM_URL = "https://www.instagram.com/vintiz.vernon/";
const FACEBOOK_URL = "https://www.facebook.com/vintiz.vernon";
const TIKTOK_URL = "https://www.tiktok.com/@vintiz.vernon";

export default function Home() {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

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
      setMessage("Une erreur est survenue. Veuillez reessayer.");
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <section className="flex-1 flex items-center justify-center px-6 py-16 bg-vz-bg">
        <div className="max-w-2xl mx-auto text-center">
          <div className="animate-fade-in-up">
            <Image
              src="/logo-teal.png"
              alt="Vintiz - Boutique seconde main premium Vernon"
              width={200}
              height={200}
              priority
              className="mx-auto mb-8 h-32 w-auto sm:h-40"
            />
          </div>

          <h1 className="animate-fade-in-up animation-delay-200 font-display font-[450] text-4xl sm:text-5xl lg:text-6xl text-vz-ink mb-6 leading-tight tracking-[-0.015em]">
            Votre nouvelle destination
            <br />
            <em className="text-vz-teal not-italic">Slow Fashion</em> premium.
          </h1>

          <p className="animate-fade-in-up animation-delay-400 text-lg sm:text-xl text-vz-ink-soft max-w-xl mx-auto mb-10 leading-relaxed">
            Des pièces uniques sélectionnées avec soin. Marques recherchées,
            qualité irréprochable, prix justes.
          </p>

          <div className="animate-fade-in-up animation-delay-600 inline-flex flex-col items-center gap-2 bg-vz-surface/70 rounded-2xl px-8 py-6 border border-vz-accent-soft/30 backdrop-blur-sm mb-8">
            <p className="text-xs uppercase tracking-[0.12em] text-vz-teal font-medium">
              Ouverture prochaine
            </p>
            <p className="text-xl font-display text-vz-ink">
              6 rue Saint-Jacques
            </p>
            <p className="text-sm text-vz-ink-mute">27200 Vernon — Normandie</p>
            <a
              href="#newsletter"
              className="mt-3 text-sm font-medium text-vz-teal hover:underline"
            >
              Être prévenue de l&apos;ouverture ↓
            </a>
          </div>

          <div
            id="newsletter"
            className="animate-fade-in-up animation-delay-800 max-w-lg mx-auto bg-vz-surface rounded-2xl shadow-sm border border-vz-accent-soft/30 px-6 py-7 mb-10"
          >
            <h2 className="font-display text-xl text-vz-ink mb-1">
              Soyez la première informée
            </h2>
            <p className="text-sm text-vz-ink-mute mb-5">
              Laissez votre e-mail : vous serez prévenue en avant-première de
              l&apos;ouverture, des ventes privées et des nouveautés.
            </p>
            {status === "success" ? (
              <div className="bg-vz-teal/10 border border-vz-teal/30 rounded-lg p-4 text-vz-teal">
                {message}
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col sm:flex-row gap-3">
                  <label htmlFor="email" className="sr-only">
                    Adresse email
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    placeholder="votre@email.fr"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="flex-1 px-4 py-3 rounded-lg bg-vz-bg/50 border border-black/10 text-vz-ink placeholder:text-vz-ink/40 focus:outline-none focus:ring-2 focus:ring-vz-teal"
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
                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-black/30 text-vz-teal focus:ring-vz-teal"
                  />
                  <span>
                    J&apos;accepte de recevoir par e-mail les actualités de Vintiz
                    (ouverture, ventes privées, nouveautés). Je peux me désinscrire
                    à tout moment via le lien présent dans chaque e-mail.
                  </span>
                </label>
              </form>
            )}
            {status === "error" && (
              <p className="mt-3 text-sm text-red-600">{message}</p>
            )}
          </div>

          <div className="animate-fade-in-up animation-delay-1000">
            <p className="text-xs uppercase tracking-[0.12em] text-vz-ink/50 mb-4">
              Suivez-nous
            </p>
            <div className="flex gap-3 justify-center">
              <a
                href={INSTAGRAM_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram Vintiz"
                className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                </svg>
              </a>
              <a
                href={FACEBOOK_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Facebook Vintiz"
                className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
                </svg>
              </a>
              <a
                href={TIKTOK_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="TikTok Vintiz"
                className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </section>

      <footer className="bg-black text-white">
        <div className="max-w-4xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image
              src="/logo-rose.png"
              alt=""
              width={44}
              height={44}
              className="h-8 w-auto"
            />
            <p className="text-xs text-white/40">
              &copy; 2026 Vintiz — Vernon, Normandie
            </p>
          </div>
          <div className="flex gap-5 text-xs text-white/40">
            <Link
              href="/mentions-legales"
              className="hover:text-vz-accent-soft transition-colors"
            >
              Mentions légales
            </Link>
            <Link href="/cgv" className="hover:text-vz-accent-soft transition-colors">
              CGV
            </Link>
            <Link
              href="/confidentialite"
              className="hover:text-vz-accent-soft transition-colors"
            >
              Confidentialité
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
