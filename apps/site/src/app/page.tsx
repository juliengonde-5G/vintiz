"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, FormEvent } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const values = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    ),
    title: "Selection Premium",
    desc: "Chaque piece est choisie avec soin pour sa qualite, son style et son etat impeccable.",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
        <path d="M14.31 8l5.74 9.94M9.69 8h11.48M7.38 12l5.74-9.94M9.69 16L3.95 6.06M14.31 16H2.83M16.62 12l-5.74 9.94" />
      </svg>
    ),
    title: "Mode Responsable",
    desc: "Donnez une seconde vie aux vetements. Un geste pour votre style et pour la planete.",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
    ),
    title: "Marques Recherchees",
    desc: "Sandro, Maje, Isabel Marant, Ba&sh, The Kooples et bien d'autres a prix doux.",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M8 14s1.5 2 4 2 4-2 4-2" />
        <line x1="9" y1="9" x2="9.01" y2="9" />
        <line x1="15" y1="9" x2="15.01" y2="9" />
      </svg>
    ),
    title: "Experience Boutique",
    desc: "Un accueil chaleureux, des conseils personnalises dans un ecrin elegant.",
  },
];

const brands = [
  "Sandro", "Maje", "Isabel Marant", "Ba&sh", "The Kooples",
  "Claudie Pierlot", "Zadig & Voltaire", "IRO", "Comptoir des Cotonniers",
  "Gerard Darel", "Vanessa Bruno", "American Vintage", "COS",
];

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
    <>
      <Navbar />

      {/* Hero */}
      <section className="min-h-screen flex items-center justify-center px-6 pt-16 bg-vintiz-bg">
        <div className="max-w-4xl mx-auto text-center">
          <div className="animate-fade-in-up">
            <Image
              src="/logo-teal.png"
              alt="Vintiz"
              width={180}
              height={180}
              priority
              className="mx-auto mb-6 h-32 w-auto sm:h-40"
            />
          </div>
          <h1 className="animate-fade-in-up animation-delay-200 font-serif text-5xl sm:text-6xl lg:text-7xl text-vintiz-black mb-6 leading-tight">
            Mode <em className="text-vintiz-teal">Premium</em>,<br />
            Seconde Vie
          </h1>
          <p className="animate-fade-in-up animation-delay-400 text-lg sm:text-xl text-vintiz-black/60 max-w-2xl mx-auto mb-10 leading-relaxed">
            Des pieces uniques selectionnees avec soin. Marques recherchees, qualite irreprochable, prix justes. Bienvenue chez Vintiz.
          </p>
          <div className="animate-fade-in-up animation-delay-600 flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/boutique"
              className="px-8 py-4 bg-vintiz-teal text-white font-medium rounded-lg hover:bg-vintiz-teal/90 transition-colors text-center"
            >
              Decouvrir la boutique
            </Link>
            <Link
              href="/espace-client"
              className="px-8 py-4 border-2 border-vintiz-teal text-vintiz-teal font-medium rounded-lg hover:bg-vintiz-teal hover:text-white transition-colors text-center"
            >
              Espace Client
            </Link>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <h2 className="font-serif text-3xl sm:text-4xl text-center text-vintiz-black mb-4">
            Pourquoi <em className="text-vintiz-teal">Vintiz</em> ?
          </h2>
          <p className="text-center text-vintiz-black/50 mb-16 max-w-xl mx-auto">
            Une experience shopping unique, pensee pour les amoureuses de belles pieces.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {values.map((v) => (
              <div key={v.title} className="text-center p-6 rounded-2xl hover:bg-vintiz-bg transition-colors">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-vintiz-pink/20 flex items-center justify-center text-vintiz-teal">
                  {v.icon}
                </div>
                <h3 className="font-serif text-lg font-semibold text-vintiz-black mb-2">{v.title}</h3>
                <p className="text-sm text-vintiz-black/50 leading-relaxed">{v.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Brands */}
      <section className="py-20 px-6 bg-vintiz-bg">
        <div className="max-w-6xl mx-auto text-center">
          <h2 className="font-serif text-3xl sm:text-4xl text-vintiz-black mb-4">
            Nos <em className="text-vintiz-teal">Marques</em>
          </h2>
          <p className="text-vintiz-black/50 mb-12 max-w-xl mx-auto">
            Une selection exigeante de marques milieu et haut de gamme.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            {brands.map((b) => (
              <span
                key={b}
                className="px-5 py-2.5 bg-white rounded-full text-sm font-medium text-vintiz-black/70 border border-vintiz-pink/30 hover:border-vintiz-teal hover:text-vintiz-teal transition-colors"
              >
                {b}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Location */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="font-serif text-3xl sm:text-4xl text-vintiz-black mb-4">
                Venez nous <em className="text-vintiz-teal">rendre visite</em>
              </h2>
              <p className="text-vintiz-black/60 mb-8 leading-relaxed">
                Situee en plein coeur de Vernon, notre boutique vous accueille dans un cadre chaleureux et elegant. Poussez la porte, decouvrez nos trouvailles du moment.
              </p>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" className="mt-1 shrink-0">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                    <circle cx="12" cy="10" r="3" />
                  </svg>
                  <div>
                    <p className="font-medium text-vintiz-black">6 rue Saint-Jacques</p>
                    <p className="text-sm text-vintiz-black/50">27200 Vernon</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" className="mt-1 shrink-0">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  <div>
                    <p className="font-medium text-vintiz-black">Horaires</p>
                    <p className="text-sm text-vintiz-black/50">Mardi - Samedi : 10h - 19h</p>
                    <p className="text-sm text-vintiz-black/50">Dimanche &amp; Lundi : Ferme</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="rounded-2xl overflow-hidden shadow-lg h-80 bg-vintiz-pink/10 flex items-center justify-center">
              <iframe
                src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2608.5!2d1.4773!3d49.0926!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x47e6b6c0d0d0d0d%3A0x0!2s6+Rue+Saint-Jacques%2C+27200+Vernon!5e0!3m2!1sfr!2sfr!4v1"
                width="100%"
                height="100%"
                style={{ border: 0 }}
                allowFullScreen
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                title="Vintiz Vernon"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Newsletter */}
      <section className="py-20 px-6 bg-vintiz-teal">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="font-serif text-3xl sm:text-4xl text-white mb-4">
            Restez informee
          </h2>
          <p className="text-white/70 mb-8">
            Recevez nos nouveautes, ventes privees et bons plans directement dans votre boite mail.
          </p>
          {status === "success" ? (
            <div className="bg-white/10 border border-white/30 rounded-lg p-4 text-white">
              {message}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto">
              <input
                type="email"
                required
                placeholder="Votre adresse email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-1 px-4 py-3 rounded-lg bg-white/10 border border-white/30 text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-white/40"
              />
              <button
                type="submit"
                disabled={status === "loading"}
                className="px-6 py-3 bg-white text-vintiz-teal font-medium rounded-lg hover:bg-white/90 disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {status === "loading" ? "Envoi..." : "S'inscrire"}
              </button>
            </form>
          )}
          {status === "error" && (
            <p className="mt-3 text-sm text-red-200">{message}</p>
          )}
        </div>
      </section>

      <Footer />
    </>
  );
}
