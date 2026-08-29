"use client";

import { FormEvent, useState } from "react";

export default function NewsletterCard() {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!consent || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, consent: true, source: "site_landing" }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.error || "L'inscription a échoué. Veuillez réessayer.");
        return;
      }
      setDone(true);
    } catch {
      setError("Une erreur est survenue. Veuillez réessayer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative mx-auto max-w-md">
      {/* Pink tag shape with punched hole */}
      <div className="relative bg-vz-accent-soft rounded-[28px] px-8 pt-14 pb-10 shadow-sm">
        <span className="absolute top-4 left-1/2 -translate-x-1/2 h-5 w-5 rounded-full bg-vz-bg" />
        <h3 className="text-center font-display text-[1.6rem] leading-tight text-black">
          Et si on restait en
        </h3>
        <p className="text-center italic text-2xl text-black mb-4" style={{ fontFamily: "'DM Serif Display', Georgia, serif" }}>
          contact ?
        </p>
        <p className="text-center text-[13px] text-black/80 leading-relaxed mb-5">
          Une dose d&apos;inspiration, des conseils mode responsable, et des offres
          exclusives rien que pour vous. <span aria-hidden>💌</span> Inscrivez-vous et laissez
          la créativité venir à vous !
        </p>
        {done ? (
          <p className="rounded-full bg-white px-4 py-3 text-center text-sm text-vz-teal">
            Merci ! Votre inscription est bien enregistrée.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <input
              type="email"
              required
              placeholder="contact@vintiz.fr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-full bg-white px-5 py-3 text-sm text-black placeholder:text-black/40 focus:outline-none focus:ring-2 focus:ring-vz-teal"
            />
            <label className="flex items-start gap-2 px-2 text-left text-[11px] leading-snug text-black/70">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 h-3.5 w-3.5 accent-vz-teal"
              />
              <span>
                J&apos;accepte de recevoir la newsletter Vintiz. Je peux me
                désinscrire à tout moment via le lien présent dans chaque email.
              </span>
            </label>
            {error && (
              <p className="rounded-2xl bg-white/80 px-4 py-2 text-center text-xs text-red-600">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="mx-auto inline-flex items-center justify-center rounded-full bg-[#4B3A5A] px-10 py-3 text-sm tracking-wider text-white hover:bg-[#3e3049] transition-colors disabled:opacity-60"
            >
              {submitting ? "INSCRIPTION…" : "S'INSCRIRE"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
