"use client";

import Image from "next/image";
import { useState, FormEvent } from "react";

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
      setMessage("Une erreur est survenue. Veuillez réessayer.");
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-12 bg-vintiz-bg">
      <div className="flex flex-col items-center max-w-lg w-full text-center">
        {/* Logo */}
        <div className="animate-fade-in-up">
          <Image
            src="/logo-rose.png"
            alt="Vintiz VZ Logo"
            width={100}
            height={100}
            priority
            className="mb-6"
          />
        </div>

        {/* Brand Name */}
        <h1 className="animate-fade-in-up animation-delay-200 font-serif text-3xl sm:text-4xl tracking-[0.4em] text-vintiz-black mb-8">
          V I N T I Z
        </h1>

        {/* Main Heading */}
        <h2 className="animate-fade-in-up animation-delay-400 font-serif text-4xl sm:text-5xl text-vintiz-black mb-4 italic">
          Ouverture Prochaine
        </h2>

        {/* Subtitle */}
        <p className="animate-fade-in-up animation-delay-600 font-sans text-lg sm:text-xl text-vintiz-black/70 mb-2 leading-relaxed">
          Votre nouvelle boutique de vêtements
          <br />
          de seconde main premium
        </p>

        {/* Address */}
        <p className="animate-fade-in-up animation-delay-600 font-sans text-base text-vintiz-black/50 mb-12">
          6 rue Saint-Jacques, 27200 Vernon
        </p>

        {/* Email Form */}
        <div className="animate-fade-in-up animation-delay-800 w-full">
          <p className="font-serif text-xl text-vintiz-black mb-4">
            Soyez les premiers informés
          </p>

          {status === "success" ? (
            <div className="bg-vintiz-teal/10 border border-vintiz-teal/30 rounded-lg p-4 text-vintiz-teal">
              {message}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 w-full">
              <input
                type="email"
                required
                placeholder="Votre adresse email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-1 px-4 py-3 rounded-lg border border-vintiz-pink/40 bg-white
                           text-vintiz-black placeholder:text-vintiz-black/30
                           focus:outline-none focus:ring-2 focus:ring-vintiz-teal/40 focus:border-vintiz-teal
                           transition-colors font-sans"
              />
              <button
                type="submit"
                disabled={status === "loading"}
                className="px-6 py-3 bg-vintiz-teal text-white font-sans font-medium rounded-lg
                           hover:bg-vintiz-teal/90 active:bg-vintiz-teal/80
                           disabled:opacity-50 disabled:cursor-not-allowed
                           transition-colors whitespace-nowrap"
              >
                {status === "loading" ? "Envoi..." : "S'inscrire"}
              </button>
            </form>
          )}

          {status === "error" && (
            <p className="mt-3 text-sm text-red-500">{message}</p>
          )}
        </div>

        {/* Footer */}
        <footer className="animate-fade-in-up animation-delay-1000 mt-16 pt-8 border-t border-vintiz-pink/30 w-full">
          <div className="flex items-center justify-center gap-4 mb-4">
            {/* Instagram placeholder */}
            <a
              href="#"
              aria-label="Instagram"
              className="w-10 h-10 rounded-full border border-vintiz-pink/40 flex items-center justify-center
                         text-vintiz-black/40 hover:text-vintiz-teal hover:border-vintiz-teal transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
              </svg>
            </a>
            {/* Facebook placeholder */}
            <a
              href="#"
              aria-label="Facebook"
              className="w-10 h-10 rounded-full border border-vintiz-pink/40 flex items-center justify-center
                         text-vintiz-black/40 hover:text-vintiz-teal hover:border-vintiz-teal transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
              </svg>
            </a>
            {/* TikTok placeholder */}
            <a
              href="#"
              aria-label="TikTok"
              className="w-10 h-10 rounded-full border border-vintiz-pink/40 flex items-center justify-center
                         text-vintiz-black/40 hover:text-vintiz-teal hover:border-vintiz-teal transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5" />
              </svg>
            </a>
          </div>
          <p className="text-sm text-vintiz-black/40 font-sans">
            &copy; 2026 Vintiz
          </p>
        </footer>
      </div>
    </main>
  );
}
