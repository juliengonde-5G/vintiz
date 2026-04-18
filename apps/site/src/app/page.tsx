"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, FormEvent } from "react";

const INSTAGRAM_URL = "https://www.instagram.com/vintiz.vernon/";
const FACEBOOK_URL = "https://www.facebook.com/vintiz.vernon";
const TIKTOK_URL = "https://www.tiktok.com/@vintiz.vernon";

export default function Home() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("success");
        setMessage(data.message);
        setEmail("");
      } else {
        setStatus("error");
        setMessage(data.error);
      }
    } catch {
      setStatus("error");
      setMessage("Une erreur est survenue. Veuillez reessayer.");
    }
  }

  return (
    <main className="min-h-screen flex flex-col">
      <section className="flex-1 flex items-center justify-center px-6 py-16 bg-cream">
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

          <h1 className="animate-fade-in-up animation-delay-200 font-display text-4xl sm:text-5xl lg:text-6xl text-black mb-6 leading-tight">
            Mode <em className="text-teal not-italic">Premium</em>,
            <br />
            Seconde Vie.
          </h1>

          <p className="animate-fade-in-up animation-delay-400 text-lg sm:text-xl text-black/70 max-w-xl mx-auto mb-10 leading-relaxed">
            Des pièces uniques sélectionnées avec soin. Marques recherchées,
            qualité irréprochable, prix justes.
          </p>

          <div className="animate-fade-in-up animation-delay-600 inline-flex flex-col items-center gap-2 bg-white/70 rounded-2xl px-8 py-6 border border-pink/30 backdrop-blur-sm mb-8">
            <p className="text-xs uppercase tracking-[0.25em] text-teal font-medium">
              Ouverture prochaine
            </p>
            <p className="text-xl font-display text-black">
              6 rue Saint-Jacques
            </p>
            <p className="text-sm text-black/60">27200 Vernon — Normandie</p>
            <a
              href="#newsletter"
              className="mt-3 text-sm font-medium text-teal hover:underline"
            >
              Être prévenue de l&apos;ouverture ↓
            </a>
          </div>

          <div
            id="newsletter"
            className="animate-fade-in-up animation-delay-800 max-w-lg mx-auto bg-white rounded-2xl shadow-sm border border-pink/30 px-6 py-7 mb-10"
          >
            <h2 className="font-display text-xl text-black mb-1">
              Soyez la première informée
            </h2>
            <p className="text-sm text-black/60 mb-5">
              Laissez votre e-mail : vous serez prévenue en avant-première de
              l&apos;ouverture, des ventes privées et des nouveautés.
            </p>
            {status === "success" ? (
              <div className="bg-teal/10 border border-teal/30 rounded-lg p-4 text-teal">
                {message}
              </div>
            ) : (
              <form
                onSubmit={handleSubmit}
                className="flex flex-col sm:flex-row gap-3"
              >
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
                  className="flex-1 px-4 py-3 rounded-lg bg-cream/50 border border-black/10 text-black placeholder:text-black/40 focus:outline-none focus:ring-2 focus:ring-teal"
                />
                <button
                  type="submit"
                  disabled={status === "loading"}
                  className="px-6 py-3 bg-teal text-white font-medium rounded-lg hover:bg-teal-600 disabled:opacity-50 transition-colors whitespace-nowrap"
                >
                  {status === "loading" ? "Envoi…" : "Me prévenir"}
                </button>
              </form>
            )}
            {status === "error" && (
              <p className="mt-3 text-sm text-red-600">{message}</p>
            )}
            <p className="mt-4 text-xs text-black/40">
              Aucun spam. Désinscription en un clic. Voir la{" "}
              <Link href="/confidentialite" className="underline hover:text-teal">
                politique de confidentialité
              </Link>
              .
            </p>
          </div>

          <div className="animate-fade-in-up animation-delay-1000">
            <p className="text-xs uppercase tracking-[0.25em] text-black/50 mb-4">
              Suivez-nous
            </p>
            <div className="flex gap-3 justify-center">
              <a
                href={INSTAGRAM_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram Vintiz"
                className="w-11 h-11 rounded-full border border-teal/30 flex items-center justify-center text-teal hover:bg-teal hover:text-white transition-colors"
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
                className="w-11 h-11 rounded-full border border-teal/30 flex items-center justify-center text-teal hover:bg-teal hover:text-white transition-colors"
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
                className="w-11 h-11 rounded-full border border-teal/30 flex items-center justify-center text-teal hover:bg-teal hover:text-white transition-colors"
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
              className="hover:text-pink transition-colors"
            >
              Mentions légales
            </Link>
            <Link href="/cgv" className="hover:text-pink transition-colors">
              CGV
            </Link>
            <Link
              href="/confidentialite"
              className="hover:text-pink transition-colors"
            >
              Confidentialité
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
