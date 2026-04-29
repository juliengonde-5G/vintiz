"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Step = "email" | "code";
type Channel = "email" | "sms";

export default function AccountLoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [channel, setChannel] = useState<Channel>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const requestCode = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      // Backend accepts an email OR phone in the same `email` field.
      const identifier = channel === "email"
        ? email.trim().toLowerCase()
        : email.trim().replace(/[\s.\-]/g, "");
      // The endpoint always returns 204; we don't disclose whether the account exists.
      await fetch(`${API_URL}/api/auth/magic-link/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: identifier }),
      });
      setStep("code");
      setInfo(
        channel === "sms"
          ? "Si un compte existe avec ce numéro, un code à 6 chiffres vient d'être envoyé par SMS."
          : "Si un compte existe avec cet email, un code à 6 chiffres vient d'être envoyé. Pensez à vérifier vos spams.",
      );
    } catch {
      setError("Erreur réseau. Réessayez.");
    }
    setBusy(false);
  };

  const verifyCode = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const identifier = channel === "email"
        ? email.trim().toLowerCase()
        : email.trim().replace(/[\s.\-]/g, "");
      const res = await fetch(`${API_URL}/api/auth/magic-link/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: identifier, code: code.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        // PR1: stash the JWT in localStorage so /account pages can call the API.
        // PR3 will move this to an HttpOnly cookie via a Next API route.
        try {
          window.localStorage.setItem("vintiz_account_token", data.access_token);
          window.localStorage.setItem("vintiz_account_email", email.trim().toLowerCase());
        } catch {
          /* private mode — the account pages still receive the token via redirect */
        }
        router.push("/account");
      } else if (res.status === 429) {
        setError("Trop de tentatives. Patientez avant de redemander un code.");
      } else {
        setError("Code invalide ou expiré. Demandez un nouveau code.");
      }
    } catch {
      setError("Erreur réseau. Réessayez.");
    }
    setBusy(false);
  };

  return (
    <main className="min-h-screen bg-vz-bg">
      <Navbar />
      <section className="max-w-md mx-auto px-4 pt-16 pb-24">
        <h1 className="text-3xl font-display font-bold text-black mb-2">Mon espace Vintiz</h1>
        <p className="text-gray-600 mb-8">
          Connectez-vous avec un code à 6 chiffres reçu par email — aucun mot de passe à retenir.
        </p>

        {step === "email" && (
          <form onSubmit={requestCode} className="space-y-4">
            <div className="inline-flex border border-vz-line rounded-full p-0.5 text-xs font-medium">
              <button
                type="button"
                onClick={() => { setChannel("email"); setEmail(""); }}
                className={`px-4 py-1.5 rounded-full transition-colors ${
                  channel === "email" ? "bg-vz-teal text-white" : "text-vz-ink-mute hover:text-vz-ink"
                }`}
              >
                Par email
              </button>
              <button
                type="button"
                onClick={() => { setChannel("sms"); setEmail(""); }}
                className={`px-4 py-1.5 rounded-full transition-colors ${
                  channel === "sms" ? "bg-vz-teal text-white" : "text-vz-ink-mute hover:text-vz-ink"
                }`}
              >
                Par SMS
              </button>
            </div>
            <div>
              <label className="block text-sm text-gray-700 mb-1" htmlFor="email-input">
                {channel === "email" ? "Email" : "Téléphone"}
              </label>
              <input
                id="email-input"
                type={channel === "email" ? "email" : "tel"}
                inputMode={channel === "email" ? "email" : "tel"}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={channel === "email" ? "vous@email.fr" : "+33 6 12 34 56 78"}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
              />
              <p className="text-xs text-vz-ink-mute mt-1">
                {channel === "email"
                  ? "Le code arrive en 30 s. Vérifiez vos spams si besoin."
                  : "Le SMS arrive en quelques secondes. Tarif opérateur standard."}
              </p>
            </div>
            <button
              type="submit"
              disabled={busy || !email}
              className="w-full bg-vz-teal text-white py-3 rounded-lg font-medium hover:bg-vz-teal/90 disabled:opacity-50"
            >
              {busy ? "Envoi…" : channel === "email" ? "Recevoir mon code par email" : "Recevoir mon code par SMS"}
            </button>
          </form>
        )}

        {step === "code" && (
          <form onSubmit={verifyCode} className="space-y-4">
            {info && (
              <div className="p-3 bg-vz-teal/10 text-vz-teal rounded-lg text-sm">{info}</div>
            )}
            <div>
              <label className="block text-sm text-gray-700 mb-1" htmlFor="code-input">
                Code à 6 chiffres
              </label>
              <input
                id="code-input"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                required
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="000000"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-2xl tracking-[0.5em] focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                autoFocus
              />
            </div>
            <button
              type="submit"
              disabled={busy || code.length !== 6}
              className="w-full bg-vz-teal text-white py-3 rounded-lg font-medium hover:bg-vz-teal/90 disabled:opacity-50"
            >
              {busy ? "Vérification…" : "Me connecter"}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setCode("");
                setError("");
                setInfo("");
              }}
              className="w-full text-sm text-gray-600 underline"
            >
              Modifier l&apos;email ou redemander un code
            </button>
          </form>
        )}

        {error && <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

        <p className="mt-8 text-xs text-gray-500">
          La carte de fidélité est gratuite — adhérez en boutique à Vernon.
          1 € dépensé = 1 point. 100 points = bon de 8 €. Validité 24 mois sans activité.
        </p>
      </section>
      <Footer />
    </main>
  );
}
